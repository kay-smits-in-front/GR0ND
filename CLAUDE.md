# GR0ND

Open-source Python-platform om kabels en leidingen in de Nederlandse bodem te tonen en te ontwerpen.

## Starten
- Lokaal: `uv run python main.py` (demo-modus zonder database en login, opent de browser).
- Tests: `uv run pytest -q`. Lint: `uv run ruff check . && uv run ruff format .`
- DB-tests draaien alleen met `GR0ND_TEST_DATABASE_URL` (PostgreSQL met PostGIS).

## Structuur (bewust weinig bestanden)
- `gr0nd/app.py` instellingen, routes, lokale start. `gr0nd/kaart.py` overzichtskaart, lagen, zoeken.
- `gr0nd/wereld.py` 3D-wereld van het gebied: AHN-maaiveld, 3D BAG-gebouwen, BGT-bomen, GeoTOP-rand.
- `gr0nd/geotop.py` grond (TNO GeoTOP). `gr0nd/netten.py` kabels (open data). `gr0nd/aanleg.py` boring/kruisingen.
- `gr0nd/database.py`, `gebruikers.py`, `beheer.py`, `projecten.py`, `projectdata.py`, `export.py`.
- `gr0nd/static/` intro, login, kaart (MapLibre) en `blok.js` (3D-wereld, three.js, luchtfoto via PDOK WMS).
- `docs/` onderzoek (doel en workflow, bronnen, 3D, export, stations en kabels, layout).

## Regels
- Modern Python, één functie doet één ding, classes waar het past, Nederlandse namen en meldingen.
- Coördinaten: RD + NAP (EPSG:7415) in meters. In het blok: x = RD-oost, y = omhoog, z = -RD-noord.
- Toon altijd de bron. Open netdata heeft geen diepte: de diepte is indicatief en de UI zegt dat.
- Het 0-zicht is verwijderd; alles gebeurt in de 3D-wereld (gebieden tot 3,5 km, ware grootte).
- Niet doen: eigen 3D-formaat (zie docs/export-onderzoek.md), betaalde diensten aanmaken zonder akkoord.
