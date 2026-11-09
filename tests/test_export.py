from xml.etree import ElementTree as ET

from fastapi.testclient import TestClient

from gr0nd.app import Settings, maak_app
from gr0nd.export import bestandsnaam, maak_kml

NS = {"k": "http://www.opengis.net/kml/2.2"}
GEBIED = [(4.88, 52.36), (4.93, 52.36), (4.93, 52.39)]
RING = [[4.9, 52.37], [4.91, 52.37], [4.91, 52.38], [4.9, 52.37]]
EIGENSCHAPPEN = {"bron": "natura2000", "naam": "Waterleidingduinen", "categorie": "natuur"}
DATA = {
    "features": [
        {
            "geometry": {"type": "MultiPolygon", "coordinates": [[RING]]},
            "properties": EIGENSCHAPPEN,
        }
    ]
}


def test_kml_bevat_gebied_trace_en_data_per_bron() -> None:
    wortel = ET.fromstring(maak_kml("Test", GEBIED, [(4.89, 52.37), (4.9, 52.375)], DATA))

    mappen = [m.findtext("k:name", namespaces=NS) for m in wortel.findall(".//k:Folder", NS)]
    assert mappen == ["Gebied", "Tracé", "natura2000"]
    assert (
        wortel.find(".//k:LineString/k:coordinates", NS).text
        == "4.8900000,52.3700000 4.9000000,52.3750000"
    )
    assert (
        wortel.findtext(".//k:Placemark/k:name[.='Waterleidingduinen']", namespaces=NS)
        == "Waterleidingduinen"
    )
    assert wortel.find(".//k:MultiGeometry/k:Polygon", NS) is not None


def test_kml_gebiedsring_is_gesloten() -> None:
    wortel = ET.fromstring(maak_kml("Test", GEBIED))
    ring = wortel.find(".//k:Polygon//k:coordinates", NS).text.split()

    assert ring[0] == ring[-1]


def test_bestandsnaam_is_veilig() -> None:
    assert bestandsnaam('Ring A/10 "nieuw"') == "gr0nd-Ring-A-10-nieuw.kml"
    assert bestandsnaam("///") == "gr0nd-project.kml"


def test_kml_endpoint_levert_bestand_en_404_voor_onbekend_project(tmp_path) -> None:
    client = TestClient(maak_app(Settings(data_map=str(tmp_path))))
    project = client.post("/api/projecten", json={"naam": "Mijn project", "gebied": GEBIED}).json()

    antwoord = client.get(f"/api/projecten/{project['id']}/kml")

    assert antwoord.status_code == 200
    assert "attachment" in antwoord.headers["content-disposition"]
    assert client.get("/api/projecten/bestaatniet/kml").status_code == 404
