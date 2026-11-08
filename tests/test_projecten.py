import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from gr0nd.app import Settings, maak_app
from gr0nd.projecten import Projecten, ProjectIn, oppervlak_km2

KLEIN = [(4.89, 52.37), (4.90, 52.37), (4.90, 52.38), (4.89, 52.38)]


def test_oppervlak_van_een_vierkantje_bij_amsterdam() -> None:
    assert oppervlak_km2(KLEIN) == pytest.approx(0.0100 * 111.32 * 0.6112 * 0.01 * 110.54, rel=0.01)


@pytest.mark.parametrize(
    ("gebied", "melding"),
    [
        ([(2.0, 52.0), (2.1, 52.0), (2.1, 52.1)], "buiten Nederland"),
        ([(4.0, 52.0), (5.5, 52.0), (5.5, 53.0)], "groter dan"),
    ],
)
def test_project_weigert_onbruikbaar_gebied(gebied, melding) -> None:
    with pytest.raises(ValidationError, match=melding):
        ProjectIn(naam="x", gebied=gebied)


def test_project_vraagt_een_naam() -> None:
    with pytest.raises(ValidationError):
        ProjectIn(naam="   ", gebied=KLEIN)


def test_opslag_bewaart_per_gebruiker_en_verwijdert(tmp_path) -> None:
    opslag = Projecten(tmp_path / "p.json")
    project = opslag.maak(1, ProjectIn(naam="A", gebied=KLEIN))

    assert [p.id for p in opslag.lijst(1)] == [project.id]
    assert opslag.lijst(2) == []
    assert opslag.werk_bij(1, project.id, ProjectIn(naam="B", gebied=KLEIN)).naam == "B"
    assert opslag.werk_bij(2, project.id, ProjectIn(naam="B", gebied=KLEIN)) is None
    assert opslag.verwijder(1, project.id) is True
    assert opslag.verwijder(1, project.id) is False


def test_api_maakt_lijst_en_verwijdert_project(tmp_path) -> None:
    client = TestClient(maak_app(Settings(data_map=str(tmp_path))))

    nieuw = client.post("/api/projecten", json={"naam": "Kade", "gebied": KLEIN})
    lijst = client.get("/api/projecten").json()

    assert nieuw.status_code == 201
    assert [p["naam"] for p in lijst] == ["Kade"]
    assert client.delete(f"/api/projecten/{nieuw.json()['id']}").status_code == 204
    assert client.delete("/api/projecten/bestaatniet").status_code == 404
    assert client.post("/api/projecten", json={"naam": "", "gebied": KLEIN}).status_code == 422


def test_projectdata_haalt_wfs_en_ogc_api_parallel_en_zet_rd_om(tmp_path) -> None:
    from gr0nd import projectdata
    from gr0nd.projectdata import Bron

    wfs = Bron("w", "WFS", "natuur", "wfs", "https://x/wfs", "laag")
    api = Bron("o", "API", "erfgoed", "ogc_api", "https://x/api")
    kapot = Bron("k", "Kapot", "natuur", "ogc_api", "https://x/kapot")

    def nep(url: str) -> dict:
        if "/kapot" in url:
            raise OSError("niet bereikbaar")
        if "/collections?" in url:
            return {"collections": [{"id": "a"}]}
        if "items" in url:
            punt = {"type": "Point", "coordinates": [4.9, 52.37]}
            return {"features": [{"geometry": punt, "properties": {"naam": "x", "leeg": None}}]}
        punt = {"type": "Point", "coordinates": [121000.0, 487000.0]}
        return {"features": [{"geometry": punt, "properties": {"id": 1}}, {"geometry": None}]}

    data = projectdata.haal_projectdata(KLEIN, nep, (wfs, api, kapot))

    status = {b["id"]: (b["status"], b["aantal"]) for b in data["bronnen"]}
    assert status == {"w": ("ok", 1), "o": ("ok", 1), "k": ("fout", 0)}
    lon, lat = next(f for f in data["features"] if f["properties"]["bron"] == "w")["geometry"][
        "coordinates"
    ]
    assert (round(lon, 2), round(lat, 2)) == (4.89, 52.37)
    assert all("leeg" not in f["properties"] for f in data["features"])
    assert data["aandachtspunten"]


def test_wfs_adres_vraagt_rd_omhullende_met_limiet() -> None:
    from gr0nd.projectdata import BRONNEN, wfs_adres

    adres = wfs_adres(BRONNEN[0], (4.89, 52.37, 4.90, 52.38))

    assert "typeNames=natura2000%3Anatura2000" in adres
    assert "EPSG%3A%3A28992" in adres
    assert "count=2000" in adres


def test_api_projectdata_bewaart_resultaat(tmp_path, monkeypatch) -> None:
    from gr0nd import projectdata

    aantal = []
    monkeypatch.setattr(
        projectdata, "haal_projectdata", lambda gebied: aantal.append(1) or {"features": []}
    )
    client = TestClient(maak_app(Settings(data_map=str(tmp_path))))
    project = client.post("/api/projecten", json={"naam": "A", "gebied": KLEIN}).json()

    client.get(f"/api/projecten/{project['id']}/data")
    client.get(f"/api/projecten/{project['id']}/data")
    client.get(f"/api/projecten/{project['id']}/data?vernieuw=true")

    assert len(aantal) == 2
    assert client.get("/api/projecten/bestaatniet/data").status_code == 404
