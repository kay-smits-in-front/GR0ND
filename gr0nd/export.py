"""Export van een project als KML (WGS84, lengte/breedtegraad), te openen in Google Earth en QGIS.

Alles wat we tonen heeft een geografische plek; hier schrijven we die weg: het gebied, het tracé
en de projectdata per bron, met de eigenschappen als uitgebreide data. Alleen standaardbibliotheek.
"""

import re
from xml.etree import ElementTree as ET

KML_NS = "http://www.opengis.net/kml/2.2"
Json = dict


def _el(ouder: ET.Element, naam: str, tekst: str | None = None) -> ET.Element:
    kind = ET.SubElement(ouder, naam)
    if tekst is not None:
        kind.text = tekst
    return kind


def _coordinaten(punten: list) -> str:
    return " ".join(
        f"{p[0]:.7f},{p[1]:.7f}" + (f",{p[2]:.2f}" if len(p) > 2 else "") for p in punten
    )


def _polygoon(ouder: ET.Element, ringen: list) -> None:
    polygoon = _el(ouder, "Polygon")
    for nr, ring in enumerate(ringen):
        grens = _el(polygoon, "outerBoundaryIs" if nr == 0 else "innerBoundaryIs")
        _el(_el(grens, "LinearRing"), "coordinates", _coordinaten(ring))


def kml_geometrie(ouder: ET.Element, geometrie: Json) -> None:
    """Zet één GeoJSON-geometrie om naar KML-elementen onder `ouder`."""
    soort, coord = geometrie["type"], geometrie.get("coordinates")
    if soort == "Point":
        _el(_el(ouder, "Point"), "coordinates", _coordinaten([coord]))
    elif soort == "LineString":
        _el(_el(ouder, "LineString"), "coordinates", _coordinaten(coord))
    elif soort == "Polygon":
        _polygoon(ouder, coord)
    elif soort.startswith("Multi"):
        meervoud = _el(ouder, "MultiGeometry")
        for deel in coord:
            kml_geometrie(meervoud, {"type": soort.removeprefix("Multi"), "coordinates": deel})
    elif soort == "GeometryCollection":
        meervoud = _el(ouder, "MultiGeometry")
        for deel in geometrie["geometries"]:
            kml_geometrie(meervoud, deel)


def _placemark(
    ouder: ET.Element, naam: str, geometrie: Json, eigenschappen: Json | None = None
) -> None:
    plek = _el(ouder, "Placemark")
    _el(plek, "name", naam)
    if eigenschappen:
        data = _el(plek, "ExtendedData")
        for sleutel, waarde in eigenschappen.items():
            if isinstance(waarde, str | int | float | bool):
                item = _el(data, "Data")
                item.set("name", str(sleutel))
                _el(item, "value", str(waarde))
    kml_geometrie(plek, geometrie)


def _feature_naam(eigenschappen: Json, bron: str) -> str:
    for sleutel in ("naam", "name", "NAAM", "gebiednaam", "omschrijving"):
        if eigenschappen.get(sleutel):
            return str(eigenschappen[sleutel])
    return bron


def maak_kml(
    naam: str,
    gebied: list[tuple[float, float]],
    trace: list[tuple[float, float]] | None = None,
    projectdata: Json | None = None,
) -> str:
    """KML-tekst van het project: gebied, tracé en (als al geladen) de data per bron."""
    ET.register_namespace("", KML_NS)
    wortel = ET.Element(f"{{{KML_NS}}}kml")
    document = _el(wortel, "Document")
    _el(document, "name", naam)
    _el(document, "description", "Export uit GR0ND. WGS84. Grond en bovengrond zijn voorbeelddata.")
    kaart = _el(document, "Folder")
    _el(kaart, "name", "Gebied")
    _placemark(kaart, f"Gebied {naam}", {"type": "Polygon", "coordinates": [[*gebied, gebied[0]]]})
    if trace:
        map_trace = _el(document, "Folder")
        _el(map_trace, "name", "Tracé")
        _placemark(map_trace, f"Tracé {naam}", {"type": "LineString", "coordinates": trace})
    for bron_id, features in _per_bron(projectdata or {}).items():
        map_bron = _el(document, "Folder")
        _el(map_bron, "name", bron_id)
        for feature in features:
            eig = feature.get("properties") or {}
            _placemark(map_bron, _feature_naam(eig, bron_id), feature["geometry"], eig)
    ET.indent(wortel)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(wortel, encoding="unicode")


def _per_bron(projectdata: Json) -> dict[str, list[Json]]:
    resultaat: dict[str, list[Json]] = {}
    for feature in projectdata.get("features", []):
        resultaat.setdefault(feature["properties"].get("bron", "overig"), []).append(feature)
    return resultaat


def bestandsnaam(naam: str) -> str:
    """Veilige bestandsnaam voor een projectnaam."""
    schoon = re.sub(r"[^A-Za-z0-9._-]+", "-", naam).strip("-") or "project"
    return f"gr0nd-{schoon}.kml"
