"""GR0ND applicatie: instellingen, routes en lokale start."""

import threading
import webbrowser
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Annotated

import uvicorn
from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

from gr0nd import kaart, ontwerp, projectdata
from gr0nd.database import Database
from gr0nd.gebruikers import SESSIE_DUUR, Gebruiker, Gebruikers, Rol, Sessies
from gr0nd.projecten import Project, Projecten, ProjectIn

STATIC_MAP = Path(__file__).parent / "static"
SESSIE_COOKIE = "gr0nd_sessie"
DEMO_GEBRUIKER = Gebruiker(id=0, email="demo@lokaal", rol=Rol.GEBRUIKER)
ZOEK_NIET_BEREIKBAAR = "Zoeken is nu niet beschikbaar. Probeer het straks opnieuw."


class Settings(BaseSettings):
    """Instellingen uit omgevingsvariabelen (prefix GR0ND_) of een .env-bestand."""

    model_config = SettingsConfigDict(env_prefix="GR0ND_", env_file=".env")

    omgeving: str = "lokaal"
    database_url: str = ""
    data_map: str = "data"  # hier staan de projecten (voorlopig als bestand)


class ControleIn(BaseModel):
    """Invoer voor de controle: het tracé, de positie langs het tracé en alle leidingen."""

    punten: list[tuple[float, float]]
    s: float
    leidingen: list[ontwerp.Leiding]


def maak_levenscyclus(settings: Settings):
    """Maak de lifespan: bij starten database openen en migreren, bij stoppen sluiten."""

    @asynccontextmanager
    async def levenscyclus(app: FastAPI) -> AsyncIterator[None]:
        if not settings.database_url:
            yield
            return
        database = Database(settings.database_url)
        database.open()
        database.migreer()
        app.state.database = database
        yield
        database.sluit()

    return levenscyclus


def zoek_database(request: Request) -> Database | None:
    """Geef de database van de app, of None als die niet is ingesteld."""
    return getattr(request.app.state, "database", None)


def is_demo(request: Request) -> bool:
    """Lokaal zonder database draait de app in demo-modus: zonder inloggen."""
    return request.app.state.settings.omgeving == "lokaal" and zoek_database(request) is None


def zoek_gebruiker(
    request: Request, database: Annotated[Database | None, Depends(zoek_database)]
) -> Gebruiker | None:
    """Geef de ingelogde gebruiker (in demo-modus de demo-gebruiker), anders None."""
    if is_demo(request):
        return DEMO_GEBRUIKER
    token = request.cookies.get(SESSIE_COOKIE)
    if database is None or not token:
        return None
    return Sessies(database).haal_gebruiker(token)


def haal_ingelogde_gebruiker(
    gebruiker: Annotated[Gebruiker | None, Depends(zoek_gebruiker)],
) -> Gebruiker:
    """Geef de ingelogde gebruiker, of 401 als er geen geldige sessie is."""
    if gebruiker is None:
        raise HTTPException(status_code=401, detail="Niet ingelogd")
    return gebruiker


Ingelogd = Annotated[Gebruiker, Depends(haal_ingelogde_gebruiker)]


def lees_punten(tekst: str) -> list[tuple[float, float]]:
    """Lees 'x,y;x,y;...' en geef de paren, of 400 als het niet kan."""
    try:
        return [tuple(float(deel) for deel in paar.split(",")) for paar in tekst.split(";")]
    except ValueError as fout:
        raise HTTPException(status_code=400, detail="Punten zijn niet goed opgegeven.") from fout


def maak_trace(punten: list[tuple[float, float]]) -> kaart.Trace:
    """Maak een tracé, of geef 400 met de Nederlandse melding."""
    try:
        return kaart.Trace(tuple(punten))
    except ValueError as fout:
        raise HTTPException(status_code=400, detail=str(fout)) from fout


def posities_json(posities: dict[str, tuple[float, float]]) -> dict[str, dict[str, float]]:
    return {id_: {"u": round(u, 4), "diepte": round(d, 4)} for id_, (u, d) in posities.items()}


def maak_app(settings: Settings | None = None) -> FastAPI:
    """Bouw de FastAPI-app en koppel de routes."""
    settings = settings or Settings()
    app = FastAPI(title="GR0ND", version="0.1.0", lifespan=maak_levenscyclus(settings))
    app.state.settings = settings
    projecten = Projecten(Path(settings.data_map) / "projecten.json")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "omgeving": settings.omgeving}

    @app.get("/", include_in_schema=False)
    def intro() -> FileResponse:
        return FileResponse(STATIC_MAP / "intro.html")

    @app.get("/login", include_in_schema=False)
    def login() -> FileResponse:
        return FileResponse(STATIC_MAP / "login.html")

    @app.post("/login", include_in_schema=False)
    def inloggen(
        request: Request,
        email: Annotated[str, Form()],
        wachtwoord: Annotated[str, Form()],
        database: Annotated[Database | None, Depends(zoek_database)],
    ) -> RedirectResponse:
        if is_demo(request):
            return RedirectResponse("/kaart", status_code=303)
        if database is None:
            raise HTTPException(status_code=503, detail="Database niet beschikbaar")
        gebruiker = Gebruikers(database).controleer_inlog(email, wachtwoord)
        if gebruiker is None:
            return RedirectResponse("/login", status_code=303)
        token = Sessies(database).start(gebruiker.id)
        antwoord = RedirectResponse("/kaart", status_code=303)
        antwoord.set_cookie(
            SESSIE_COOKIE,
            token,
            max_age=int(SESSIE_DUUR.total_seconds()),
            httponly=True,
            samesite="lax",
            secure=settings.omgeving == "productie",
        )
        return antwoord

    @app.get("/ik")
    def ik(gebruiker: Ingelogd) -> dict[str, str]:
        return {"email": gebruiker.email, "rol": gebruiker.rol.value}

    @app.get("/kaart", include_in_schema=False, response_model=None)
    def kaartpagina(
        gebruiker: Annotated[Gebruiker | None, Depends(zoek_gebruiker)],
    ) -> FileResponse | RedirectResponse:
        if gebruiker is None:
            return RedirectResponse("/login", status_code=303)
        return FileResponse(STATIC_MAP / "kaart.html")

    @app.get("/api/nederland")
    def nederland(_: Ingelogd) -> dict:
        return kaart.nederland()

    @app.get("/api/lagen")
    def lagen(_: Ingelogd) -> dict:
        """De kaartlagen die de kaart kan tonen, en de lagen die nog volgen."""
        return kaart.kaartlagen()

    @app.get("/api/zoek")
    def zoek(_: Ingelogd, q: str) -> list[dict]:
        try:
            return kaart.zoek_locaties(q)
        except OSError as fout:
            raise HTTPException(status_code=502, detail=ZOEK_NIET_BEREIKBAAR) from fout

    @app.get("/api/zoek/locatie")
    def zoek_locatie(_: Ingelogd, id: str) -> dict:
        try:
            return kaart.zoek_locatie(id)
        except LookupError as fout:
            raise HTTPException(status_code=404, detail=str(fout)) from fout
        except OSError as fout:
            raise HTTPException(status_code=502, detail=ZOEK_NIET_BEREIKBAAR) from fout

    @app.get("/api/rd")
    def rd(_: Ingelogd, punten: str) -> dict[str, list[list[float]]]:
        """Zet 'lon,lat;lon,lat;...' om naar RD-paren."""
        paren = lees_punten(punten)
        if any(len(paar) != 2 for paar in paren):
            raise HTTPException(status_code=400, detail="Punten zijn niet goed opgegeven.")
        return {"punten": [list(kaart.wgs84_naar_rd(lon, lat)) for lon, lat in paren]}

    @app.get("/api/wgs84")
    def wgs84(_: Ingelogd, x: float, y: float) -> dict[str, float]:
        lon, lat = kaart.rd_naar_wgs84(x, y)
        return {"lon": lon, "lat": lat}

    @app.get("/api/profiel")
    def profiel(_: Ingelogd, punten: str, s: float = 0.0) -> dict:
        """Het 0-zicht met de bibliotheek, bestaande leidingen en de checklist."""
        trace = maak_trace(lees_punten(punten))
        try:
            antwoord = kaart.dwarsprofiel(trace, s)
        except ValueError as fout:
            raise HTTPException(status_code=400, detail=str(fout)) from fout
        bestaand = ontwerp.bestaande_leidingen(antwoord["bovengrond"])
        _, posities = ontwerp.controleer(antwoord["bovengrond"], bestaand)
        return antwoord | {
            "bibliotheek": [asdict(leidingtype) for leidingtype in ontwerp.BIBLIOTHEEK],
            "leidingen": [leiding.model_dump() for leiding in bestaand],
            "posities": posities_json(posities),
            "checklist": [asdict(punt) for punt in ontwerp.CHECKLIST],
        }

    @app.post("/api/controle")
    def controle(_: Ingelogd, invoer: ControleIn) -> dict:
        """Controleer alle leidingen en geef meldingen, posities en de checklist-status."""
        trace = maak_trace(invoer.punten)
        bovengrond = kaart.voorbeeld_bovengrond(trace.seed(invoer.s))
        try:
            meldingen, posities = ontwerp.controleer(bovengrond, invoer.leidingen)
        except ValueError as fout:
            raise HTTPException(status_code=422, detail=str(fout)) from fout
        heeft_nieuwe = any(leiding.nieuw for leiding in invoer.leidingen)
        return {
            "meldingen": [melding.model_dump() for melding in meldingen],
            "posities": posities_json(posities),
            "checklist": ontwerp.checklist_status(meldingen, heeft_nieuwe),
            "afstanden": ontwerp.meetlijnen(bovengrond, invoer.leidingen, posities),
        }

    @app.get("/api/projecten")
    def projecten_lijst(gebruiker: Ingelogd) -> list[Project]:
        return projecten.lijst(gebruiker.id)

    @app.post("/api/projecten", status_code=201)
    def project_maak(gebruiker: Ingelogd, invoer: ProjectIn) -> Project:
        return projecten.maak(gebruiker.id, invoer)

    @app.put("/api/projecten/{project_id}")
    def project_werk_bij(gebruiker: Ingelogd, project_id: str, invoer: ProjectIn) -> Project:
        project = projecten.werk_bij(gebruiker.id, project_id, invoer)
        if project is None:
            raise HTTPException(status_code=404, detail="Project niet gevonden.")
        return project

    @app.delete("/api/projecten/{project_id}", status_code=204)
    def project_verwijder(gebruiker: Ingelogd, project_id: str) -> None:
        if not projecten.verwijder(gebruiker.id, project_id):
            raise HTTPException(status_code=404, detail="Project niet gevonden.")

    @app.get("/api/projecten/{project_id}/data")
    def project_data(gebruiker: Ingelogd, project_id: str, vernieuw: bool = False) -> dict:
        project = projecten.zoek(gebruiker.id, project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project niet gevonden.")
        data = None if vernieuw else projecten.lees_data(project_id)
        if data is None:
            data = projectdata.haal_projectdata(project.gebied)
            projecten.bewaar_data(project_id, data)
        return data

    app.mount("/static", StaticFiles(directory=STATIC_MAP), name="static")
    return app


app = maak_app()


def start_lokaal(poort: int = 8000) -> None:
    """Start de app op dit apparaat en open de browser. Stoppen met Ctrl+C."""
    adres = f"http://127.0.0.1:{poort}"
    threading.Timer(1.5, webbrowser.open, args=[adres]).start()
    uvicorn.run(app, host="127.0.0.1", port=poort)


if __name__ == "__main__":
    start_lokaal()
