"""Echte ondergrondse netten uit open data van netbeheerders (ArcGIS, zonder API-key).

Alleen ligging, geen diepte: de diepte is een indicatieve standaardwaarde per soort.
Open data vervangt geen KLIC-melding; die blijft verplicht vóór het graven.
"""

import json
import urllib.request
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from urllib.parse import urlencode

Ophaler = Callable[[str], dict]

STEDIN = (
    "https://services-eu1.arcgis.com/zVfwJbtoF8XqDNr0/arcgis/rest/services"
    "/Stedin_Electriciteitsnetwerk/FeatureServer"
)
LIANDER = "https://services1.arcgis.com/v6W5HAVrpgSg3vts/arcgis/rest/services"
TENNET = (
    "https://services-eu1.arcgis.com/WjozPuR5ROn6NZE8/arcgis/rest/services"
    "/TenneT_Assets_Hoogspanning/FeatureServer"
)
MAX_PER_LAAG = 2000  # grens van de diensten zelf; meer komt niet terug


@dataclass(frozen=True)
class Soort:
    id: str
    naam: str
    kleur: str
    diepte_m: float  # indicatief: open data heeft geen diepte


SOORTEN = {
    s.id: s
    for s in (
        Soort("ls", "Laagspanning", "#ffd23f", 0.6),
        Soort("ms", "Middenspanning", "#ff7a1a", 0.9),
        Soort("hs", "Hoogspanning", "#e0245e", 1.4),
        Soort("gas", "Gas", "#5bd96a", 0.8),
    )
}


@dataclass(frozen=True)
class Laag:
    beheerder: str
    soort: str
    url: str


LAGEN = (
    Laag("Stedin (peildatum 28-05-2024)", "ls", f"{STEDIN}/7"),
    Laag("Stedin (peildatum 28-05-2024)", "ms", f"{STEDIN}/8"),
    Laag("Stedin (peildatum 28-05-2024)", "hs", f"{STEDIN}/6"),
    Laag("Liander", "ls", f"{LIANDER}/Liander_Open_Data_Elektra/FeatureServer/112"),
    Laag("Liander", "ms", f"{LIANDER}/Liander_Open_Data_Elektra/FeatureServer/424"),
    Laag("Liander", "hs", f"{LIANDER}/Liander_Open_Data_Elektra/FeatureServer/632"),
    Laag("Liander", "gas", f"{LIANDER}/Liander_Open_Data_Gas/FeatureServer/0"),
    Laag("TenneT", "hs", f"{TENNET}/3"),
)


def query_adres(laag: Laag, gebied: tuple[float, float, float, float]) -> str:
    """ArcGIS-query voor alle lijnen in het gebied, in RD."""
    vraag = {
        "where": "1=1",
        "geometry": ",".join(f"{v:.0f}" for v in gebied),
        "geometryType": "esriGeometryEnvelope",
        "inSR": 28992,
        "outSR": 28992,
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "",
        "resultRecordCount": MAX_PER_LAAG,
        "f": "geojson",
    }
    return f"{laag.url}/query?{urlencode(vraag)}"


def haal_json(url: str) -> dict:
    """Haal JSON op. Gooit OSError als de dienst niet bereikbaar is."""
    verzoek = urllib.request.Request(url, headers={"User-Agent": "GR0ND"})
    with urllib.request.urlopen(verzoek, timeout=20) as antwoord:
        return json.load(antwoord)


def lijnen(geojson: dict) -> list[list[list[float]]]:
    """Alle lijnstukken uit een GeoJSON-antwoord (LineString en MultiLineString)."""
    uit = []
    for feature in geojson.get("features", []):
        geometrie = feature.get("geometry") or {}
        if geometrie.get("type") == "LineString":
            uit.append(geometrie["coordinates"])
        elif geometrie.get("type") == "MultiLineString":
            uit.extend(geometrie["coordinates"])
    return [[[round(x, 2), round(y, 2)] for x, y, *_ in lijn] for lijn in uit]


def haal_laag(laag: Laag, gebied: tuple[float, float, float, float], ophalen: Ophaler) -> dict:
    """Eén laag: de lijnen, of een foutmelding als de dienst niet antwoordt."""
    basis = {"beheerder": laag.beheerder, "soort": laag.soort}
    try:
        antwoord = ophalen(query_adres(laag, gebied))
    except (OSError, ValueError) as fout:
        return basis | {"lijnen": [], "fout": f"Niet bereikbaar: {fout}"}
    if "error" in antwoord:
        return basis | {"lijnen": [], "fout": str(antwoord["error"].get("message", "fout"))}
    return basis | {"lijnen": lijnen(antwoord)}


def haal_netten(gebied: tuple[float, float, float, float], ophalen: Ophaler = haal_json) -> dict:
    """Alle open netten in het gebied (RD), per laag, met de soorten voor kleur en diepte."""
    with ThreadPoolExecutor(len(LAGEN)) as pool:
        lagen = list(pool.map(lambda laag: haal_laag(laag, gebied, ophalen), LAGEN))
    return {
        "soorten": [vars(s) for s in SOORTEN.values()],
        "lagen": [laag for laag in lagen if laag["lijnen"] or "fout" in laag],
        "let_op": "Open data van netbeheerders, diepte indicatief. Geen vervanging van KLIC.",
    }
