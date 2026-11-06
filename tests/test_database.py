import os

import pytest

from gr0nd.database import Database

TEST_URL = os.environ.get("GR0ND_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(not TEST_URL, reason="GR0ND_TEST_DATABASE_URL niet gezet")

TEST_MIGRATIES = [
    (1, "CREATE TABLE IF NOT EXISTS test_a (id integer)"),
    (2, "CREATE TABLE IF NOT EXISTS test_b (id integer)"),
]


@pytest.fixture
def database():
    db = Database(TEST_URL, migraties=TEST_MIGRATIES)
    db.open()
    with db.verbinding() as verbinding:
        verbinding.execute("DROP TABLE IF EXISTS schema_migraties, test_a, test_b")
    yield db
    db.sluit()


def test_migreer_past_nieuwe_versies_eenmalig_toe(database) -> None:
    assert database.migreer() == [1, 2]
    assert database.migreer() == []


def test_migreer_slaat_toegepaste_versies_over(database) -> None:
    database.migraties = TEST_MIGRATIES[:1]
    assert database.migreer() == [1]

    database.migraties = TEST_MIGRATIES
    assert database.migreer() == [2]
