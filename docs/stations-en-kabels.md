# Transformatorstations en kabels (onderzoek, 5 november 2026)

Doel: een bibliotheek van 3D-modellen (nep-3D met plaatjes) van de stations en kabels die gebruikers kunnen plaatsen, met een uitklapbaar paneel per type.

## Wat niet gevonden is

- **De nummers 180 / 220 / 430** komen in geen enkele bron voor. Stations worden in de bronnen aangeduid met kVA (250, 400, 630, hoger). Ik vermoed dat je dit bedoelt, maar dat is een gok. Controleer het bij Liander of Enexis voordat het in de app komt.
- **Welk model "het nieuwste" is** is niet vastgesteld. De bronnen laten alleen zien welke typen bestaan.
- **Kabelkleuren**: geen betrouwbare bron gevonden (de zoekresultaten waren forumberichten).
- **Foto's van de binnenkant van een kabel**: bronnen leveren geen bruikbare afbeeldingen. De Google-afbeeldingenlink kon ik niet gebruiken. Plan: eigen doorsnede-tekeningen (SVG) op schaal uit de gevonden diameters.
- **Of loodkabels "altijd vervangen moeten worden"**: geen bron gevonden die dat zo stelt.

## Transformatorstations (de huisjes)

| Type | Gegevens | Bron |
|---|---|---|
| Compactstation 250 kVA (ZPUE) | 3000 × 1650 × 2400 mm (l × b × h); beton B30, aluminium deuren; trafo 10/0,42 kV, giethars, Dyn5; drie ruimtes: LS, MS, trafo. De offerte noemt ook "400 kVA", dus tegenstrijdig | [offerte-tekening](https://repository.officiele-overheidspublicaties.nl/Bijlagen/TerInzageLegging/2023/til-2023-14466/1/bijlage/BK_tekeningen_transformatorhuisje-A.pdf) |
| Compactstation 630 kVA (Alfen Diabolo 20H) | Standaardversie met gescheiden MS- en LS-ruimte; 400 kVA-variant als optie; totaalgewicht ca. 8.600 kg (omhulsel 5.900, trafo 1.900); IEC 62271-202; afmetingen niet leesbaar | [tekening](https://repository.officiele-overheidspublicaties.nl/externebijlagen/exb-2020-13892/currentItem) |
| Diabolo-reeks | 250 tot 3.500 kVA, geprefabriceerd beton, lichtgrijs met anti-graffiticoating, verwijderbaar dak, geïntegreerde olieopvang | [Alfen](https://alfen.com/en/smart-grids/compact-station/diabolo) |
| Klein compactstation | ca. 2 × 1,8 m, 1,7 m hoog | [Schagen](https://raad.schagen.nl/Documenten/106b-Bijlage-Transformatorstation-Sint-Maartensweg-vastgesteld-Toelichting.pdf) |
| Gemeentelijke grens voor nieuwe huisjes (Aalsmeer) | max. 25 m² inclusief groen, 2 m hoog | [Nieuws in Aalsmeer](https://nieuwsinaalsmeer.nl/weerstand-transformatorhuisjes.php) |

Spanningen: middenspanning is in Nederland meestal ca. 10 kV (ook 13, 20 en 23 kV genoemd); laagspanning is onder 1.000 V, met 230 V voor woningen en vaak 420 V voor bedrijven [Voltens](https://voltens.nl/blog/wat-gebeurt-er-in-een-transformatorstation/). Dat past bij de 10/0,42 kV van de trafo hierboven.

Waarom grotere stations: toenemende vraag door energietransitie, zonnepanelen en elektrische auto's. Enexis plaatst duizenden nieuwe trafo's en verzwaart vele duizenden bestaande [Solar Magazine](https://solarmagazine.nl/nieuws-zonne-energie/i34842/primeur-sappemeer-enexis-start-wijkgerichte-aanpak-verzwaren-laagspanningsnet). Liander noemt ca. 20.000 transformatorhuisjes in Noord-Holland (Aalsmeer-artikel hierboven).

Grote stations (niet voor de eerste bibliotheek): regelstations (20 naar 10 kV) en transportverdeelstations van Enexis, een modulair TV(R)S-station met bouwtijd van 4 maanden in plaats van 1 tot 1,5 jaar [Enexis](https://www.enexis.nl/over-ons/wat-doen-wij/elektriciteitsstations/middenspanningsstations), [Solar Magazine](https://solarmagazine.nl/nieuws-zonne-energie/i39437/enexis-kan-door-nieuwe-aanpak-jaarlijks-ruim-10-keer-zo-veel-stroomstations-bouwen). De oppervlaktegetallen op de Enexis-pagina kloppen niet met de genoemde maten, dus die neem ik niet over.

## Kabels

| Soort | Types en doorsneden | Bron |
|---|---|---|
| Middenspanning, papier-lood (GPLK) | 3-aderig, aluminium of koper, 25 tot 240 mm², 8/10 en 10/10 kV | [Phase to Phase](https://phasetophase.nl/wp-content/uploads/2024/04/afleidingkabelparameters.pdf) |
| Middenspanning, XLPE eenader, aluminium | 6/10 kV: 50, 95, 150, 240, 400, 630 mm²; 12/20 kV: 95 tot 630; 18/30 kV: 150 tot 630 | idem |
| Middenspanning, XLPE drieaderig, koper | 6/10 kV: 50, 95, 150, 240 mm² | idem |
| Laagspanning, kunststof (Alkudia, 750 V) | 4-aderig: 16, 50, 95, 150 mm² | idem |
| Laagspanning, papier-lood in de praktijk | Hoofdkabel 4 × 16 Cu (GPLK) op een Alliander-tekening | [Alliander](https://repository.officiele-overheidspublicaties.nl/externebijlagen/exb-2021-76209/currentItem) |

Buitendiameters (voorbeeld: eenader aluminium XLPE 6/10 kV, datasheet van een Duitse fabrikant, dus indicatief voor Nederland): 50 mm² = 25 mm, 95 = 29, 150 = 31, 240 = 36, 400 = 41, 630 = 49 [datasheet](https://waskoenig.de/download/0076?locale=nl). De samenvatting van de datasheet noemt geen scherm, wat vrijwel zeker een leesfout is; controleer de opbouw voordat de doorsnede-tekening wordt gemaakt. Je opmerking dat het "per millimeter" gaat klopt in zoverre dat de diameter per doorsnede verschilt, maar de aanduiding in de bronnen is de doorsnede in mm², niet de buitendiameter.

Loodkabels: GPLK ligt nog in de grond. Op een KPN-overzicht zijn dat 3 × 300 GPLK van ca. 40 tot 60 mm en 200DA GPLK van ca. 30 mm, samen in stalen buizen van 110 tot 160 mm [bron](https://repository.officiele-overheidspublicaties.nl/externebijlagen/exb-2019-17739/currentItem). Meerdere kabels per buis komt dus voor.

Kabelleveranciers van Alliander: Prysmian (middenspanning en laagspanning, XLPE en P-Laser) en TKH [Prysmian](https://www.prysmian.com/en/media/press-releases/prysmian-wins-a-framework-agreement-from-alliander-to-strengthen-the-dutch-power-grid).

## Diepte en afstanden (voor de checklist en de rode waarschuwing)

| Regel | Waarde | Bron |
|---|---|---|
| Standaarddekking laagspanning | 60 cm | [Stedin](https://www.stedin.net/-/media/project/online/files/aansluiting/stedin-richtlijnen-kabels-en-leidingen.pdf) |
| Standaarddekking middenspanning, gas, datakabels | 80 cm | idem |
| Maximale diepte voordat Stedin ingrijpt | zand en klei 120 cm, veen 100 cm, sterk zakkend veen 80 cm | idem |
| Grond ophogen bij minder dan | 40 cm dekking | idem |
| Gasleiding tot bebouwing | 1,00 m | idem |
| Bomen tot kabelroute (hart stam tot rand) | min. 2,5 m; struiken min. 1 m | idem |
| Kruisen en parallel leggen | min. 0,5 m; kruisen altijd onder de bestaande kabel door | [Netbeheer Nederland](https://www.netbeheernederland.nl/sites/default/files/Uniforme_aanwijzingen_werken_nabij_kabels___leidingen_259.pdf) |
| Heien, boren, sonderen | min. 2 m afstand | idem |
| Kasten en stations (kranen, hekken, materiaal) | min. 1 m | idem |
| Aanvullen | handmatig binnen 0,2 m naast en 0,4 m boven de kabel, lagen van max. 0,3 m | idem |

Stedin-waarden gelden voor Stedin. Andere netbeheerders kunnen andere waarden hanteren.

## Voor het datamodel

Eén tabel `asset_typen` met: soort (station of kabel), naam, spanningsniveau, vermogen (kVA) of doorsnede (mm²), buitendiameter (mm), afmetingen, materiaal, afbeelding. Gebruikers plaatsen een exemplaar; de bibliotheek blijft apart. Dan kan een klein station later door een groter worden vervangen zonder dat de oude gegevens verloren gaan.

## Verzadiging

De derde onderzoeksronde leverde vooral herhaling en kleine details op. Wat nog open is (de nummering van de huisjes, kabelkleuren, echte foto's) staat niet in publiek vindbare bronnen die ik kon bereiken. Een kabelcatalogus van een fabrikant (Prysmian, TKH) of een netbeheerder zou die gaten dichten. Als je zo'n document hebt, kun je het hier toevoegen.
