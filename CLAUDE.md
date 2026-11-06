# GR0ND

Open-source Python-platform om kabels en leidingen in de Nederlandse bodem te tonen en te ontwerpen.

## Starten
- Lokaal: `uv run python main.py` (demo-modus zonder database en login, opent de browser).
- Tests: `uv run pytest -q`. Lint: `uv run ruff check . && uv run ruff format .`
- DB-tests draaien alleen met `GR0ND_TEST_DATABASE_URL` (PostgreSQL met PostGIS).

## Structuur (bewust weinig bestanden)
- `gr0nd/app.py` instellingen, routes, lokale start. `gr0nd/kaart.py` tracé, grondlagen, 0-zicht.
- `gr0nd/ontwerp.py` leidingtypen, controles, checklist. `gr0nd/database.py`, `gebruikers.py`, `beheer.py`.
- `gr0nd/static/` intro, login, kaart (HTML/CSS/JS, canvas 2D zonder library).
- `docs/` onderzoek (export, stations en kabels, layout).

## Regels
- Modern Python, één functie doet één ding, classes waar het past, Nederlandse namen en meldingen.
- Coördinaten: RD + NAP (EPSG:7415) in meters. In het 0-zicht: u haaks op tracé, diepte positief naar beneden.
- Grond, bovengrond en bestaande leidingen zijn VOORBEELDDATA; de UI zegt dat.
- Niet doen: eigen 3D-formaat (zie docs/export-onderzoek.md), betaalde diensten aanmaken zonder akkoord.
