"""Projecten: een getekend gebied (met optioneel tracé) dat per gebruiker wordt bewaard.

Het gebied is de grens voor alle data die later wordt geladen, zodat nooit heel Nederland
nodig is. Opslag is voorlopig één JSON-bestand; een databasetabel volgt (zie CLAUDE.md).
"""

import json
import math
import os
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field, field_validator

MAX_GEBIED_KM2 = 100.0  # 10 × 10 km: groter laden we niet, om data en rekentijd klein te houden
MAX_HOEKPUNTEN = 500
MAX_TRACEPUNTEN = 200


def oppervlak_km2(ring: list[tuple[float, float]]) -> float:
    """Oppervlak van een gebied in lengte/breedtegraden (vlakke benadering) in km²."""
    lon0, lat0 = ring[0]
    kosinus = math.cos(math.radians(lat0))
    xy = [((lon - lon0) * 111.32 * kosinus, (lat - lat0) * 110.54) for lon, lat in ring]
    som = sum(
        x * xy[(i + 1) % len(xy)][1] - xy[(i + 1) % len(xy)][0] * y for i, (x, y) in enumerate(xy)
    )
    return abs(som) / 2


class ProjectIn(BaseModel):
    """Wat de gebruiker instuurt: naam, gebied en (later) het tracé, als [lon, lat]."""

    naam: str = Field(min_length=1, max_length=80)
    gebied: list[tuple[float, float]] = Field(min_length=3, max_length=MAX_HOEKPUNTEN)
    trace: list[tuple[float, float]] = Field(default_factory=list, max_length=MAX_TRACEPUNTEN)

    @field_validator("naam")
    @classmethod
    def naam_opschonen(cls, waarde: str) -> str:
        waarde = waarde.strip()
        if not waarde:
            raise ValueError("Geef het project een naam.")
        return waarde

    @field_validator("gebied")
    @classmethod
    def gebied_binnen_nederland_en_niet_te_groot(
        cls, ring: list[tuple[float, float]]
    ) -> list[tuple[float, float]]:
        if any(not (3.0 <= lon <= 7.5 and 50.5 <= lat <= 53.8) for lon, lat in ring):
            raise ValueError("Het gebied ligt buiten Nederland.")
        if oppervlak_km2(ring) > MAX_GEBIED_KM2:
            raise ValueError(f"Het gebied is groter dan {MAX_GEBIED_KM2:.0f} km².")
        return ring


class Project(ProjectIn):
    id: str
    aangemaakt: datetime


class Projecten:
    """Bewaart de projecten per gebruiker in één JSON-bestand."""

    def __init__(self, pad: Path) -> None:
        self.pad = pad

    def _lees(self) -> dict[str, list[dict]]:
        if not self.pad.exists():
            return {}
        return json.loads(self.pad.read_text(encoding="utf-8"))

    def _schrijf(self, alles: dict[str, list[dict]]) -> None:
        self.pad.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w", dir=self.pad.parent, suffix=".tmp", delete=False, encoding="utf-8"
        ) as tijdelijk:
            json.dump(alles, tijdelijk, ensure_ascii=False)
        os.replace(tijdelijk.name, self.pad)

    def lijst(self, gebruiker_id: int) -> list[Project]:
        return [Project(**p) for p in self._lees().get(str(gebruiker_id), [])]

    def maak(self, gebruiker_id: int, invoer: ProjectIn) -> Project:
        project = Project(
            **invoer.model_dump(), id=uuid.uuid4().hex[:12], aangemaakt=datetime.now(UTC)
        )
        alles = self._lees()
        alles.setdefault(str(gebruiker_id), []).append(project.model_dump(mode="json"))
        self._schrijf(alles)
        return project

    def werk_bij(self, gebruiker_id: int, project_id: str, invoer: ProjectIn) -> Project | None:
        alles = self._lees()
        lijst = alles.get(str(gebruiker_id), [])
        for i, oud in enumerate(lijst):
            if oud["id"] == project_id:
                nieuw = Project(**invoer.model_dump(), id=project_id, aangemaakt=oud["aangemaakt"])
                lijst[i] = nieuw.model_dump(mode="json")
                self._schrijf(alles)
                return nieuw
        return None

    def verwijder(self, gebruiker_id: int, project_id: str) -> bool:
        alles = self._lees()
        lijst = alles.get(str(gebruiker_id), [])
        rest = [p for p in lijst if p["id"] != project_id]
        if len(rest) == len(lijst):
            return False
        alles[str(gebruiker_id)] = rest
        self._schrijf(alles)
        return True

    def data_pad(self, project_id: str) -> Path:
        return self.pad.parent / "projectdata" / f"{project_id}.json"

    def lees_data(self, project_id: str) -> dict | None:
        """De eerder opgehaalde projectdata, of None als die er nog niet is."""
        pad = self.data_pad(project_id)
        return json.loads(pad.read_text(encoding="utf-8")) if pad.exists() else None

    def bewaar_data(self, project_id: str, data: dict) -> None:
        pad = self.data_pad(project_id)
        pad.parent.mkdir(parents=True, exist_ok=True)
        pad.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def zoek(self, gebruiker_id: int, project_id: str) -> Project | None:
        return next((p for p in self.lijst(gebruiker_id) if p.id == project_id), None)
