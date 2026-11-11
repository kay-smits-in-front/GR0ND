"""3D-wereld van een projectgebied: maaiveld (AHN), gebouwen (3D BAG), bomen (BGT), grond (GeoTOP).

Alles in RD en NAP (meters), open data zonder API-key. De luchtfoto haalt de browser zelf bij PDOK.
"""

import json
import struct
import urllib.request
import zlib
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlencode

import numpy as np

from gr0nd import geotop

Punt = tuple[float, float]
Gebied = tuple[float, float, float, float]
Ophaler = Callable[[str], bytes]

MAX_ZIJDE_M = 3500.0
MAAIVELD_RASTER = 384  # punten per zijde van het hoogteraster (3 km: ca. 8 m, 1 km: ca. 2,6 m)
RAND_STAP_M = 5.0  # afstand tussen de grondkolommen langs de projectgrens
GROND_DIEPTE_M = 25.0
AHN = "https://service.pdok.nl/rws/ahn/wcs/v1_0"
BAG3D = "https://data.3dbag.nl/api/BAG3D/wfs"
BGT = "https://api.pdok.nl/lv/bgt/ogc/v1/collections"
RD_CRS = "http://www.opengis.net/def/crs/EPSG/0/28992"


def haal(url: str) -> bytes:
    """Haal bytes op. Gooit OSError als de dienst niet bereikbaar is."""
    verzoek = urllib.request.Request(url, headers={"User-Agent": "GR0ND"})
    with urllib.request.urlopen(verzoek, timeout=60) as antwoord:
        return antwoord.read()


def omhullende(ring: list[Punt]) -> Gebied:
    xs, ys = zip(*ring, strict=True)
    return min(xs), min(ys), max(xs), max(ys)


def binnen(x: np.ndarray, y: np.ndarray, ring: list[Punt]) -> np.ndarray:
    """Ligt elk punt binnen de ring? (even-oneven-regel, werkt ook voor arrays)."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    uit = np.zeros(x.shape, bool)
    for (x0, y0), (x1, y1) in zip(ring, ring[1:] + ring[:1], strict=True):
        kruist = (y0 > y) != (y1 > y)
        xs = x0 + (y - y0) * (x1 - x0) / ((y1 - y0) or 1e-12)
        uit ^= kruist & (x < xs)
    return uit


# ---------- maaiveld (AHN) ----------


def tiff_tags(data: bytes) -> dict[int, tuple[int, ...]]:
    """De tags van de eerste afbeelding in een little-endian TIFF (alleen SHORT, LONG en ASCII)."""
    if data[:2] != b"II":
        raise ValueError("Alleen little-endian TIFF wordt ondersteund.")
    begin = struct.unpack("<I", data[4:8])[0]
    aantal = struct.unpack("<H", data[begin : begin + 2])[0]
    tags = {}
    for i in range(aantal):
        tag, soort, n, waarde = struct.unpack(
            "<HHII", data[begin + 2 + 12 * i : begin + 14 + 12 * i]
        )
        grootte = {2: 1, 3: 2, 4: 4}.get(soort)
        if grootte is None:
            continue
        if n * grootte <= 4:
            ruw = struct.pack("<I", waarde)[: n * grootte]
        else:
            ruw = data[waarde : waarde + n * grootte]
        tags[tag] = (ruw,) if soort == 2 else struct.unpack("<" + "_HI"[soort - 2] * n, ruw)
    return tags


def lees_hoogtes(data: bytes) -> np.ndarray:
    """Float32-raster uit de AHN-GeoTIFF (deflate, met of zonder float-predictor). Leeg is NaN."""
    tags = tiff_tags(data)
    breedte, hoogte = tags[256][0], tags[257][0]
    compressie, predictor = tags.get(259, (1,))[0], tags.get(317, (1,))[0]
    if tags[258][0] != 32 or tags.get(339, (3,))[0] != 3 or compressie not in (1, 8):
        raise ValueError("Onverwacht AHN-formaat.")
    rijen = []
    for begin, lengte in zip(tags[273], tags[279], strict=True):
        ruw = data[begin : begin + lengte]
        ruw = zlib.decompress(ruw) if compressie == 8 else ruw
        bytes_ = np.frombuffer(ruw, np.uint8).reshape(-1, breedte * 4)
        if (
            predictor == 3
        ):  # per rij bytes opgeteld en per byte-vlak gegroepeerd (meest significant eerst)
            bytes_ = np.cumsum(bytes_, axis=1, dtype=np.uint8).reshape(-1, 4, breedte)
            bytes_ = np.ascontiguousarray(bytes_.transpose(0, 2, 1)[:, :, ::-1])
        rijen.append(bytes_.view("<f4").reshape(-1, breedte))
    raster = np.vstack(rijen)[:hoogte].astype(float)
    raster[(raster > 1e30) | (raster < -1e3)] = np.nan
    return raster


def vul_gaten(raster: np.ndarray) -> np.ndarray:
    """Vul lege cellen (gebouwen, water) lineair per rij en daarna per kolom aan."""
    uit = raster.copy()
    for as_ in (1, 0):
        uit = np.apply_along_axis(_vul_rij, as_, uit)
    return np.nan_to_num(uit, nan=float(np.nanmedian(raster)) if np.isfinite(raster).any() else 0.0)


def _vul_rij(rij: np.ndarray) -> np.ndarray:
    goed = np.isfinite(rij)
    if goed.sum() < 2:
        return rij
    i = np.arange(rij.size)
    return np.interp(i, i[goed], rij[goed])


def maaiveld(gebied: Gebied, ophalen: Ophaler = haal) -> np.ndarray:
    """NAP-hoogte op een raster van MAAIVELD_RASTER × MAAIVELD_RASTER, rij 0 is het zuiden."""
    x0, y0, x1, y1 = gebied
    n = MAAIVELD_RASTER
    vraag = (
        f"service=WCS&version=2.0.1&request=GetCoverage&CoverageId=dtm_05m&format=image/tiff"
        f"&subset=x({x0:.1f},{x1:.1f})&subset=y({y0:.1f},{y1:.1f})&scaleSize=x({n}),y({n})"
    )
    return vul_gaten(lees_hoogtes(ophalen(f"{AHN}?{vraag}")))[::-1]


def hoogte_op(raster: np.ndarray, gebied: Gebied, x: float, y: float) -> float:
    """NAP-hoogte op (x, y), dichtstbijzijnde rastercel."""
    x0, y0, x1, y1 = gebied
    n = raster.shape[0]
    i = int(np.clip(round((y - y0) / (y1 - y0) * (n - 1)), 0, n - 1))
    j = int(np.clip(round((x - x0) / (x1 - x0) * (n - 1)), 0, n - 1))
    return float(raster[i, j])


# ---------- gebouwen (3D BAG) en bomen (BGT) ----------


def gebouwen(gebied: Gebied, ring: list[Punt], ophalen: Ophaler = haal) -> list[dict]:
    """Panden met het midden binnen de ring: omtrek, maaiveld- en dakhoogte (NAP) en daktype."""
    vraag = urlencode({
        "service": "WFS", "version": "2.0.0", "request": "GetFeature", "typeNames": "BAG3D:lod12",
        "bbox": ",".join(f"{v:.1f}" for v in gebied) + ",EPSG:28992",
        "outputFormat": "application/json", "count": 50_000,
        "propertyName": "b3_h_70p,b3_h_maaiveld,b3_dak_type,geom",
    })  # fmt: skip
    uit = []
    for f in json.loads(ophalen(f"{BAG3D}?{vraag}"))["features"]:
        p, geometrie = f["properties"], f.get("geometry") or {}
        if geometrie.get("type") != "Polygon" or p.get("b3_h_70p") is None:
            continue
        rand = [[round(x, 2), round(y, 2)] for x, y, *_ in geometrie["coordinates"][0][:-1]]
        mx, my = np.mean(rand, axis=0)
        if not binnen(mx, my, ring):
            continue
        uit.append({
            "rand": rand, "dak": round(p["b3_h_70p"], 2),
            "voet": round(p.get("b3_h_maaiveld") or p["b3_h_70p"] - 3, 2),
            "schuin": p.get("b3_dak_type") == "slanted",
        })  # fmt: skip
    return uit


BOOM_TEGEL_M = (
    400.0  # de BGT geeft max 1000 per pagina; tegels tegelijk ophalen is veel sneller dan bladeren
)


def bomen_in_tegel(tegel: Gebied, ophalen: Ophaler) -> list[list[float]]:
    """Losse bomen uit de BGT in één tegel, bladerend tot alles binnen is."""
    vraag = urlencode({
        "bbox": ",".join(f"{v:.1f}" for v in tegel), "bbox-crs": RD_CRS, "crs": RD_CRS,
        "limit": 1000, "f": "json",
    })  # fmt: skip
    url, punten = f"{BGT}/vegetatieobject_punt/items?{vraag}", []
    while url:
        antwoord = json.loads(ophalen(url))
        for f in antwoord.get("features", []):
            p = f["properties"]
            actueel = not p.get("eind_registratie")  # de BGT geeft ook oude versies terug
            if actueel and p.get("plus_type") in ("boom", None) and f.get("geometry"):
                punten.append(f["geometry"]["coordinates"][:2])
        url = next((ln["href"] for ln in antwoord.get("links", []) if ln["rel"] == "next"), None)
    return punten


def tegels(gebied: Gebied, maat: float) -> list[Gebied]:
    """Het gebied opgedeeld in vierkanten van ten hoogste `maat` meter."""
    x0, y0, x1, y1 = gebied
    xs = np.linspace(x0, x1, max(1, int(np.ceil((x1 - x0) / maat))) + 1)
    ys = np.linspace(y0, y1, max(1, int(np.ceil((y1 - y0) / maat))) + 1)
    return [
        (a, b, c, d)
        for a, c in zip(xs, xs[1:], strict=False)
        for b, d in zip(ys, ys[1:], strict=False)
    ]


def bomen(gebied: Gebied, ring: list[Punt], ophalen: Ophaler = haal) -> list[list[float]]:
    """Losse bomen uit de BGT binnen de ring, als [x, y]. Niet elke gemeente vult dit in."""
    with ThreadPoolExecutor(12) as pool:
        delen = pool.map(lambda t: bomen_in_tegel(t, ophalen), tegels(gebied, BOOM_TEGEL_M))
        punten = [p for deel in delen for p in deel]
    if not punten:
        return []
    xy = np.unique(np.array(punten), axis=0)  # een boom op een tegelrand komt twee keer terug
    return xy[binnen(xy[:, 0], xy[:, 1], ring)].round(1).tolist()


# ---------- grond langs de projectgrens (GeoTOP) ----------


def randpunten(ring: list[Punt], stap: float = RAND_STAP_M) -> list[Punt]:
    """Punten om de stap langs de gesloten ring, inclusief elk hoekpunt."""
    uit = []
    for (x0, y0), (x1, y1) in zip(ring, ring[1:] + ring[:1], strict=True):
        n = max(1, int(np.ceil(np.hypot(x1 - x0, y1 - y0) / stap)))
        uit += [(x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * i / n) for i in range(n)]
    return uit + uit[:1]


def grondrand(
    ring: list[Punt], gebied: Gebied, raster: np.ndarray, ophalen: Callable[[str], str]
) -> list[dict]:
    """Per randpunt: plek, maaiveld (AHN) en lithoklassen per 0,5 m naar beneden (GeoTOP)."""
    half = geotop.STAP_XY
    x0, y0, x1, y1 = gebied
    onder = float(np.nanmin(raster)) - GROND_DIEPTE_M
    boven = float(np.nanmax(raster)) + 1.0
    uitsnede = geotop.haal_uitsnede(
        (x0 - half, y0 - half, x1 + half, y1 + half), (onder, boven), ophalen
    )
    lagen = int(GROND_DIEPTE_M / geotop.STAP_Z)
    uit = []
    for x, y in randpunten(ring):
        i = int(np.abs(uitsnede.x - x).argmin())
        j = int(np.abs(uitsnede.y - y).argmin())
        hoogte = hoogte_op(raster, gebied, x, y)
        k = int(np.clip(np.searchsorted(uitsnede.z, hoogte) - 1, 0, uitsnede.z.size - 1))
        kolom = uitsnede.lithok[i, j, max(0, k - lagen + 1) : k + 1][::-1]
        uit.append({"x": round(x, 2), "y": round(y, 2), "maaiveld": round(hoogte, 2),
                    "lithok": kolom.tolist()})  # fmt: skip
    return uit


# ---------- alles samen ----------


def wereld(ring: list[Punt]) -> dict:
    """Alle data voor de 3D-wereld van het gebied binnen de ring (RD)."""
    if len(ring) < 3:
        raise ValueError("Het gebied heeft minstens 3 punten nodig.")
    gebied = omhullende(ring)
    if max(gebied[2] - gebied[0], gebied[3] - gebied[1]) > MAX_ZIJDE_M:
        raise ValueError(
            f"Het gebied is te groot (maximaal {MAX_ZIJDE_M / 1000:.1f} km per zijde)."
        )
    with ThreadPoolExecutor(3) as pool:
        raster_taak = pool.submit(maaiveld, gebied)
        gebouwen_taak = pool.submit(gebouwen, gebied, ring)
        bomen_taak = pool.submit(bomen, gebied, ring)
        raster = raster_taak.result()
        rand = grondrand(ring, gebied, raster, geotop.haal_tekst)
        panden, boompunten = gebouwen_taak.result(), bomen_taak.result()
    return {
        "ring": [list(p) for p in ring],
        "gebied": list(gebied),
        "referentie_nap": round(float(np.median(raster)), 2),
        "maaiveld": {"n": raster.shape[0], "hoogtes": raster.round(2).ravel().tolist()},
        "gebouwen": panden,
        "bomen": boompunten,
        "rand": rand,
        "stap_z": geotop.STAP_Z,
        "klassen": [
            {"code": k.code, "naam": k.naam, "kleur": k.kleur} for k in geotop.LITHOKLASSEN
        ],
        "bronnen": "AHN (maaiveld), 3D BAG (gebouwen), BGT (bomen), GeoTOP (grond), PDOK luchtfoto",
    }
