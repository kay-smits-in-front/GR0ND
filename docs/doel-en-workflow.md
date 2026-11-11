# Doel en workflow (11 nov 2026)

## Doel
Het intekenen van kabeltracés sneller en beter maken. GR0ND automatiseert de route **niet**: de
engineer kiest de route. GR0ND zorgt dat alle beschikbare informatie over een gebied zo snel
mogelijk beschikbaar is, en toont het gebied in 3D in plaats van met lijntjes en blokjes zoals in AutoCAD.
In 3D is te zien waar het tracé ligt en hoe het wordt aangelegd: open ontgraving of gestuurde boring.

## Workflow van de engineer
| Stap | Wat gebeurt er | In GR0ND nu | Ontbreekt |
| --- | --- | --- | --- |
| 1. Opdracht komt binnen | Engineer krijgt een aanvraag | Project met naam | Opdrachtgegevens (klant, kenmerk, deadline) |
| 2. Gebied vastleggen | Gebied wordt in het systeem gezet | Gebied tekenen (max. 100 km²) | – |
| 3. Informatie verzamelen | Alle bronnen voor het gebied ophalen | Natura 2000, cultuurhistorie, grondwatermonitoring | Bodemonderzoek, grondsoort, kabels, eigendom, bestemming (zie hieronder) |
| 4. Tracé tekenen | Engineer tekent de route | Tracé op de kaart, 0-zicht, 3D-blok, controles | Echte grond en bovengrond in 0-zicht en blok; boring als aanlegwijze |
| 5. Checken en varianten | Tracé wordt vaak gecontroleerd, alternatieven onderzocht | Eén tracé per project, controles | Meerdere varianten per project naast elkaar vergelijken |

## Informatie per gebied: wat bestaat en is bereikbaar
Getest vanaf de server op 11 nov 2026 (HTTP 200 = bereikbaar).

| Vraag | Bron | Toegang | Getest |
| --- | --- | --- | --- |
| Welke grond (diep) | GeoTOP 1.6.1 (TNO), voxels 100 × 100 × 0,5 m, lithoklasse + kans per klasse | OPeNDAP `https://www.dinodata.nl/opendap/GeoTOP/geotop.nc`, uitsnede per index | Ja, werkt |
| Welke grond (ondiep, tot 1,2 m) | BRO Bodemkaart (SGM) | PDOK | Nog niet |
| Bodemonderzoek in het verleden | BRO sonderingen (CPT), boringen (BHR-GT/-G/-P), milieuhygiënisch (SAD) | `https://publiek.broservices.nl/sr/cpt/v1/` | Bereikbaar, zoekvraag nog uitwerken |
| Maaiveldhoogte | AHN (dtm_05m, dsm_05m) | PDOK WCS `service.pdok.nl/rws/ahn/wcs/v1_0` | Ja, GeoTIFF |
| Wat ligt boven de grond | BGT (wegen, water, panden, bomen, kasten, putten) | PDOK OGC API `api.pdok.nl/lv/bgt/ogc/v1` | Ja |
| Gebouwen in 3D | 3D Basisvoorziening | PDOK 3D Tiles | Ja (al in het blok) |
| Wat ligt in de grond | KLIC (IMKL) | Alleen eigen graafmelding van de gebruiker, niet open | Importer nog te bouwen |
| Van wie is de grond | Kadastrale kaart (percelen, grenzen) | PDOK `api.pdok.nl/kadaster/brk-kadastrale-kaart/ogc/v1` | Ja |
| Wie is de eigenaar | BRK eigendomsinformatie | Kadaster, betaald per perceel | Niet open; niet zonder akkoord |
| Bestemming van de grond | Omgevingsplan / bestemmingsplan | DSO-API's, gratis API-key (header `x-api-key`) | Key nodig; aanvragen vraagt naam en organisatie |

Bron DSO-API-key: https://developer.omgevingswet.overheid.nl/formulieren/api-key-aanvragen-0/

## Aanlegwijze: ontgraving of gestuurde boring
- Ontwerpkaders: NEN 3650-serie en NEN 3651 (kruisingen met waterstaatswerken), Richtlijn
  Boortechnieken (Rijkswaterstaat), Kennisdocument sleufloze technieken (SIKB).
- Voor het 3D-beeld zijn per boring nodig: intrede- en uittredepunt, hoeken, boogstraal en diepste punt.
  Waarden nog uit de richtlijnen halen voordat ze in de controles komen.

## Realistisch 0-zicht en 3D-blok
Nu zijn grondlagen en bovengrond **voorbeelddata** (`kaart.laagdikten`, `kaart.voorbeeld_bovengrond`).
Echte vervanging, per bron:
1. Grondlagen: GeoTOP-uitsnede rond het tracé/blok (lithoklasse per 0,5 m), op de server opgehaald.
2. Maaiveld: AHN dtm_05m langs de doorsnede en over het blok.
3. Bovengrond in het 0-zicht: BGT-objecten die de doorsnede kruisen (weg, water, pand, boom).
4. Perceelgrenzen: kadastrale kaart op dezelfde doorsnede.

Beperking: GeoTOP is 100 m horizontaal en begint pas onder het maaiveld zoals TNO dat modelleert;
voor de bovenste meters zijn BRO-boringen/sonderingen en de Bodemkaart nauwkeuriger.
