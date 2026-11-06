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

from gr0nd import kaart, ontwerp
from gr0nd.database import Database
from gr0nd.gebruikers import SESSIE_DUUR, Gebruiker, Gebruikers, Rol, Sessies

STATIC_MAP = Path(__file__).parent / "static"
SESSIE_COOKIE = "gr0nd_sessie"
DEMO_GEBRUIKER = Gebruiker(id=0, email="demo@lokaal", rol=Rol.GEBRUIKER)


class Settings(BaseSettings):
    """Instellingen uit omgevingsvariabelen (prefix GR0ND_) of een .env-bestand."""

    model_config = SettingsConfigDict(env_prefix="GR0ND_", env_file=".env")

    omgeving: str = "lokaal"
    database_url: str = ""


class ControleIn(BaseModel):
    """Invoer voor de controle: het tracé, de positie langs het tracé en alle leidingen."""

    ax: float
    ay: float
    bx: float
    by: float
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


def maak_trace(ax: float, ay: float, bx: float, by: float) -> kaart.Trace:
    """Maak een tracé, of geef 400 met de Nederlandse melding."""
    try:
        return kaart.Trace(ax, ay, bx, by)
    except ValueError as fout:
        raise HTTPException(status_code=400, detail=str(fout)) from fout


def posities_json(posities: dict[str, tuple[float, float]]) -> dict[str, dict[str, float]]:
    return {id_: {"u": round(u, 4), "diepte": round(d, 4)} for id_, (u, d) in posities.items()}


def maak_app(settings: Settings | None = None) -> FastAPI:
    """Bouw de FastAPI-app en koppel de routes."""
    settings = settings or Settings()
    app = FastAPI(title="GR0ND", version="0.1.0", lifespan=maak_levenscyclus(settings))
    app.state.settings = settings

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

    @app.get("/api/profiel")
    def profiel(_: Ingelogd, ax: float, ay: float, bx: float, by: float, s: float = 0.0) -> dict:
        """Het 0-zicht met de bibliotheek, bestaande leidingen en de checklist."""
        trace = maak_trace(ax, ay, bx, by)
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
        trace = maak_trace(invoer.ax, invoer.ay, invoer.bx, invoer.by)
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
        }

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
