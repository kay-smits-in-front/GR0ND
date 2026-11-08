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
TRACE_PUNTEN = "121000,487000;121000,487500"
TRACE = {"punten": [[121000, 487000], [121000, 487500]]}
VRAAG = {"punten": TRACE_PUNTEN}


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
    assert client.get("/api/profiel", params=VRAAG).status_code == 401


def test_api_nederland_geeft_omtrek_en_zonekaart() -> None:
    antwoord = TestClient(maak_app(DEMO)).get("/api/nederland")

    assert antwoord.status_code == 200
    assert antwoord.json()["crs"] == "EPSG:28992"


def test_api_profiel_geeft_lagen_bibliotheek_en_checklist() -> None:
    antwoord = TestClient(maak_app(DEMO)).get("/api/profiel", params=VRAAG | {"s": 100})
    inhoud = antwoord.json()

    assert antwoord.status_code == 200
    assert len(inhoud["lagen"]) == 8
    assert inhoud["bibliotheek"]
    assert inhoud["posities"]
    assert len(inhoud["checklist"]) == 14


def test_api_profiel_weigert_te_kort_trace_en_positie_buiten_trace() -> None:
    client = TestClient(maak_app(DEMO))

    assert (
        client.get("/api/profiel", params={"punten": "121000,487000;121000,487005"}).status_code
        == 400
    )
    assert client.get("/api/profiel", params=VRAAG | {"s": 9999}).status_code == 400


def test_api_controle_meldt_te_weinig_dekking() -> None:
    leiding = {"id": "n", "type_id": "ms240", "u": -8, "diepte": 0.5, "nieuw": True}

    antwoord = TestClient(maak_app(DEMO)).post(
        "/api/controle", json=TRACE | {"s": 100, "leidingen": [leiding]}
    )
    inhoud = antwoord.json()

    assert antwoord.status_code == 200
    assert any(m["code"] == "dekking" for m in inhoud["meldingen"])
    assert inhoud["checklist"]["dekking"] == "fout"


def test_api_controle_geeft_422_bij_ontbrekende_buis() -> None:
    leiding = {"id": "k", "type_id": "ms150", "u": 0, "diepte": 1, "buis_id": "weg"}

    antwoord = TestClient(maak_app(DEMO)).post(
        "/api/controle", json=TRACE | {"s": 100, "leidingen": [leiding]}
    )

    assert antwoord.status_code == 422


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


def test_api_profiel_en_controle_werken_met_een_bocht() -> None:
    client = TestClient(maak_app(DEMO))
    punten = "121000,487000;121000,487300;121400,487300"

    profiel = client.get("/api/profiel", params={"punten": punten, "s": 500}).json()
    antwoord = client.post(
        "/api/controle",
        json={
            "punten": [[121000, 487000], [121000, 487300], [121400, 487300]],
            "s": 500,
            "leidingen": [],
        },
    )

    assert profiel["trace"]["azimut"] == 90
    assert profiel["trace"]["knikken"] == [300.0]
    assert antwoord.status_code == 200
