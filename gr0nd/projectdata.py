"""Projectdata: haalt per projectgebied de relevante open data op (natuur, erfgoed, grondwater).

Alles wordt opgehaald voor de omhullende van het getekende gebied, nooit voor heel Nederland.
Het resultaat zijn GeoJSON-features in WGS84 (lon, lat) met bron en categorie als eigenschap,
zodat ze rechtstreeks naar KML te exporteren zijn.
"""

import json
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import urlencode

from pyproj import Transformer

from gr0nd.kaart import haal_json

MAX_FEATURES = 2000  # per bron; meer is niet nodig voor één projectgebied
PARALLEL = 8  # gelijktijdige verzoeken (het wachten op het netwerk is de bottleneck)

Json = dict
Ophaler = Callable[[str], Json]


@dataclass(frozen=True)
class Bron:
    id: str
    naam: str
    categorie: str  # natuur, erfgoed of grondwater
    soort: str  # "wfs" of "ogc_api"
    url: str
    laag: str = ""  # alleen WFS: de typename


BRONNEN = (
    Bron("natura2000", "Natura 2000", "natuur", "wfs",
         "https://service.pdok.nl/rvo/natura2000/wfs/v1_0", "natura2000:natura2000"),
    Bron("cultuurhistorie", "Beschermde gebieden cultuurhistorie", "erfgoed", "ogc_api",
         "https://api.pdok.nl/rce/beschermde-gebieden-cultuurhistorie/ogc/v1"),
    Bron("grondwatermonitoring", "BRO grondwatermonitoring", "grondwater", "ogc_api",
         "https://api.pdok.nl/tno/bro-grondwatermonitoring-in-samenhang-karakteristieken/ogc/v1"),
)  # fmt: skip

NOG_TE_KOPPELEN = (
    "BRO bodemonderzoek (booronderzoek, sonderingen, milieuhygiënisch)",
    "Natuurnetwerk Nederland (NNN)",
    "Bodemverontreiniging (SLD)",
    "Explosieven (gemeentelijke bommenkaarten)",
    "Eerdere projecten en vergunningen",
)

AANDACHTSPUNTEN = (
    {
        "titel": "Broedseizoen",
        "tekst": "Werk met bomen, struiken of riet: vermijd globaal 15 maart tot 15 juli.",
        "categorie": "natuur",
    },
    {
        "titel": "Vleermuizen en winterslaap",
        "tekst": "Gebouwen, bomen en kelders: een ecologische quickscan kan nodig zijn.",
        "categorie": "natuur",
    },
    {
        "titel": "Explosieven",
        "tekst": "Geen landelijke open kaart. Een vooronderzoek NGE (CS-NGE) kan nodig zijn.",
        "categorie": "explosieven",
    },
    {
        "titel": "KLIC",
        "tekst": "Altijd een graafmelding (KLIC) vóór het graven; de levering is beperkt geldig.",
        "categorie": "kabels",
    },
)


def bbox_van_gebied(ring: list[tuple[float, float]]) -> tuple[float, float, float, float]:
    """Omhullende (min_lon, min_lat, max_lon, max_lat) van het gebied."""
    lons, lats = zip(*ring, strict=False)
    return min(lons), min(lats), max(lons), max(lats)


@lru_cache(maxsize=1)
def rd_naar_ll() -> Transformer:
    return Transformer.from_crs("EPSG:28992", "EPSG:4326", always_xy=True)


def bbox_rd(bbox: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    """Dezelfde omhullende in RD-meters (voor WFS in de standaard coördinaten)."""
    naar_rd = Transformer.from_crs("EPSG:4326", "EPSG:28992", always_xy=True)
    x0, y0 = naar_rd.transform(bbox[0], bbox[1])
    x1, y1 = naar_rd.transform(bbox[2], bbox[3])
    return x0, y0, x1, y1


def wfs_adres(bron: Bron, bbox: tuple[float, float, float, float]) -> str:
    x0, y0, x1, y1 = bbox_rd(bbox)
    vraag = urlencode(
        {
            "service": "WFS",
            "version": "2.0.0",
            "request": "GetFeature",
            "typeNames": bron.laag,
            "outputFormat": "application/json",
            "count": MAX_FEATURES,
            "bbox": f"{x0:.1f},{y0:.1f},{x1:.1f},{y1:.1f},urn:ogc:def:crs:EPSG::28992",
        }
    )
    return f"{bron.url}?{vraag}"


def ogc_adres(bron: Bron, collectie: str, bbox: tuple[float, float, float, float]) -> str:
    vraag = urlencode(
        {"bbox": ",".join(f"{c:.6f}" for c in bbox), "limit": MAX_FEATURES, "f": "json"}
    )
    return f"{bron.url}/collections/{collectie}/items?{vraag}"


def collecties(bron: Bron, ophalen: Ophaler) -> list[str]:
    """De ids van alle collecties van een OGC API."""
    return [c["id"] for c in ophalen(f"{bron.url}/collections?f=json")["collections"]]


def zet_rd_om(geometrie: Json) -> Json:
    """Zet de coördinaten van een geometrie van RD naar lon/lat."""

    def punt(c: list[float]) -> list[float]:
        lon, lat = rd_naar_ll().transform(c[0], c[1])
        return [round(lon, 7), round(lat, 7)]

    def recursief(delen):
        if delen and isinstance(delen[0], int | float):
            return punt(delen)
        return [recursief(d) for d in delen]

    return {**geometrie, "coordinates": recursief(geometrie["coordinates"])}


def maak_feature(bron: Bron, ruw: Json, in_rd: bool) -> Json:
    geometrie = ruw.get("geometry")
    if geometrie is None:
        return {}
    eigenschappen = {k: v for k, v in (ruw.get("properties") or {}).items() if v is not None}
    return {
        "type": "Feature",
        "geometry": zet_rd_om(geometrie) if in_rd else geometrie,
        "properties": {**eigenschappen, "bron": bron.id, "categorie": bron.categorie},
    }


def features_van_bron(
    bron: Bron, bbox: tuple[float, float, float, float], ophalen: Ophaler
) -> list[Json]:
    """Alle features van één bron binnen de omhullende, als WGS84-features."""
    if bron.soort == "wfs":
        ruw = ophalen(wfs_adres(bron, bbox))["features"]
        resultaat = [maak_feature(bron, f, in_rd=True) for f in ruw]
    else:
        resultaat = [
            maak_feature(bron, f, in_rd=False)
            for collectie in collecties(bron, ophalen)
            for f in ophalen(ogc_adres(bron, collectie, bbox))["features"]
        ]
    return [f for f in resultaat if f]


def haal_bron(bron: Bron, bbox: tuple[float, float, float, float], ophalen: Ophaler) -> Json:
    """Ophalen van één bron; een fout bij één bron stopt de andere niet."""
    basis = {"id": bron.id, "naam": bron.naam, "categorie": bron.categorie}
    try:
        features = features_van_bron(bron, bbox, ophalen)
    except (OSError, ValueError, KeyError) as fout:
        return {**basis, "status": "fout", "aantal": 0, "fout": str(fout)[:200], "features": []}
    status = "ok" if features else "leeg"
    return {**basis, "status": status, "aantal": len(features), "features": features}


def haal_projectdata(
    gebied: list[tuple[float, float]],
    ophalen: Ophaler = haal_json,
    bronnen: tuple[Bron, ...] = BRONNEN,
) -> Json:
    """Haal alle bronnen parallel op voor het gebied."""
    bbox = bbox_van_gebied(gebied)
    with ThreadPoolExecutor(max_workers=PARALLEL) as pool:
        resultaten = list(pool.map(lambda b: haal_bron(b, bbox, ophalen), bronnen))
    return {
        "bbox": bbox,
        "bronnen": [{k: v for k, v in r.items() if k != "features"} for r in resultaten],
        "features": [f for r in resultaten for f in r["features"]],
        "aandachtspunten": list(AANDACHTSPUNTEN),
        "nog_te_koppelen": list(NOG_TE_KOPPELEN),
    }


def naar_json(data: Json) -> str:
    return json.dumps(data, ensure_ascii=False)
