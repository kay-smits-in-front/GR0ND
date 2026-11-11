"""Kaartmodel van GR0ND: overzichtskaart, kaartlagen, zoeken en het reserveblok.

LET OP: de grondlagen en zones hieronder zijn VOORBEELDDATA (grove rechthoeken in RD). Het 3D-blok
gebruikt ze alleen als GeoTOP niet bereikbaar is; de app zegt dat. Afmetingen in meters.
"""

import json
import math
import re
import urllib.request
from dataclasses import asdict, dataclass
from functools import cache
from pathlib import Path
from urllib.parse import urlencode

import numpy as np
from pyproj import Transformer

DATA_MAP = Path(__file__).parent / "data"

DIEPTE_M = 50.0
RD_BEREIK = (-7000.0, 289000.0, 300000.0, 629000.0)  # x_min, y_min, x_max, y_max (EPSG:28992)
ZONEKAART_CEL_M = 2500.0


@dataclass(frozen=True)
class LaagType:
    id: str
    naam: str
    kleur: str  # basiskleur aan het oppervlak; de weergave verdonkert met de diepte


LAGEN = (
    LaagType("toplaag", "Humeuze toplaag (bouwvoor)", "#4a3626"),
    LaagType("loess", "Löss", "#c9a972"),
    LaagType("klei", "Klei", "#a0714d"),
    LaagType("veen", "Veen", "#3b2a1c"),
    LaagType("siltige_klei", "Siltige klei", "#8f8a64"),
    LaagType("fijn_zand", "Fijn zand (dekzand)", "#d9c48a"),
    LaagType("keileem", "Keileem", "#94775a"),
    LaagType("grof_zand", "Grof zand en grind", "#c98f4e"),
)


@dataclass(frozen=True)
class Zone:
    naam: str
    kleur: str  # voor de overzichtskaart
    dikten_m: tuple[float, ...]  # per laag; de laatste laag krijgt de rest tot DIEPTE_M
    grondwater_m: float  # diepte van de grondwaterspiegel onder maaiveld


ZONES = (
    Zone("Kustklei en veen", "#7f8f78", (0.3, 0, 2.5, 2.5, 3.0, 12.0, 0, 0), 0.7),
    Zone("Rivierengebied", "#8d8a62", (0.3, 0, 3.0, 0, 2.5, 4.0, 0, 0), 1.0),
    Zone("Hoge zandgronden", "#b9a15a", (0.3, 0, 0, 0, 0, 9.0, 0, 0), 2.0),
    Zone("Drents plateau (keileem)", "#a08a6b", (0.3, 0, 0, 0, 0, 4.0, 4.0, 0), 1.2),
    Zone("Zuid-Limburg (löss)", "#c9a972", (0.3, 8.0, 0, 0, 0, 0, 0, 0), 4.0),
)
KUSTKLEI, RIVIEREN, ZAND, DRENTS, LOESS = range(len(ZONES))
DIKTEN = np.array([zone.dikten_m for zone in ZONES], dtype=float)


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


def ruis(x: np.ndarray, y: np.ndarray, fase: float) -> np.ndarray:
    """Vloeiende, deterministische variatie tussen -1 en 1 (golflengtes van 100 tot 800 m)."""
    golf = (
        np.sin(x / 173 + fase) * np.cos(y / 211 + 2 * fase)
        + 0.7 * np.sin((x + y) / 419 + 3 * fase)
        + 0.3 * np.sin(x / 57 - y / 83 + 5 * fase)
    )
    return np.clip(golf / 2.0, -1.0, 1.0)


def laagdikten(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Dikte per laag (laatste as) voor elk punt. De onderste laag vult aan tot DIEPTE_M."""
    basis = DIKTEN[zone_index(x, y)]
    variatie = np.stack([1 + 0.3 * ruis(x, y, fase=i + 1) for i in range(len(LAGEN))], axis=-1)
    dikten = basis * variatie
    bovenste = dikten[..., :-1]
    totaal = bovenste.sum(axis=-1)
    schaal = np.minimum(1.0, (DIEPTE_M - 5.0) / np.maximum(totaal, 1e-9))
    dikten[..., :-1] = bovenste * schaal[..., None]
    dikten[..., -1] = DIEPTE_M - dikten[..., :-1].sum(axis=-1)
    return dikten


BLOK_MAX_M = 15_000.0  # grootste zijde van een gebied dat als blok wordt opgevraagd
BLOK_RASTER = (8, 96)  # kleinste en grootste aantal rasterpunten per zijde


def georeferentie(x: float, y: float) -> dict:
    """Plek in lengte/breedtegraad en de hoek tussen RD-noord en ware noord (graden, oost positief).

    Nodig om 3D-data in ECEF (3D Tiles) in het RD-vlak van het blok te leggen.
    """
    naar_ll = transformer("EPSG:28992", "EPSG:4326")
    lon, lat = naar_ll.transform(x, y)
    lon_n, lat_n = naar_ll.transform(x, y + 100.0)
    oost = (lon_n - lon) * math.cos(math.radians(lat))
    noord = lat_n - lat
    return {"lon": lon, "lat": lat, "convergentie": math.degrees(math.atan2(oost, noord))}


def blok(x0: float, y0: float, x1: float, y1: float, n: int = 48) -> dict:
    """Bodemlagen van een gebied (RD, meters) op een raster van n × n punten, voor het 3D-blok.

    `onderkant[i]` is de diepte van de onderkant van laag i onder maaiveld, rij voor rij van
    zuid naar noord en binnen een rij van west naar oost. Voorbeelddata, zoals de rest van de grond.
    """
    if not (x1 > x0 and y1 > y0):
        raise ValueError("Het gebied moet een positieve breedte en hoogte hebben.")
    if max(x1 - x0, y1 - y0) > BLOK_MAX_M:
        raise ValueError(f"Het gebied is te groot (maximaal {BLOK_MAX_M / 1000:.0f} km per zijde).")
    if not BLOK_RASTER[0] <= n <= BLOK_RASTER[1]:
        raise ValueError(
            f"Het raster moet tussen {BLOK_RASTER[0]} en {BLOK_RASTER[1]} punten zijn."
        )
    x, y = np.meshgrid(np.linspace(x0, x1, n), np.linspace(y0, y1, n))
    onder = np.cumsum(laagdikten(x, y), axis=-1)
    onder[..., -1] = DIEPTE_M
    return {
        "bron": "voorbeelddata",
        "crs": "EPSG:28992",
        "gebied": [x0, y0, x1, y1],
        "midden": georeferentie((x0 + x1) / 2, (y0 + y1) / 2),
        "n": n,
        "diepte": DIEPTE_M,
        "lagen": [{"id": laag.id, "naam": laag.naam, "kleur": laag.kleur} for laag in LAGEN],
        "onderkant": [onder[..., i].round(2).ravel().tolist() for i in range(len(LAGEN))],
    }


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
