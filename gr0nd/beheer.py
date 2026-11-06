"""Beheercommando's.

Gebruik: uv run python -m gr0nd.beheer maak-gebruiker EMAIL [--rol beheerder]
"""

import argparse
import getpass
import sys

from gr0nd.app import Settings
from gr0nd.database import Database
from gr0nd.gebruikers import Gebruikers, Rol


def lees_argumenten(argv: list[str]) -> argparse.Namespace:
    """Lees de commandoregel."""
    parser = argparse.ArgumentParser(prog="gr0nd.beheer")
    onderdelen = parser.add_subparsers(dest="commando", required=True)
    maak = onderdelen.add_parser("maak-gebruiker", help="Maak een gebruiker of beheerder aan")
    maak.add_argument("email")
    maak.add_argument("--rol", choices=[r.value for r in Rol], default=Rol.GEBRUIKER.value)
    return parser.parse_args(argv)


def vraag_wachtwoord() -> str:
    """Vraag twee keer om een wachtwoord, zonder het te tonen."""
    wachtwoord = getpass.getpass("Wachtwoord: ")
    if wachtwoord != getpass.getpass("Nogmaals: "):
        sys.exit("Wachtwoorden komen niet overeen.")
    if len(wachtwoord) < 8:
        sys.exit("Wachtwoord moet minstens 8 tekens hebben.")
    return wachtwoord


def maak_gebruiker(database: Database, email: str, wachtwoord: str, rol: Rol) -> None:
    """Migreer de database en sla de gebruiker op."""
    database.migreer()
    Gebruikers(database).maak_aan(email, wachtwoord, rol)


def main(argv: list[str] | None = None) -> None:
    argumenten = lees_argumenten(sys.argv[1:] if argv is None else argv)
    url = Settings().database_url
    if not url:
        sys.exit("GR0ND_DATABASE_URL is niet gezet.")
    database = Database(url)
    database.open()
    try:
        maak_gebruiker(database, argumenten.email, vraag_wachtwoord(), Rol(argumenten.rol))
    finally:
        database.sluit()
    print(f"Gebruiker {argumenten.email} aangemaakt als {argumenten.rol}.")


if __name__ == "__main__":
    main()
