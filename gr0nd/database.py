"""Databaselaag: verbindingspool en migraties voor PostgreSQL/PostGIS."""

from collections.abc import Iterator
from contextlib import contextmanager

from psycopg import Connection
from psycopg_pool import ConnectionPool

# (versie, sql). Alleen onderaan toevoegen, bestaande regels nooit wijzigen.
MIGRATIES: list[tuple[int, str]] = [
    (1, "CREATE EXTENSION IF NOT EXISTS postgis"),
    (
        2,
        """
        CREATE TABLE gebruikers (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            email text NOT NULL,
            wachtwoord_hash text NOT NULL,
            rol text NOT NULL DEFAULT 'gebruiker' CHECK (rol IN ('gebruiker', 'beheerder')),
            aangemaakt_op timestamptz NOT NULL DEFAULT now()
        );
        CREATE UNIQUE INDEX gebruikers_email_uniek ON gebruikers (lower(email));
        """,
    ),
    (
        3,
        """
        CREATE TABLE sessies (
            token_hash text PRIMARY KEY,
            gebruiker_id bigint NOT NULL REFERENCES gebruikers (id) ON DELETE CASCADE,
            verloopt_op timestamptz NOT NULL
        );
        """,
    ),
]


class Database:
    """Beheert de verbindingspool en past migraties toe."""

    def __init__(self, url: str, migraties: list[tuple[int, str]] = MIGRATIES) -> None:
        self.migraties = migraties
        self.pool = ConnectionPool(url, open=False)

    def open(self) -> None:
        """Open de pool en wacht tot er een werkende verbinding is."""
        self.pool.open(wait=True)

    def sluit(self) -> None:
        """Sluit de pool."""
        self.pool.close()

    @contextmanager
    def verbinding(self) -> Iterator[Connection]:
        """Geef een verbinding uit de pool; commit bij succes, rollback bij een fout."""
        with self.pool.connection() as verbinding:
            yield verbinding

    def migreer(self) -> list[int]:
        """Pas alle nog niet toegepaste migraties toe, op volgorde. Geeft de nieuwe versies."""
        with self.verbinding() as verbinding:
            self._maak_migratietabel(verbinding)
            toegepast = self._toegepaste_versies(verbinding)
            nieuw = sorted(m for m in self.migraties if m[0] not in toegepast)
            for versie, sql in nieuw:
                verbinding.execute(sql)
                verbinding.execute("INSERT INTO schema_migraties (versie) VALUES (%s)", (versie,))
            return [versie for versie, _ in nieuw]

    @staticmethod
    def _maak_migratietabel(verbinding: Connection) -> None:
        verbinding.execute(
            "CREATE TABLE IF NOT EXISTS schema_migraties ("
            "versie integer PRIMARY KEY, "
            "toegepast_op timestamptz NOT NULL DEFAULT now())"
        )

    @staticmethod
    def _toegepaste_versies(verbinding: Connection) -> set[int]:
        rijen = verbinding.execute("SELECT versie FROM schema_migraties").fetchall()
        return {rij[0] for rij in rijen}
