"""Gebruikers, wachtwoorden en sessies."""

import hashlib
import secrets
from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum

from pwdlib import PasswordHash

from gr0nd.database import Database

HASHER = PasswordHash.recommended()
# Wordt gebruikt bij onbekende e-mailadressen, zodat de rekentijd gelijk blijft.
NEP_HASH = HASHER.hash("nep-wachtwoord")
SESSIE_DUUR = timedelta(days=7)


class Rol(StrEnum):
    GEBRUIKER = "gebruiker"
    BEHEERDER = "beheerder"


@dataclass(frozen=True)
class Gebruiker:
    id: int
    email: str
    rol: Rol


class Gebruikers:
    """Aanmaken en controleren van gebruikers."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def maak_aan(self, email: str, wachtwoord: str, rol: Rol = Rol.GEBRUIKER) -> Gebruiker:
        """Sla een nieuwe gebruiker op. Een bestaand e-mailadres geeft een UniqueViolation."""
        email = email.strip()
        with self.database.verbinding() as verbinding:
            rij = verbinding.execute(
                "INSERT INTO gebruikers (email, wachtwoord_hash, rol) VALUES (%s, %s, %s) "
                "RETURNING id",
                (email, HASHER.hash(wachtwoord), rol.value),
            ).fetchone()
        return Gebruiker(id=rij[0], email=email, rol=rol)

    def controleer_inlog(self, email: str, wachtwoord: str) -> Gebruiker | None:
        """Geef de gebruiker bij een juiste combinatie, anders None."""
        with self.database.verbinding() as verbinding:
            rij = verbinding.execute(
                "SELECT id, email, wachtwoord_hash, rol FROM gebruikers "
                "WHERE lower(email) = lower(%s)",
                (email.strip(),),
            ).fetchone()
        if rij is None:
            HASHER.verify(wachtwoord, NEP_HASH)
            return None
        if not HASHER.verify(wachtwoord, rij[2]):
            return None
        return Gebruiker(id=rij[0], email=rij[1], rol=Rol(rij[3]))


class Sessies:
    """Sessies in de database. Het token zelf wordt nooit opgeslagen, alleen de hash."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def start(self, gebruiker_id: int) -> str:
        """Maak een sessie en geef het token terug voor in de cookie."""
        token = secrets.token_urlsafe(32)
        with self.database.verbinding() as verbinding:
            verbinding.execute(
                "INSERT INTO sessies (token_hash, gebruiker_id, verloopt_op) "
                "VALUES (%s, %s, now() + %s)",
                (self._hash(token), gebruiker_id, SESSIE_DUUR),
            )
        return token

    def haal_gebruiker(self, token: str) -> Gebruiker | None:
        """Geef de gebruiker bij een geldig, niet verlopen token, anders None."""
        with self.database.verbinding() as verbinding:
            rij = verbinding.execute(
                "SELECT g.id, g.email, g.rol FROM sessies s "
                "JOIN gebruikers g ON g.id = s.gebruiker_id "
                "WHERE s.token_hash = %s AND s.verloopt_op > now()",
                (self._hash(token),),
            ).fetchone()
        if rij is None:
            return None
        return Gebruiker(id=rij[0], email=rij[1], rol=Rol(rij[2]))

    @staticmethod
    def _hash(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()
