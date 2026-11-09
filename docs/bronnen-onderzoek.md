# Bronnenonderzoek: data en controles voor leidingen (7 nov 2026)

Doel: welke data we per projectgebied inladen en waarop we controleren. Alles wordt per project
(getekend gebied, max. 10 × 10 km) opgehaald, nooit voor heel Nederland, en moet als KML te
exporteren zijn (dus met geometrie in WGS84 en diepte/NAP als attribuut).

## 1. KLIC (kabels en leidingen)
- KLIC is **niet open data**. Per graafmelding (Kadaster, € 10,50, met DigiD) komt een levering:
  leveringsbrief (PDF) + IMKL-bestand (GML in een zip) met de ligging van alle netten van alle
  netbeheerders in het aangevraagde gebied, plus contactgegevens per netbeheerder.
- De levering is bedoeld voor het graafwerk en is beperkt geldig (zolang de grond open is of er
  niets verandert). Wettelijk kader: WIBON en de Regeling informatie-uitwisseling ondergrondse netten.
- **Route voor GR0ND:** een IMKL-importer waarmee de gebruiker zijn eigen KLIC-levering in een
  project laadt (geen scrapen, geen opslaan buiten het project). Opslag en delen: vooraf juridisch
  nagaan (zie Open vragen).
- Daarnaast is er open hoofdnet-data (zie 2), geschikt als indicatie, niet als vervanging van KLIC.

## 2. Open data voor kabels en leidingen (indicatief)
| Bron | Inhoud | Toegang |
| --- | --- | --- |
| TenneT "Kabels en leidingen Tennet" (ArcGIS Online) | Hoogspanningslijnen en ondergrondse kabels 110–380 kV | ArcGIS Feature Service, geen gebruiksbeperking vermeld |
| Liander Open Data Elektra | Hoofdnet laag- en middenspanning, stations | ArcGIS, o.a. in de mapservice "Open Data Elektranet" |
| Stedin, Enexis, Enduris, Westland Infra | LS/MS-verbindingen en stations (grof) | ArcGIS-lagen, peildatum verschilt (bijv. Stedin 2023/2024) |
| REV / Provincie | Buisleidingen met extern veiligheidsrisico | ArcGIS Feature Service |
Let op: peildata en nauwkeurigheid verschillen; per laag tonen we bron en peildatum.

## 3. Ondergrond en bodem (PDOK, BRO)
- GeoTOP (voxels 100 × 100 × 0,5 m tot 50 m onder NAP): echte lagen per locatie voor het 0-zicht.
- BRO Bodemkaart (SGM, tot 1,2 m), Geomorfologische kaart, REGIS II (hydrogeologie).
- Boorgegevens: BRO Bodemkundig booronderzoek (BHR-P), Geologisch (BHR-G), Geotechnisch
  sondeeronderzoek (CPT), Geotechnisch booronderzoek (BHR-GT): "is er bodemonderzoek gedaan".
- Grondwater: Model grondwaterspiegeldiepte (WDM), monitoringputten (GMW).
- Verontreiniging: Milieuhygiënisch bodemonderzoek (SAD), Overheidsbesluit bodemverontreiniging (SLD).
- Toegang: PDOK WMS/WFS/OGC API en ATOM-downloads, open licentie.

## 4. Boven de grond
- BGT (wegen, water, terreinen), BAG (gebouwen), Kadastrale kaart (percelen, voor privé/openbaar).
- 3D BAG / 3D Basisvoorziening (gebouwhoogtes, LoD1.x) en AHN (maaiveldhoogte, WCS/WMS).
- Via PDOK OGC API / WFS met bbox-filter, dus per projectgebied op te halen.

## 5. Natuur, erfgoed, ruimte
- Natura 2000, Natuurnetwerk Nederland (NNN), Natuurmeting op kaart, Provinciale monumenten,
  Ruimtelijke plannen: PDOK, open.
- Soortgegevens (welke dieren, wanneer actief): NDFF is niet volledig open. Voorlopig tonen we
  generieke ecologische perioden (broedseizoen 15 maart–15 juli, winterslaap vleermuizen, enz.)
  plus een melding dat een ecologische quickscan nodig kan zijn.
- Archeologie (RCE, AMK/verwachtingenkaart): nog uitzoeken welke dienst open is.

## 6. Explosieven (NGE)
- Geen landelijke open bommenkaart gevonden. Wel per gemeente: Amsterdam (bommenkaart), Den Haag
  (open data), Eindhoven (open data blindgangers). Landelijk is een vooronderzoek door een
  gecertificeerd bedrijf (CS-NGE) de norm.
- Aanpak: gemeentelijke open data per projectgebied tonen waar beschikbaar; anders melding
  "vooronderzoek NGE nodig, geen open kaart beschikbaar".

## 7. Eerdere projecten
- Geen open landelijke bron gevonden. Mogelijkheden: Omgevingsloket/vergunningen (gemeenten),
  KLIC-meldingen zijn niet openbaar. Eerst eigen projecten van gebruikers zichtbaar maken.

## 8. Rekenregels uit de praktijk (voor de controles)
| Regel | Waarde | Bron |
| --- | --- | --- |
| Parallel leggen kabels/leidingen | min. 0,5 m | Netbeheer Nederland, uniforme aanwijzingen |
| Kruisen: verticale tussenruimte | min. 0,5 m (boring/persing), gemeente Delft 0,30 m bij open ontgraving; De Fryske Marren 0,20 m | NBN, handboeken gemeenten |
| Kruising sloot/open water: dekking | min. 1,0 m onder ontwerpdiepte/bodem | Handboek Delft 2025 |
| Mantelbuis bij wegkruising | 0,5 m voorbij de verharding | Handboek Delft 2025 |
| Zandbed onder rijbaan / fietspad / trottoir | 50 / 40 / 30 cm | Handboek Delft 2025 |
| Gronddekking handholes | min. 0,30 m | Handboek Delft 2025 |
| Heien, boren, sonderen nabij kabels | min. 2 m afstand | Netbeheer Nederland |
| Trillingen nabij brosse leidingen (gietijzer, AC) | binnen 10 m vooraf contact | Netbeheer Nederland |
| Verdichten naast de kabel | met de hand tot 0,2 m opzij en 0,4 m boven | Netbeheer Nederland |
| Schoon zand tussen kabel en puingranulaat | min. 0,3 m | Netbeheer Nederland |
| Bomen eerste grootte (≥ 12 m) | min. 2,5 m tot tracé | Handboek Den Helder 2014 |
| Vergunning/instemming aanvragen | min. 8 weken vooraf | Handboek Delft 2025 |
Regels verschillen per gemeente en beheerder. Daarom komt er een regelset per beheerder met bron
en jaartal; de standaardset in de app blijft "indicatief".

## 9. Open vragen
- Mag een KLIC-levering in een gedeeld GR0ND-project worden bewaard? (WIBON, voorwaarden Kadaster)
- Welke dienst levert archeologische verwachting open (RCE)?
- Welke ArcGIS-services zijn stabiel genoeg om rechtstreeks aan te roepen (eigenaren zijn
  individuele accounts)? Alternatief: de officiële open-data downloads van Liander/Stedin/Enexis.

## Bronnen
- Kadaster KLIC-melding: https://www.kadaster.nl/producten/woning/klic-melding
- Regeling informatie-uitwisseling ondergrondse netten: https://wetten.overheid.nl/BWBR0027409/2017-02-15/0
- PDOK datasets: https://www.pdok.nl/datasets
- 3D Basisvoorziening: https://www.pdok.nl/introductie/-/article/3d-basisvoorziening-1
- BRO GeoTOP: https://www.pdok.nl/introductie/-/article/bro-geotop-gtm-
- BRO Bodemkaart: https://www.pdok.nl/introductie/-/article/bro-bodemkaart-sgm-
- Netbeheer Nederland, uniforme aanwijzingen: https://www.netbeheernederland.nl/sites/default/files/Uniforme_aanwijzingen_werken_nabij_kabels___leidingen_259.pdf
- Handboek ondergrondse infrastructuur Delft: https://www.delft.nl/sites/default/files/2025-02/handboek-ondergrondse-infrastructuur.pdf
- TenneT Kabels en leidingen (ArcGIS): https://www.arcgis.com/home/item.html?id=264386a34f3a42ffbab696e40ae4d3d2
- Open Data Elektranet (ArcGIS): https://dpmc-gis.maps.arcgis.com/home/item.html?id=306fbc76117c4af994ec9ab613c0279c
- Bommenkaart Amsterdam: https://www.amsterdam.nl/wonen-bouwen-verbouwen/bodem/bommenkaart-amsterdam/
