# Onderzoek: realistisch 3D-blok (nov 2026)

Doel: het blok en het 0-zicht niet uit een nep-vlak laten bestaan, maar uit echte Nederlandse 3D-data,
waar je doorheen kunt bewegen. Geverifieerd via Firecrawl (de sandbox bereikt PDOK zelf niet).

## Boven de grond: PDOK 3D Basisvoorziening (CC BY 4.0)
API: `https://api.pdok.nl/kadaster/3d-basisvoorziening/ogc/v1`

| Collectie | Inhoud | Formaat |
|---|---|---|
| `gebouwen` | alle panden, BAG-geometrie, LoD 2.2 (waar geen AHN is LoD 1.3) | 3D Tiles 1.1, glb-tegels (`3DTILES_content_gltf`) |
| `terreinen` | BGT-vlakken (weg, water, begroeid, onbegroeid) op AHN-hoogte | 3D Tiles |
| `digitaalterreinmodel` | maaiveld van heel NL (AHN) | Quantized Mesh |
| `digitaaloppervlaktemodel_8cm/_20cm` | puntenwolk incl. bomen en objecten | LAZ per kaartblad |
| `basisbestand_gebouwen(_terreinen)` | 3D-objecten met attributen | CityJSON (IFC-converter beschikbaar) |

- Tileset: `.../collections/gebouwen/3dtiles?f=json` (en `terreinen`). Root heeft een regio-boundingvolume en een
  ECEF-transform; subtilesets (`tileset-5-64-192.json`) en glb-tegels (`t/4/64/128.glb`) laden per zicht.
- Bomen zitten niet in de tiles: die komen uit het DSM (puntenwolk) of de BGT (begroeid terrein) en blijven te modelleren.

## Onder de grond: GeoTOP (TNO / BRO)
- Voxelmodel 100 × 100 m horizontaal, 0,5 m verticaal, tot 50 m onder NAP, met lithoklasse en kans per klasse.
- Programmatisch: NetCDF via TNO's OPeNDAP-server `http://dinodata.nl/opendap` (alleen http: dus via onze server,
  niet rechtstreeks uit de browser). OPeNDAP laat toe om een uitsnede te halen in plaats van het hele model.
- Let op: hoogte is in NAP. Op de Veluwe ligt maaiveld ver boven NAP, dus "50 m onder maaiveld" is daar niet gedekt.
- Horizontale resolutie 100 m is grof voor een leiding op 1,2 m diepte. Lokale grond vraagt BRO-boringen/sonderingen.

## Renderen
- `3d-tiles-renderer` (NASA-AMMOS, Apache-2.0) laadt 3D Tiles in three.js, Babylon en PlayCanvas.
- GeoTOP-voxels: instanced kubussen of een mesh per laag, op de server samengesteld uit de NetCDF-uitsnede.

## Beoordeling van de genoemde hulpmiddelen
- **three.js + 3d-tiles-renderer** (wat we al gebruiken): past, geen extra engine, werkt in de browser, open source.
- **PlayCanvas**: kan dezelfde tiles laden, maar levert nu alleen een andere engine + editor; geen extra data.
- **Unity** (Cesium for Unity): zwaar, aparte build, niet open web; alleen zinvol voor een aparte desktop-app.
- **AutoCAD**: geen live verbinding vanuit de browser. Wel een exportdoel (DXF/IFC via CityJSON).
- **Meshy**: genereert losse 3D-modellen (boom, huis), geen geodata. Alleen nuttig voor stijlvolle props.
