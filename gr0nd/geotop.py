"""GeoTOP (TNO / BRO): de echte grondsoort per voxel van 100 × 100 × 0,5 m.

Uitsneden komen van de OPeNDAP-server van TNO. Coördinaten zijn voxelmiddens in RD (x, y) en
NAP (z). Een voxel zonder grond (lucht, buiten het model) heeft waarde GEEN_DATA.
Bron: https://www.dinoloket.nl, documentatie lithoklassen: TNO 2012 R10991.
"""

import urllib.request
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

OPENDAP = "https://www.dinodata.nl/opendap/GeoTOP/geotop.nc"
X0, Y0, Z0 = 13_600.0, 338_500.0, -50.0  # middelpunt van de eerste voxel (RD, NAP)
STAP_XY, STAP_Z = 100.0, 0.5
AANTAL_X, AANTAL_Y, AANTAL_Z = 2646, 2811, 313
GEEN_DATA = -127
MAX_VOXELS = 2_000_000  # grens per verzoek: de ASCII-uitvoer is ongeveer 5 bytes per voxel


@dataclass(frozen=True)
class Lithoklasse:
    code: int
    naam: str
    kleur: str


LITHOKLASSEN = (
    Lithoklasse(0, "Antropogeen", "#8c8c8c"),
    Lithoklasse(1, "Veen", "#6b4a2b"),
    Lithoklasse(2, "Klei", "#3f7f4f"),
    Lithoklasse(3, "Kleiig zand, zandige klei, leem", "#9bb36b"),
    Lithoklasse(5, "Fijn zand", "#f2dc82"),
    Lithoklasse(6, "Midden zand", "#e6c255"),
    Lithoklasse(7, "Grof zand", "#d4a437"),
    Lithoklasse(8, "Grind", "#b57d3a"),
    Lithoklasse(9, "Schelpen", "#d9d2c3"),
)

Ophaler = Callable[[str], str]


@dataclass(frozen=True)
class Uitsnede:
    """Lithoklasse per voxel, as-volgorde [x][y][z], met de middens per as."""

    x: np.ndarray
    y: np.ndarray
    z: np.ndarray
    lithok: np.ndarray


def index_bereik(begin: float, eind: float, oorsprong: float, stap: float, aantal: int) -> range:
    """De voxelindexen waarvan het midden tussen begin en eind ligt (grenzen inbegrepen)."""
    eerste = max(0, int(np.ceil((begin - oorsprong) / stap - 1e-9)))
    laatste = min(aantal - 1, int(np.floor((eind - oorsprong) / stap + 1e-9)))
    if laatste < eerste:
        raise ValueError("Het gebied valt buiten GeoTOP.")
    return range(eerste, laatste + 1)


def opendap_adres(ix: range, iy: range, iz: range) -> str:
    """URL voor de lithoklasse binnen de indexbereiken, als ASCII."""
    deel = "".join(f"%5B{r.start}:1:{r.stop - 1}%5D" for r in (ix, iy, iz))
    return f"{OPENDAP}.ascii?lithok{deel}"


def lees_ascii(tekst: str, vorm: tuple[int, int, int]) -> np.ndarray:
    """Zet de OPeNDAP-ASCII van één grid om naar een array met de gegeven vorm."""
    rijen = [regel for regel in tekst.splitlines() if regel.startswith("lithok.lithok[")]
    waarden = [int(v) for regel in rijen for v in regel.split(",")[1:]]
    if len(waarden) != vorm[0] * vorm[1] * vorm[2]:
        raise ValueError("Onverwacht antwoord van GeoTOP.")
    return np.array(waarden, dtype=np.int16).reshape(vorm)


def haal_tekst(url: str) -> str:
    """Haal tekst op. Gooit OSError als de dienst niet bereikbaar is."""
    verzoek = urllib.request.Request(url, headers={"User-Agent": "GR0ND"})
    with urllib.request.urlopen(verzoek, timeout=60) as antwoord:
        return antwoord.read().decode()


def haal_uitsnede(
    gebied: tuple[float, float, float, float],
    nap: tuple[float, float],
    ophalen: Ophaler = haal_tekst,
) -> Uitsnede:
    """Lithoklassen binnen gebied (x0, y0, x1, y1 in RD) en nap (z_onder, z_boven in m NAP)."""
    x0, y0, x1, y1 = gebied
    ix = index_bereik(x0, x1, X0, STAP_XY, AANTAL_X)
    iy = index_bereik(y0, y1, Y0, STAP_XY, AANTAL_Y)
    iz = index_bereik(nap[0], nap[1], Z0, STAP_Z, AANTAL_Z)
    vorm = (len(ix), len(iy), len(iz))
    if vorm[0] * vorm[1] * vorm[2] > MAX_VOXELS:
        raise ValueError("De uitsnede is te groot; kies een kleiner gebied of minder diepte.")
    lithok = lees_ascii(ophalen(opendap_adres(ix, iy, iz)), vorm)
    return Uitsnede(
        x=X0 + STAP_XY * np.array(ix),
        y=Y0 + STAP_XY * np.array(iy),
        z=Z0 + STAP_Z * np.array(iz),
        lithok=lithok,
    )
