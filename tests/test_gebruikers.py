import os

import pytest
from fastapi.testclient import TestClient
from psycopg.errors import UniqueViolation

from gr0nd.app import SESSIE_COOKIE, Settings, maak_app
from gr0nd.database import MIGRATIES, Database
from gr0nd.gebruikers import Gebruikers, Rol, Sessies

TEST_URL = os.environ.get("GR0ND_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(not TEST_URL, reason="GR0ND_TEST_DATABASE_URL niet gezet")


@pytest.fixture
def database():
    # Migratie 1 (PostGIS) wordt overgeslagen: die extensie is niet overal beschikbaar.
    db = Database(TEST_URL, migraties=MIGRATIES[1:])
    db.open()
    with db.verbinding() as verbinding:
        verbinding.execute("DROP TABLE IF EXISTS sessies, gebruikers, schema_migraties CASCADE")
    db.migreer()
    yield db
    db.sluit()


@pytest.fixture
def client(database):
    app = maak_app(Settings())
    app.state.database = database
    return TestClient(app, follow_redirects=False)


def test_maak_aan_en_controleer_inlog(database) -> None:
    gebruikers = Gebruikers(database)
    gebruikers.maak_aan("Kay@Voorbeeld.nl", "geheim", Rol.BEHEERDER)

    gebruiker = gebruikers.controleer_inlog("kay@voorbeeld.nl", "geheim")

    assert gebruiker is not None
    assert gebruiker.rol == Rol.BEHEERDER


def test_verkeerd_wachtwoord_of_onbekende_email_geeft_none(database) -> None:
    gebruikers = Gebruikers(database)
    gebruikers.maak_aan("kay@voorbeeld.nl", "geheim")

    assert gebruikers.controleer_inlog("kay@voorbeeld.nl", "fout") is None
    assert gebruikers.controleer_inlog("niemand@voorbeeld.nl", "geheim") is None


def test_dubbel_emailadres_wordt_geweigerd(database) -> None:
    gebruikers = Gebruikers(database)
    gebruikers.maak_aan("kay@voorbeeld.nl", "geheim")

    with pytest.raises(UniqueViolation):
        gebruikers.maak_aan("KAY@voorbeeld.nl", "ander")


def test_sessie_geeft_gebruiker_terug_en_onbekend_token_niet(database) -> None:
    gebruiker = Gebruikers(database).maak_aan("kay@voorbeeld.nl", "geheim")
    sessies = Sessies(database)

    token = sessies.start(gebruiker.id)

    assert sessies.haal_gebruiker(token) == gebruiker
    assert sessies.haal_gebruiker("onbekend") is None


def test_inloggen_zet_cookie_en_ik_werkt(database, client) -> None:
    Gebruikers(database).maak_aan("kay@voorbeeld.nl", "geheim")

    antwoord = client.post("/login", data={"email": "kay@voorbeeld.nl", "wachtwoord": "geheim"})

    assert antwoord.status_code == 303
    assert antwoord.headers["location"] == "/kaart"
    assert "httponly" in antwoord.headers["set-cookie"].lower()
    client.cookies.set(SESSIE_COOKIE, antwoord.cookies[SESSIE_COOKIE])
    assert client.get("/ik").json() == {"email": "kay@voorbeeld.nl", "rol": "gebruiker"}


def test_fout_wachtwoord_stuurt_terug_naar_login_zonder_cookie(database, client) -> None:
    Gebruikers(database).maak_aan("kay@voorbeeld.nl", "geheim")

    antwoord = client.post("/login", data={"email": "kay@voorbeeld.nl", "wachtwoord": "fout"})

    assert antwoord.headers["location"] == "/login"
    assert "set-cookie" not in antwoord.headers


def test_ik_zonder_sessie_geeft_401(client) -> None:
    assert client.get("/ik").status_code == 401
