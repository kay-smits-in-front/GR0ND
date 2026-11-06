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
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import numpy as np

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


@dataclass(frozen=True)
class Trace:
    """Een rechte lijn van beginpunt A naar eindpunt B in RD-meters."""

    ax: float
    ay: float
    bx: float
    by: float

    def __post_init__(self) -> None:
        self.controleer()

    @property
    def lengte(self) -> float:
        return math.hypot(self.bx - self.ax, self.by - self.ay)

    @property
    def richting(self) -> tuple[float, float]:
        lengte = self.lengte
        return (self.bx - self.ax) / lengte, (self.by - self.ay) / lengte

    @property
    def azimut(self) -> float:
        """Kompasrichting in graden (0 = noord, 90 = oost)."""
        dx, dy = self.richting
        return math.degrees(math.atan2(dx, dy)) % 360

    def controleer(self) -> None:
        """Gooi een ValueError met een Nederlandse melding als het tracé niet kan."""
        x_min, y_min, x_max, y_max = RD_BEREIK
        for x, y in ((self.ax, self.ay), (self.bx, self.by)):
            if not (x_min <= x <= x_max and y_min <= y <= y_max):
                raise ValueError("Het tracé ligt buiten het RD-bereik van Nederland.")
        if self.lengte < MIN_TRACE_M:
            raise ValueError(f"Het tracé is te kort (minimaal {MIN_TRACE_M:.0f} m).")
        if self.lengte > MAX_TRACE_M:
            raise ValueError(f"Het tracé is te lang (maximaal {MAX_TRACE_M / 1000:.0f} km).")

    def punten(self, s: float, u: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """RD-coördinaten van de punten op afstand s langs het tracé en u haaks erop."""
        dx, dy = self.richting
        return self.ax + dx * s - dy * u, self.ay + dy * s + dx * u

    def seed(self, s: float) -> int:
        """Vaste waarde per tracé en stukje van 100 m, zodat dezelfde plek er hetzelfde uitziet."""
        tekst = f"{self.ax:.0f},{self.ay:.0f},{self.bx:.0f},{self.by:.0f},{int(s // SEED_STAP_M)}"
        return int(hashlib.sha256(tekst.encode()).hexdigest()[:12], 16)


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
            "y": round(float(ym[0]), 1), "azimut": round(trace.azimut, 1),
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
