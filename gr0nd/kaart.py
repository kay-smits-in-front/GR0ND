"""Kaartmodel van GR0ND: overzichtskaart, kaartlagen, RD-omrekening en zoeken.

LET OP: de zones hieronder zijn een grove VOORBEELDKAART (rechthoeken in RD) voor het overzicht.
"""

import json
import re
import urllib.request
from dataclasses import asdict, dataclass
from functools import cache
from pathlib import Path
from urllib.parse import urlencode

import numpy as np
from pyproj import Transformer

DATA_MAP = Path(__file__).parent / "data"

RD_BEREIK = (-7000.0, 289000.0, 300000.0, 629000.0)  # x_min, y_min, x_max, y_max (EPSG:28992)
ZONEKAART_CEL_M = 2500.0


@dataclass(frozen=True)
class Zone:
    naam: str
    kleur: str  # voor de overzichtskaart


ZONES = (
    Zone("Kustklei en veen", "#7f8f78"),
    Zone("Rivierengebied", "#8d8a62"),
    Zone("Hoge zandgronden", "#b9a15a"),
    Zone("Drents plateau (keileem)", "#a08a6b"),
    Zone("Zuid-Limburg (löss)", "#c9a972"),
)
KUSTKLEI, RIVIEREN, ZAND, DRENTS, LOESS = range(len(ZONES))


def zone_index(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Geef per RD-punt de zone. Volgorde bepaalt de voorrang. Voorbeeldregels, geen BRO."""
    zones = np.full(np.shape(x), ZAND, dtype=int)
    kust = ((x <= 135000) & (y >= 430000)) | ((x <= 95000) & (y < 430000)) | (y >= 575000)
    flevoland = (x >= 145000) & (x <= 185000) & (y >= 475000) & (y <= 530000)
    rivieren = (x >= 105000) & (x <= 205000) & (y >= 405000) & (y <= 445000)
    drents = (x >= 215000) & (x <= 265000) & (y >= 515000) & (y <= 575000)
    loess = (x >= 170000) & (y <= 335000)
    for masker, zone in ((kust, KUSTKLEI), (flevoland, KUSTKLEI), (rivieren, RIVIEREN)):
        zones[masker] = zone
    zones[drents] = DRENTS
    zones[loess] = LOESS
    return zones


@cache
def nederland() -> dict:
    """Omtrek van Nederland (RD) plus een grove zonekaart voor de overzichtskaart."""
    omtrek = json.loads((DATA_MAP / "nederland_rd.json").read_text())
    x_min, y_min, x_max, y_max = RD_BEREIK
    xs = np.arange(0.0, x_max, ZONEKAART_CEL_M)
    ys = np.arange(y_min, y_max, ZONEKAART_CEL_M)
    x, y = np.meshgrid(xs + ZONEKAART_CEL_M / 2, ys + ZONEKAART_CEL_M / 2)
    return {
        "crs": omtrek["crs"],
        "bron": "voorbeelddata",
        "polygonen": omtrek["polygonen"],
        "zonekaart": {
            "x0": 0.0, "y0": y_min, "cel": ZONEKAART_CEL_M, "nx": len(xs), "ny": len(ys),
            "zones": zone_index(x, y).ravel().tolist(),
        },
        "legenda": [{"naam": zone.naam, "kleur": zone.kleur} for zone in ZONES],
    }  # fmt: skip


# ---------- coördinaten ----------


@cache
def transformer(van: str, naar: str) -> Transformer:
    return Transformer.from_crs(van, naar, always_xy=True)


def wgs84_naar_rd(lon: float, lat: float) -> tuple[float, float]:
    """Zet lengte- en breedtegraad om naar RD-meters (zonder RDNAPTRANS-raster ca. 1 m)."""
    x, y = transformer("EPSG:4326", "EPSG:28992").transform(lon, lat)
    return round(x, 2), round(y, 2)


def rd_naar_wgs84(x: float, y: float) -> tuple[float, float]:
    """Zet RD-meters om naar lengte- en breedtegraad (lon, lat)."""
    lon, lat = transformer("EPSG:28992", "EPSG:4326").transform(x, y)
    return round(lon, 7), round(lat, 7)


# ---------- kaartlagen (PDOK) ----------


@dataclass(frozen=True)
class KaartLaag:
    id: str
    naam: str
    groep: str  # "achtergrond" (kies er één) of "laag" (aan en uit)
    tegels: str  # tegel-URL voor MapLibre; pdok:// loopt via onze eigen tegelhandler
    bron: str
    standaard: bool = False
    max_zoom: int = 19


PDOK = "service.pdok.nl"


def wmts_tegels(pad: str, laag: str, formaat: str) -> str:
    """Tegel-URL van een PDOK-WMTS in Web Mercator (EPSG:3857). De browser vult de matrix op."""
    vraag = (
        f"service=WMTS&request=GetTile&version=1.0.0&layer={laag}&style=default"
        f"&tilematrixset=EPSG:3857&format={formaat}&tilematrix={{z}}&tilerow={{y}}&tilecol={{x}}"
    )
    return f"pdok://{PDOK}{pad}?{vraag}"


def wms_tegels(pad: str, lagen: str) -> str:
    """Tegel-URL van een PDOK-WMS met doorzichtige achtergrond (EPSG:3857)."""
    vraag = (
        f"service=WMS&version=1.3.0&request=GetMap&layers={lagen}&styles=&format=image/png"
        "&transparent=true&crs=EPSG:3857&width=256&height=256&bbox={bbox-epsg-3857}"
    )
    return f"pdok://{PDOK}{pad}?{vraag}"


KAARTLAGEN = (
    KaartLaag("brt", "Kaart (BRT)", "achtergrond",
              wmts_tegels("/brt/achtergrondkaart/wmts/v2_0", "standaard", "image/png"),
              "PDOK / Kadaster BRT", standaard=True),
    KaartLaag("brt-grijs", "Kaart grijs (BRT)", "achtergrond",
              wmts_tegels("/brt/achtergrondkaart/wmts/v2_0", "grijs", "image/png"),
              "PDOK / Kadaster BRT"),
    KaartLaag("luchtfoto", "Luchtfoto 8 cm", "achtergrond",
              wmts_tegels("/hwh/luchtfotorgb/wmts/v1_0", "Actueel_orthoHR", "image/jpeg"),
              "PDOK / Beeldmateriaal Nederland", max_zoom=20),
    KaartLaag("percelen", "Kadastrale percelen", "laag",
              wms_tegels("/kadaster/kadastralekaart/wms/v5_0", "Perceel"), "PDOK / Kadaster"),
    KaartLaag("gebouwen", "Gebouwen (kadaster)", "laag",
              wms_tegels("/kadaster/kadastralekaart/wms/v5_0", "Bebouwing"), "PDOK / Kadaster"),
    KaartLaag("wegen", "Wegen (NWB)", "laag",
              wms_tegels("/rws/nationaal-wegenbestand-wegen/wms/v1_0", "wegvakken"),
              "PDOK / Rijkswaterstaat"),
    KaartLaag("spoor", "Spoorwegen", "laag",
              wms_tegels("/prorail/spoorwegen/wms/v1_0", "spooras,station,overweg,wissel"),
              "PDOK / ProRail"),
    KaartLaag("vaarwegen", "Vaarwegen", "laag",
              wms_tegels("/rws/nationaal-wegenbestand-vaarwegen/wms/v1_0", "vaarwegvakken"),
              "PDOK / Rijkswaterstaat"),
    KaartLaag("bodem", "Bodemkaart (BRO)", "laag",
              wms_tegels("/tno/bro-bodemkaart/wms/v1_0", "soil"), "PDOK / TNO BRO"),
    KaartLaag("natura2000", "Natura 2000", "laag",
              wms_tegels("/rvo/natura2000/wms/v1_0", "natura2000"), "PDOK / RVO"),
)  # fmt: skip

# Wel gewenst, nog niet ingebouwd: de bron is nog niet gecontroleerd of is niet openbaar.
LAGEN_VOLGT = (
    ("Hoogspanning en andere kabels", "Geen openbare landelijke bron; KLIC is niet open data."),
    ("Explosieven (bominslagen)", "Geen landelijke open bron gevonden; vaak per gemeente."),
    ("Scholen", "Bron nog niet gekozen."),
    ("Stadsgebied", "PDOK heeft CBS Bevolkingskernen; laagnaam nog te controleren."),
    ("Natuurregels", "PDOK heeft Natuurnetwerk en Nationale Parken; lagen nog te controleren."),
)  # fmt: skip


def kaartlagen() -> dict:
    return {
        "lagen": [asdict(laag) for laag in KAARTLAGEN],
        "volgt": [{"naam": naam, "reden": reden} for naam, reden in LAGEN_VOLGT],
    }


# ---------- locatie zoeken (PDOK Locatieserver) ----------

LOCATIESERVER = "https://api.pdok.nl/bzk/locatieserver/search/v3_1"
ZOOM_PER_TYPE = {
    "adres": 18, "perceel": 18, "weg": 16, "postcode": 16, "buurt": 15, "wijk": 14,
    "woonplaats": 13, "gemeente": 11, "waterschap": 11, "provincie": 9,
}  # fmt: skip


def haal_json(url: str) -> dict:
    """Haal JSON op. Gooit OSError als de dienst niet bereikbaar is."""
    verzoek = urllib.request.Request(url, headers={"User-Agent": "GR0ND"})
    with urllib.request.urlopen(verzoek, timeout=8) as antwoord:
        return json.load(antwoord)


def zoek_locaties(tekst: str, aantal: int = 8) -> list[dict]:
    """Suggesties bij een zoektekst: id, naam en type."""
    if len(tekst.strip()) < 2:
        return []
    vraag = urlencode({"q": tekst.strip(), "rows": aantal})
    docs = haal_json(f"{LOCATIESERVER}/suggest?{vraag}")["response"]["docs"]
    return [{"id": d["id"], "naam": d["weergavenaam"], "type": d["type"]} for d in docs]


def lees_punt(wkt: str) -> tuple[float, float]:
    """Lees 'POINT(lon lat)' en geef (lon, lat)."""
    gevonden = re.fullmatch(r"POINT\(\s*(-?[\d.]+)\s+(-?[\d.]+)\s*\)", wkt.strip())
    if not gevonden:
        raise ValueError(f"Onbekend puntformaat: {wkt}")
    return float(gevonden[1]), float(gevonden[2])


def zoek_locatie(id_: str) -> dict:
    """De plek bij een suggestie: naam, lon, lat en een passend zoomniveau."""
    vraag = urlencode({"id": id_, "fl": "id,weergavenaam,centroide_ll,type"})
    docs = haal_json(f"{LOCATIESERVER}/lookup?{vraag}")["response"]["docs"]
    if not docs:
        raise LookupError("Deze locatie is niet gevonden.")
    doc = docs[0]
    lon, lat = lees_punt(doc["centroide_ll"])
    return {
        "naam": doc["weergavenaam"], "lon": lon, "lat": lat,
        "zoom": ZOOM_PER_TYPE.get(doc.get("type", ""), 15),
    }  # fmt: skip
