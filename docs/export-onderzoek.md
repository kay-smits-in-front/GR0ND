# GR0ND: exportformaten en geolocatie (onderzoek, 5 november 2026)

## Conclusie

1. **Geen eigen 3D-bestandstype bouwen.** Niemand kan het openen, jij moet alle lees- en schrijfsoftware onderhouden, en het botst met "hoe universeler hoe beter". Een eigen formaat lost alleen iets op als geen bestaand formaat de data kan dragen. Dat is hier niet zo.
2. **Eén intern model, meerdere exports.** In PostGIS bewaren we elke kabel als hartlijn met Z, plus diameter, materiaal en bedekking. Alle exportformaten worden daaruit gegenereerd. De echte "buis op ware grootte" ontstaat pas bij het exporteren of renderen (hartlijn + diameter wordt een buis).
3. **Eén coördinatenstelsel intern: EPSG:7415** (RD + NAP-hoogte, meters). Bij export naar Google of web wordt getransformeerd naar WGS 84.
4. **Exportvolgorde:** eerst GeoPackage (ArcGIS, QGIS), dan KML/KMZ (Google Earth), daarna glTF/GLB voor echte 3D-buizen. IFC en IMKL pas als er een concrete vraag is.

## Coördinaten: waar het misgaat

- Nederland gebruikt RD (EPSG:28992) voor positie en NAP (EPSG:5709) voor hoogte. De samenstelling is EPSG:7415, in meters, voor heel Nederland inclusief offshore. [spatialreference.org]
- KML kent alleen WGS 84. GeoJSON gaat uit van WGS 84 (EPSG:4326). [Studio Matrx]
- Dus elke export naar Google of web vraagt een transformatie. Het traject klopt alleen als die transformatie nauwkeurig is. Dit moet getest worden met pyproj en de officiële RDNAPTRANS-rasterbestanden; zonder raster kan de afwijking meters zijn (eigen kennis, nog niet gecontroleerd).
- Afspraak: Z is altijd NAP in meters. Diepte onder maaiveld = maaiveldhoogte NAP min Z.
- Testeis voor elke export: hoofdpunten heen en terug transformeren (RD naar WGS 84 naar RD) binnen een vaste marge in centimeters.

## Vergelijking

| Formaat | 3D | Voordelen | Nadelen | Rol in GR0ND |
|---|---|---|---|---|
| **GeoPackage** | Z-waarden ja; solids en surfaces niet [FME] | Eén bestand, volledige veldnamen, meerdere lagen, open OGC-standaard, QGIS eerste klas, ArcGIS Pro exporteert ernaar [Studio Matrx] | Geen echte buisvorm: hartlijn plus diameter als attribuut | **Hoofdexport voor GIS** |
| **GeoJSON** | Z in coördinaten mogelijk | Eén leesbaar tekstbestand, werkt in webkaarten | Alleen WGS 84, groot bij veel data [Studio Matrx] | Alleen voor web-API |
| **Shapefile** | Beperkt | Bijna overal leesbaar | Meerdere bestanden, veldnamen max. 10 tekens, 2 GB, één geometrietype per bestand [Studio Matrx] | Alleen op verzoek, voor oude software |
| **KML/KMZ** | Ja, met hoogtemodus | Opent in Google Earth, goed voor presentaties | Alleen WGS 84. In absolute modus kan geometrie onder het maaiveld liggen, maar is dan verborgen [Google KML-docs] | **Export voor Google Earth** |
| **glTF/GLB** | Volledige 3D-meshes | ArcGIS Pro importeert het (Import 3D Objects) [Esri]; buizen op ware grootte mogelijk | Georeferentie moet apart goed worden meegegeven; modellen zonder coördinatenstelsel komen in Web Mercator terecht [Esri] | **Export voor visuele 3D** |
| **3D Tiles** | Gestreamde 3D | ArcGIS Pro 3.2 laadt 3D Tiles; Esri zet 3D Tiles ook in ArcGIS Online en Enterprise [Esri-persbericht] | Zwaarder om te genereren; nuttig bij grote gebieden | Later, voor de kaart zelf |
| **IFC 4.3** | Ja | Standaard voor BIM; voegt alignments en infrastructuur toe [Trimble] | Het artikel noemt leidingen en kabels niet; tunnels pas in 4.4; leveranciersbron [Trimble] | Pas bij vraag van bouwbedrijven |
| **CityJSON-utility-extensie** | Ja | Gebaseerd op de CityGML Utility Network ADE [GitHub] | Maker zegt: "niet gebruiken in productie" [GitHub] | Niet gebruiken |
| **IMKL (GML)** | Niet vastgesteld | Nederlands informatiemodel voor kabels en leidingen, gebouwd op INSPIRE Utility Networks [wetransform] | Pagina noemt geen Z-ondersteuning; niet verder onderzocht | Later onderzoeken voor uitwisseling met KLIC |
| **PDF** | Nee | Iedereen kan het openen | Geen betrouwbare locatie in standaard-PDF (zoals jij zei); georeferentie-extensies bestaan maar zijn niet gecontroleerd | Alleen als rapport, niet als dataformaat |
| **Eigen formaat** | Alles wat je wilt | Volledige controle | Geen enkele tool leest het; onderhoud voor altijd; botst met "universeel" | **Niet doen** |

## Eisen voor het exportsysteem

- Exports lopen via één functie per formaat, met dezelfde invoer: een selectie (gebied of lijst kabels) en het doelcoördinatenstelsel.
- Elke export draagt bronvermelding, versie van de data en het gebruikte coördinatenstelsel mee.
- Wie mag exporteren, hangt af van het pakket (zie hieronder). Eigen geüploade data mag de gebruiker altijd terug exporteren.

## Betaalmuur en pakketten (nieuwe eisen)

- Kijkpakket: €0,99 per maand (bedrag nog te bevestigen: je schreef "0,99 cent").
- Ontwerp- en data-pakket (uitgebreid): €14,99 per maand.
- Demo: 6 uur toegang tot het hele systeem voor €0,99.
- Later: adviespakket, totaalpakket met begeleiding van In-front, bedrijfspakket.
- Ontwerpregel: pakketten zijn gegevens in de database (naam, prijs, periode, rechten), niet vastgelegd in code. Dan kunnen pakketten wijzigen zonder aanpassing van de app.
- Rechten worden per functie gecontroleerd, bijvoorbeeld `export_gpkg` of `kabel_tekenen`.

## Niet gecontroleerd

- Nauwkeurigheid van RD-naar-WGS 84 zonder rasterbestanden.
- Hoe Google Maps zelf met KML en hoogte omgaat. De Google KML-documentatie gaat over Google Earth.
- Georeferentie in PDF (GeoPDF).
- OGC 3D Tiles-specificatie zelf: die pagina was niet bereikbaar. Wat hier staat komt uit het Esri-persbericht.
- IFC voor leidingen en kabels: de bron noemt ze niet.
- IMKL: ondersteuning voor diepte.

## Bronnen

- [spatialreference.org: EPSG:7415](https://spatialreference.org/ref/epsg/7415/)
- [Studio Matrx: spatial data formats](https://www.studiomatrx.org/students/gis-for-architecture-planning-urban-design/spatial-data-formats)
- [FME: GeoPackage quick facts](https://docs.safe.com/fme/2019.2/html/FME_Desktop_Documentation/FME_ReadersWriters/geopackage/quick_facts_geopackage.htm)
- [Google: KML altitude modes](https://developers.google.cn/kml/documentation/altitudemode)
- [Esri: Import 3D Objects](https://doc.esri.com/en/arcgis-pro/latest/tool-reference/data-management/import-3d-objects.html)
- [Esri: 3D Tiles in ArcGIS (persbericht)](https://stocks.observer-reporter.com/observerreporter/article/bizwire-2023-11-8-esri-integrates-3d-tiles-into-the-arcgis-system-of-record-enhancing-3d-gis-workflows)
- [Trimble: IFC 4.3 voor infrastructuur](https://www.trimble.com/blog/construction/en-US/article/adopting-ifc-4-3-for-infrastructure-projects)
- [GitHub: cjutilitynetwork](https://github.com/idiap/cjutilitynetwork)
- [wetransform: IMKL2015](https://inspire-extensions.wetransform.to/models/2016/04/23/imkl2015.html)
