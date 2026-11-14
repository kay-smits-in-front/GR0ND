# Eisen van de opdrachtgever (14 november 2026)

Bron: gesprek met de opdrachtgever, doorgegeven door Kay. Dit document legt de eisen vast en zet ze
naast wat GR0ND nu kan. Status: **er** = werkt, **deels** = begin aanwezig, **niet** = nog niet gebouwd.

## Uitgangspunt

De engineer houdt de controle en het inzicht. GR0ND beslist niet, maar laat zien waar je rekening mee
moet houden, op elk punt waar je boort, graaft of iets kruist. Nu is dat inzicht "lijntjes op een
kaart"; het moet de echte situatie worden waarin je lijnen trekt. Liever nu te veel informatie dan te
weinig; ordenen komt later.

## Eisen en status

| # | Eis | Status | Wat er is / wat ontbreekt |
|---|-----|--------|---------------------------|
| 1 | 3D-gebied kiezen zonder tracé | er | Blok opent zodra een gebied is gekozen; tracé is niet nodig. |
| 2 | In het 3D-gebied tekenen of erdoorheen lopen | deels | Lopen langs een bestaand tracé werkt. Tekenen in het blok zelf ontbreekt. |
| 3 | Gestuurde boring ontwerpen (intrede, uittrede, diepte, boogstraal) | niet | Leiding heeft nu één vaste diepte. Een boorprofiel met diepte per meter ontbreekt. |
| 4 | Open ontgraving (sleuf) ontwerpen | niet | Geen onderscheid tussen boren en graven per tracédeel. |
| 5 | Door beton/verharding snijden | niet | Verhardingstype per punt ontbreekt (komt uit BGT). |
| 6 | Onder water, spoor en weg door | deels | Sloot en weg zitten in de controles, op voorbeelddata. Spoor ontbreekt. |
| 7 | Weg nooit schuin kruisen: haaks of parallel | niet | Kruisingshoek wordt niet gecontroleerd. Vereist echte weggeometrie (BGT). |
| 8 | Per punt: wat kruis ik en waar moet ik op letten | deels | Checklist en meldingen bestaan, op voorbeelddata. |
| 9 | Privégrond of openbaar; vergunning nodig | niet | Kadastrale percelen (PDOK BRK) ontbreken. Eigenaarsnamen zijn niet openbaar. |
| 10 | KLIC-levering inladen en meewegen | niet | Importer voor de KLIC-zip (GML volgens IMKL) ontbreekt. |
| 11 | KLIC-leidingen zichtbaar in 3D | niet | Volgt op 10. KLIC geeft meestal geen diepte: diepte is dan een aanname en zo gelabeld. |
| 12 | Proefsleuf inladen voor de echte ligging | niet | Meetpunten (x, y, diepte) die een KLIC-leiding corrigeren. |
| 13 | Bestemmings-/omgevingsplan van de gemeente | niet | Bron te onderzoeken (Omgevingswet, Ruimtelijke Plannen). |
| 14 | Algemene gemeentedata die van toepassing is | niet | Per gemeente verschillend; eerst bepalen welke data. |
| 15 | Natuur: waarschuwing voor regels, broedseizoen, soorten | niet | Natura 2000 en NNN zijn open (PDOK). Soortgegevens (NDFF) zijn betaald. Eerst een algemene seizoenswaarschuwing. |
| 16 | Kennisbank: per onderwerp een bron of plugin | deels | Kaartlagen zijn per bron gedefinieerd (`KaartLaag`). Een vaste vorm voor nieuwe bronnen ontbreekt. |
| 17 | Export naar AutoCAD en ArcGIS | deels | KML-export werkt (ArcGIS leest KML). AutoCAD werkt met DXF/DWG: DXF-export ontbreekt. |
| 18 | Zelfde symbolen als AutoCAD | niet | Eerst vaststellen welke symbolenset de engineers gebruiken (NLCS ligt voor de hand). |
| 19 | 3D-kabels tekenen | deels | Leiding als buis in het blok langs het tracé. Vrij tekenen in 3D ontbreekt. |
| 20 | 3D-kasten: welk type staat er, welk type komt er, waar | niet | Kasttypen en plaatsing ontbreken. Onderzoek staat in `stations-en-kabels.md`. |
| 21 | Alle TenneT-stations in kaart | niet | Open data van TenneT te onderzoeken en als laag toe te voegen. |

## Voorgestelde volgorde

Elke stap levert iets wat de engineer kan gebruiken en de volgende stap nodig heeft.

1. **Echte bovengrond (BGT)** langs tracé en in het gebied: weg, water, spoor, verharding, pand.
   Maakt 5, 6, 7 en 8 mogelijk op echte data.
2. **Tracédelen met methode**: per deel open ontgraving of gestuurde boring, met boorprofiel
   (3, 4) en de regel haaks of parallel (7).
3. **KLIC-import** en tonen in kaart, 0-zicht en blok (10, 11), daarna **proefsleuf** (12).
4. **Percelen en natuur** als lagen met waarschuwingen per punt (9, 15), daarna gemeente (13, 14).
5. **DXF-export** met vaste symbolen (17, 18).
6. **Kasten en stations** (20, 21) en vrij tekenen in 3D (2, 19).

## Open vragen aan de opdrachtgever

- Welke symbolenset en welke AutoCAD-variant (gewoon, Civil 3D, Map 3D) gebruiken de engineers?
- Welke regels gelden voor een gestuurde boring (minimale boogstraal, dekking onder weg, water, spoor)?
  Zonder die waarden worden de controles voorbeeldwaarden en zo gelabeld.
- Kunnen we een echte (geanonimiseerde) KLIC-levering en een proefsleufrapport krijgen om mee te testen?
- Wat hoort bij "algemene gemeentedata"?
