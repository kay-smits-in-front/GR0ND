from fastapi.testclient import TestClient

from gr0nd import kaart
from gr0nd.app import Settings, maak_app


def test_health_geeft_ok_en_omgeving() -> None:
    client = TestClient(maak_app(Settings(omgeving="test")))

    antwoord = client.get("/health")

    assert antwoord.status_code == 200
    assert antwoord.json() == {"status": "ok", "omgeving": "test"}


def test_intro_toont_merknaam() -> None:
    client = TestClient(maak_app(Settings()))

    antwoord = client.get("/")

    assert antwoord.status_code == 200
    assert "GR0ND" in antwoord.text
    assert "Empowered by In-front" in antwoord.text


def test_login_toont_formulier() -> None:
    client = TestClient(maak_app(Settings()))

    antwoord = client.get("/login")

    assert antwoord.status_code == 200
    assert 'name="email"' in antwoord.text
    assert 'name="wachtwoord"' in antwoord.text


DEMO = Settings(omgeving="lokaal", database_url="")
PRODUCTIE = Settings(omgeving="productie", database_url="")


def test_demo_login_gaat_naar_de_kaart() -> None:
    client = TestClient(maak_app(DEMO))

    antwoord = client.post("/login", data={"email": "x", "wachtwoord": "y"}, follow_redirects=False)

    assert antwoord.status_code == 303
    assert antwoord.headers["location"] == "/kaart"


def test_demo_kaartpagina_is_bereikbaar() -> None:
    assert TestClient(maak_app(DEMO)).get("/kaart").status_code == 200


def test_zonder_database_in_productie_stuurt_kaart_naar_login() -> None:
    client = TestClient(maak_app(PRODUCTIE))

    antwoord = client.get("/kaart", follow_redirects=False)

    assert antwoord.status_code == 303
    assert antwoord.headers["location"] == "/login"
    assert client.get("/api/netten", params={"x0": 0, "y0": 0, "x1": 1, "y1": 1}).status_code == 401


def test_api_nederland_geeft_omtrek_en_zonekaart() -> None:
    antwoord = TestClient(maak_app(DEMO)).get("/api/nederland")

    assert antwoord.status_code == 200
    assert antwoord.json()["crs"] == "EPSG:28992"


def test_api_lagen_geeft_lagen_en_wat_nog_volgt() -> None:
    inhoud = TestClient(maak_app(DEMO)).get("/api/lagen").json()

    assert any(laag["id"] == "luchtfoto" for laag in inhoud["lagen"])
    assert inhoud["volgt"]


def test_api_rd_en_wgs84_zetten_coordinaten_om() -> None:
    client = TestClient(maak_app(DEMO))

    rd = client.get("/api/rd", params={"punten": "5.38720621,52.1551744;4.9,52.37"}).json()[
        "punten"
    ]
    wgs = client.get("/api/wgs84", params={"x": 155000, "y": 463000}).json()

    assert abs(rd[0][0] - 155000) < 2
    assert len(rd) == 2
    assert abs(wgs["lat"] - 52.155) < 0.001


def test_api_zoek_geeft_suggesties_en_502_als_pdok_uitvalt(monkeypatch) -> None:
    client = TestClient(maak_app(DEMO))
    docs = [{"type": "adres", "weergavenaam": "Dam 1, Amsterdam", "id": "adr-1"}]
    monkeypatch.setattr(kaart, "haal_json", lambda url: {"response": {"docs": docs}})

    assert client.get("/api/zoek", params={"q": "Dam 1"}).json()[0]["id"] == "adr-1"

    def uitval(url):
        raise OSError("geen verbinding")

    monkeypatch.setattr(kaart, "haal_json", uitval)
    assert client.get("/api/zoek", params={"q": "Dam 1"}).status_code == 502
    assert client.get("/api/zoek/locatie", params={"id": "adr-1"}).status_code == 502


def test_api_rd_weigert_slechte_punten() -> None:
    client = TestClient(maak_app(DEMO))

    assert client.get("/api/rd", params={"punten": "abc"}).status_code == 400
    assert client.get("/api/rd", params={"punten": "5.3,52.1,7"}).status_code == 400


def test_wereld_vraagt_inloggen_en_weigert_te_groot_gebied() -> None:
    ring = [[0, 0], [5000, 0], [5000, 5000]]
    productie = TestClient(maak_app(Settings(omgeving="test")))
    assert productie.post("/api/wereld", json={"ring": ring}).status_code == 401
    demo = TestClient(maak_app(DEMO))
    assert demo.post("/api/wereld", json={"ring": ring}).status_code == 400
    assert demo.post("/api/wereld", json={"ring": ring[:2]}).status_code == 422


def test_api_aanleg_geeft_profiel_en_kruisingen(monkeypatch) -> None:
    from gr0nd import netten

    lijn = {"soort": "ls", "beheerder": "Test", "lijnen": [[[136050, 454990], [136050, 455010]]]}
    monkeypatch.setattr(
        netten,
        "haal_netten",
        lambda gebied: {"soorten": [vars(netten.SOORTEN["ls"])], "lagen": [lijn]},
    )
    client = TestClient(maak_app(DEMO))
    vraag = {
        "punten": [[136000, 455000], [136100, 455000]],
        "aanleg": {"wijze": "boring", "diepte": 4},
    }
    data = client.post("/api/aanleg", json=vraag).json()
    assert data["lengte"] == 100 and data["profiel"][0][2] == 0
    assert data["kruisingen"][0]["ok"] and data["kruisingen"][0]["s"] == 50
    assert (
        client.post(
            "/api/aanleg", json=vraag | {"aanleg": {"wijze": "boring", "diepte": 99}}
        ).status_code
        == 422
    )
    assert (
        client.post("/api/aanleg", json=vraag | {"aanleg": {"wijze": "graven"}}).status_code == 422
    )


def test_api_aanleg_geeft_duur_grondverzet_en_boorstukken(monkeypatch) -> None:
    from gr0nd import netten

    monkeypatch.setattr(netten, "haal_netten", lambda gebied: {"soorten": [], "lagen": []})
    aanleg = {"wijze": "ontgraven", "snelheid_m_per_uur": 30, "boringen": [[50, 100]]}
    vraag = {"punten": [[0, 0], [150, 0]], "aanleg": aanleg}
    data = TestClient(maak_app(DEMO)).post("/api/aanleg", json=vraag).json()
    assert data["boorstukken"] == [[50, 100]]
    assert data["duur_uren"] == round(100 / 30 + 50 / 20, 1)
    assert data["grondverzet_m3"] == round(100 * 0.6 * 1.3, 1)


def test_api_aanleg_geojson_is_een_download(monkeypatch) -> None:
    from gr0nd import netten

    monkeypatch.setattr(netten, "haal_netten", lambda gebied: {"soorten": [], "lagen": []})
    vraag = {
        "punten": [[136000, 455000], [136100, 455000]],
        "aanleg": {"wijze": "boring"},
        "naam": "Mijn tracé",
    }
    antwoord = TestClient(maak_app(DEMO)).post("/api/aanleg/geojson", json=vraag)
    assert antwoord.status_code == 200
    assert "gr0nd-Mijn-trac-trace.geojson" in antwoord.headers["content-disposition"]
    lijn = antwoord.json()["features"][0]
    assert lijn["properties"]["wijze"] == "boring" and len(lijn["geometry"]["coordinates"]) > 2


def test_api_aandacht_weigert_te_lang_trace() -> None:
    vraag = {"punten": [[0, 0], [9000, 0]], "aanleg": {"wijze": "ontgraven"}}
    assert TestClient(maak_app(DEMO)).post("/api/aandacht", json=vraag).status_code == 400
