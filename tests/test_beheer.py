import os

import pytest

from gr0nd.beheer import lees_argumenten, maak_gebruiker
from gr0nd.database import MIGRATIES, Database
from gr0nd.gebruikers import Gebruikers, Rol


def test_lees_argumenten_standaardrol_is_gebruiker() -> None:
    argumenten = lees_argumenten(["maak-gebruiker", "kay@voorbeeld.nl"])

    assert argumenten.email == "kay@voorbeeld.nl"
    assert argumenten.rol == "gebruiker"


def test_lees_argumenten_neemt_rol_over() -> None:
    argumenten = lees_argumenten(["maak-gebruiker", "kay@voorbeeld.nl", "--rol", "beheerder"])

    assert argumenten.rol == "beheerder"


@pytest.mark.skipif(
    not os.environ.get("GR0ND_TEST_DATABASE_URL"), reason="GR0ND_TEST_DATABASE_URL niet gezet"
)
def test_maak_gebruiker_slaat_beheerder_op() -> None:
    db = Database(os.environ["GR0ND_TEST_DATABASE_URL"], migraties=MIGRATIES[1:])
    db.open()
    try:
        with db.verbinding() as verbinding:
            verbinding.execute("DROP TABLE IF EXISTS sessies, gebruikers, schema_migraties CASCADE")
        maak_gebruiker(db, "kay@voorbeeld.nl", "geheim123", Rol.BEHEERDER)

        gebruiker = Gebruikers(db).controleer_inlog("kay@voorbeeld.nl", "geheim123")
    finally:
        db.sluit()

    assert gebruiker is not None
    assert gebruiker.rol == Rol.BEHEERDER
