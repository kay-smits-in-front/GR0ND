"""Kaartmodel van GR0ND: tracé, grondlagen en het 0-zicht (dwarsprofiel).

LET OP: de grondlagen, zones en bovengrond hieronder zijn VOORBEELDDATA. De zones zijn grove
rechthoeken in RD-coördinaten en vervangen de BRO/GeoTOP-modellen nog niet. De app laat dat in
beeld zien. Alle afmetingen zijn in meters. In het 0-zicht is u de afstand haaks op het tracé
(positief links van de looprichting) en is diepte positief naar beneden vanaf het maaiveld.
"""

import hashlib
import json
import math
import random
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
MIN_TRACE_M = 20.0
MAX_TRACE_M = 50_000.0
RD_BEREIK = (-7000.0, 289000.0, 300000.0, 629000.0)  # x_min, y_min, x_max, y_max (EPSG:28992)
VENSTER_U_M = 30.0  # het 0-zicht toont u van -30 tot +30 m
U_STAP_M = 1.0
ZONEKAART_CEL_M = 2500.0
SEED_STAP_M = 100.0  # de voorbeeldbovengrond verandert elke 100 m langs het tracé


@dataclass(frozen=True)
class LaagType:
    id: str
    naam: str
    kleur: str  # basiskleur aan het oppervlak; de weergave verdonkert met de diepte


LAGEN = (
    LaagType("toplaag", "Humeuze toplaag (bouwvoor)", "#4a3626"),
    LaagType("loess", "Löss", "#c9a972"),
    LaagType("klei", "Klei", "#8a7d68"),
    LaagType("veen", "Veen", "#3b2a1c"),
    LaagType("siltige_klei", "Siltige klei", "#7d8478"),
    LaagType("fijn_zand", "Fijn zand (dekzand)", "#d9c48a"),
    LaagType("keileem", "Keileem", "#8f7f6b"),
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


MAX_KNIKPUNTEN = 200
MIN_STUK_M = 1.0


@dataclass(frozen=True)
class Trace:
    """Een tracé van beginpunt tot eindpunt via knikpunten, in RD-meters."""

    knikpunten: tuple[tuple[float, float], ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "knikpunten", tuple((float(x), float(y)) for x, y in self.knikpunten)
        )
        self.controleer()

    @classmethod
    def recht(cls, ax: float, ay: float, bx: float, by: float) -> "Trace":
        return cls(((ax, ay), (bx, by)))

    @property
    def stukken(self) -> list[tuple[float, float, float, float, float]]:
        """Per stuk tussen twee knikpunten: x, y van het begin, richting dx, dy en lengte."""
        stukken = []
        for (x0, y0), (x1, y1) in zip(self.knikpunten, self.knikpunten[1:], strict=False):
            lengte = math.hypot(x1 - x0, y1 - y0)
            stukken.append((x0, y0, (x1 - x0) / lengte, (y1 - y0) / lengte, lengte))
        return stukken

    @property
    def lengte(self) -> float:
        return sum(stuk[4] for stuk in self.stukken)

    def plek(self, s: float) -> tuple[float, float, float, float]:
        """x, y en richting (dx, dy) op afstand s langs het tracé."""
        rest = min(max(s, 0.0), self.lengte)
        stukken = self.stukken
        for x0, y0, dx, dy, lengte in stukken[:-1]:
            if rest <= lengte:
                return x0 + dx * rest, y0 + dy * rest, dx, dy
            rest -= lengte
        x0, y0, dx, dy, _ = stukken[-1]
        return x0 + dx * rest, y0 + dy * rest, dx, dy

    @property
    def afstanden(self) -> list[float]:
        """Afstand langs het tracé van elk knikpunt, beginnend bij 0."""
        totaal = [0.0]
        for stuk in self.stukken:
            totaal.append(totaal[-1] + stuk[4])
        return totaal

    def azimut(self, s: float = 0.0) -> float:
        """Kompasrichting in graden (0 = noord, 90 = oost) op afstand s."""
        _, _, dx, dy = self.plek(s)
        return math.degrees(math.atan2(dx, dy)) % 360

    def controleer(self) -> None:
        """Gooi een ValueError met een Nederlandse melding als het tracé niet kan."""
        if len(self.knikpunten) < 2:
            raise ValueError("Een tracé heeft minstens een begin- en een eindpunt.")
        if len(self.knikpunten) > MAX_KNIKPUNTEN:
            raise ValueError(f"Een tracé mag maximaal {MAX_KNIKPUNTEN} punten hebben.")
        x_min, y_min, x_max, y_max = RD_BEREIK
        for x, y in self.knikpunten:
            if not (x_min <= x <= x_max and y_min <= y <= y_max):
                raise ValueError("Het tracé ligt buiten het RD-bereik van Nederland.")
        for (x0, y0), (x1, y1) in zip(self.knikpunten, self.knikpunten[1:], strict=False):
            if math.hypot(x1 - x0, y1 - y0) < MIN_STUK_M:
                raise ValueError("Twee opeenvolgende punten liggen op dezelfde plek.")
        if self.lengte < MIN_TRACE_M:
            raise ValueError(f"Het tracé is te kort (minimaal {MIN_TRACE_M:.0f} m).")
        if self.lengte > MAX_TRACE_M:
            raise ValueError(f"Het tracé is te lang (maximaal {MAX_TRACE_M / 1000:.0f} km).")

    def punten(self, s: float, u: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """RD-coördinaten van de punten op afstand s langs het tracé en u haaks erop."""
        x, y, dx, dy = self.plek(s)
        return x - dy * u, y + dx * u

    def seed(self, s: float) -> int:
        """Vaste waarde per tracé en stukje van 100 m, zodat dezelfde plek er hetzelfde uitziet."""
        punten = ";".join(f"{x:.0f},{y:.0f}" for x, y in self.knikpunten)
        return int(
            hashlib.sha256(f"{punten},{int(s // SEED_STAP_M)}".encode()).hexdigest()[:12], 16
        )


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


def voorbeeld_bovengrond(seed: int) -> dict:
    """Voorbeeld-dwarsprofiel: huis, sloot, weg op een berm en een lantaarnpaal.

    Alle waarden zijn u-posities en afmetingen in meters. Geen echte data.
    """
    rng = random.Random(seed)
    verschuiving = round(rng.uniform(-2.0, 2.0), 1)
    berm = round(rng.uniform(0.4, 0.8), 2)
    sloot_diepte = round(rng.uniform(0.9, 1.4), 2)
    teen_links = round(3.0 + verschuiving, 2)
    kruin_begin = round(teen_links + berm * 3, 2)
    kruin_eind = round(kruin_begin + 7.0, 2)
    huis_begin = round(-22.0 + verschuiving, 2)
    huis_eind = round(huis_begin + 9.0, 2)
    sloot_links = round(-3.0 + verschuiving - 2.0, 2)
    return {
        "huis": {
            "u0": huis_begin, "u1": round(huis_begin + 9.0, 2), "goot": 5.5, "nok": 9.5,
            "fundering_diepte": 0.8, "fundering_breedte": 0.5,
        },
        "sloot": {
            "u_midden": round(-3.0 + verschuiving, 2), "breedte_boven": 4.0,
            "breedte_bodem": 1.5, "diepte": sloot_diepte, "waterpeil": 0.4,
        },
        "weg": {
            "teen_l": teen_links, "kruin0": kruin_begin, "kruin1": kruin_eind,
            "teen_r": round(kruin_eind + berm * 3, 2), "hoogte": berm, "asfalt": 0.2,
        },
        "lantaarn": {"u": round(kruin_eind - 0.8, 2), "hoogte": 5.0},
        # Perceelgrens: links is privéterrein (kavel van het huis), rechts openbaar.
        "perceel": {"grens": round((huis_eind + sloot_links) / 2, 2)},
    }  # fmt: skip


def dwarsprofiel(trace: Trace, s: float) -> dict:
    """Het 0-zicht op afstand s langs het tracé: grondlagen plus voorbeeldbovengrond."""
    if not 0 <= s <= trace.lengte:
        raise ValueError("De positie ligt buiten het tracé.")
    us = np.arange(-VENSTER_U_M, VENSTER_U_M + 1e-9, U_STAP_M)
    x, y = trace.punten(s, us)
    onder = np.cumsum(laagdikten(x, y), axis=-1)
    onder[..., -1] = DIEPTE_M
    aantal = np.bincount(zone_index(x, y), minlength=len(ZONES))
    zone = ZONES[int(aantal.argmax())]
    xm, ym = trace.punten(s, np.array([0.0]))
    return {
        "bron": "voorbeelddata",
        "trace": {
            "lengte": round(trace.lengte, 1), "s": s, "x": round(float(xm[0]), 1),
            "y": round(float(ym[0]), 1), "azimut": round(trace.azimut(s), 1),
            "knikken": [round(afstand, 1) for afstand in trace.afstanden[1:-1]],
        },
        "zone": zone.naam,
        "grondwater": zone.grondwater_m,
        "venster": {"u_min": -VENSTER_U_M, "u_max": VENSTER_U_M, "stap": U_STAP_M,
                    "diepte": DIEPTE_M},
        "lagen": [
            {"id": laag.id, "naam": laag.naam, "kleur": laag.kleur,
             "onderkant": onder[:, i].round(2).tolist()}
            for i, laag in enumerate(LAGEN)
        ],
        "bovengrond": voorbeeld_bovengrond(trace.seed(s)),
    }  # fmt: skip


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
    tegels: str  # tegel-URL voor MapLibre; pdok:// betekent: tegelmatrix met nul opvullen
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
    return f"https://{PDOK}{pad}?{vraag}"


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
