"""Aanleg van een tracé: open ontgraving of gestuurde boring, en kruisingen met bestaande netten.

Alles is indicatief. Coördinaten in RD (meters), diepte positief naar beneden vanaf maaiveld.
Bronnen: Netbeheer Nederland (0,5 m tussenruimte), boring Heemstede (intrede 10°), praktijk.
"""

import math
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

Punt = tuple[float, float]

MIN_TUSSENRUIMTE_M = 0.5  # verticaal, bij kruisen met een bestaande kabel of leiding
PROFIEL_STAP_M = 2.0
SLEUF_EXTRA_M = 0.1  # de sleuf gaat iets dieper dan de kabel (zandbed)


class Wijze(StrEnum):
    ONTGRAVEN = "ontgraven"
    BORING = "boring"


class Aanleg(BaseModel):
    """Instellingen van de aanleg. Standaardwaarden zijn indicatief; de engineer past ze aan.

    shortcut: een boring gaat recht onder de intrede- en uittredehoek, zonder boogstraal.
    """

    model_config = ConfigDict(frozen=True)

    wijze: Wijze
    diepte: float = Field(1.2, ge=0.3, le=40)
    intrede_graden: float = Field(10.0, ge=3, le=45)
    uittrede_graden: float = Field(10.0, ge=3, le=45)
    sleuf_breedte: float = Field(0.6, ge=0.2, le=3)
    # graven ca. 100-150 m per werkdag, boren ca. 150 m
    snelheid_m_per_uur: float = Field(15.0, gt=0, le=500)
    # stukken (van, tot) in meters langs het tracé die geboord worden; de rest wordt gegraven
    boringen: list[tuple[float, float]] = Field(default_factory=list, max_length=50)
    boor_diepte: float = Field(4.0, ge=0.5, le=40)
    boor_snelheid_m_per_uur: float = Field(20.0, gt=0, le=500)


def boorstukken(lengte: float, aanleg: Aanleg) -> list[tuple[float, float]]:
    """De geboorde stukken, binnen het tracé en op volgorde. Bij wijze 'boring' het hele tracé."""
    if aanleg.wijze is Wijze.BORING:
        return [(0.0, lengte)]
    stukken = sorted(
        (max(0.0, a), min(lengte, b)) for a, b in aanleg.boringen if min(lengte, b) > max(0.0, a)
    )
    samen: list[tuple[float, float]] = []
    for a, b in stukken:  # overlappende boringen worden één boring
        if samen and a <= samen[-1][1]:
            samen[-1] = (samen[-1][0], max(samen[-1][1], b))
        else:
            samen.append((a, b))
    return samen


def boorlengte(lengte: float, aanleg: Aanleg) -> float:
    return sum(b - a for a, b in boorstukken(lengte, aanleg))


def duur_uren(lengte: float, aanleg: Aanleg) -> float:
    """Werkuren: graven en boren elk met hun eigen snelheid."""
    boren = boorlengte(lengte, aanleg)
    snelheid = (
        aanleg.snelheid_m_per_uur
        if aanleg.wijze is Wijze.BORING
        else aanleg.boor_snelheid_m_per_uur
    )
    return (lengte - boren) / aanleg.snelheid_m_per_uur + boren / snelheid


def grondverzet_m3(lengte: float, aanleg: Aanleg) -> float:
    """Uitgegraven grond bij ontgraven; een boring verzet (bijna) geen grond aan het maaiveld."""
    gegraven = lengte - boorlengte(lengte, aanleg)
    return gegraven * aanleg.sleuf_breedte * (aanleg.diepte + SLEUF_EXTRA_M)


def afstanden(punten: list[Punt]) -> list[float]:
    """Afstand langs het tracé tot elk knikpunt."""
    uit = [0.0]
    for (x0, y0), (x1, y1) in zip(punten, punten[1:], strict=False):
        uit.append(uit[-1] + math.hypot(x1 - x0, y1 - y0))
    return uit


def diepte_op(s: float, lengte: float, aanleg: Aanleg) -> float:
    """Diepte van de nieuwe leiding op afstand s. Een boring gaat schuin de grond in en weer uit."""
    for a, b in boorstukken(lengte, aanleg):
        if a <= s <= b:
            diepte = aanleg.diepte if aanleg.wijze is Wijze.BORING else aanleg.boor_diepte
            erin = (s - a) * math.tan(math.radians(aanleg.intrede_graden))
            eruit = (b - s) * math.tan(math.radians(aanleg.uittrede_graden))
            return max(0.0, min(diepte, erin, eruit))
    return aanleg.diepte


def plek_op(punten: list[Punt], langs: list[float], s: float) -> Punt:
    """Het punt op afstand s langs het tracé."""
    for i in range(1, len(punten)):
        if s <= langs[i] or i == len(punten) - 1:
            t = (s - langs[i - 1]) / max(langs[i] - langs[i - 1], 1e-9)
            (x0, y0), (x1, y1) = punten[i - 1], punten[i]
            return x0 + t * (x1 - x0), y0 + t * (y1 - y0)
    return punten[0]


def profiel(punten: list[Punt], aanleg: Aanleg) -> list[list[float]]:
    """Punten [x, y, diepte] van de nieuwe leiding; bij een boring om de PROFIEL_STAP_M."""
    langs = afstanden(punten)
    lengte = langs[-1]
    stappen = {0.0, lengte, *langs}
    for a, b in boorstukken(lengte, aanleg):
        # net buiten de boring ligt de sleuf weer op graafdiepte: daar ook een punt
        stappen |= {a, b, max(0.0, a - 0.01), min(lengte, b + 0.01)}
        stappen |= {a + i * PROFIEL_STAP_M for i in range(int((b - a) / PROFIEL_STAP_M) + 1)}
    uit = []
    for s in sorted(stappen):
        x, y = plek_op(punten, langs, s)
        uit.append([round(x, 2), round(y, 2), round(diepte_op(s, lengte, aanleg), 2)])
    return uit


def snijpunt(a: Punt, b: Punt, c: Punt, d: Punt) -> tuple[float, float] | None:
    """Fracties (t langs ab, u langs cd) waar lijnstuk ab en cd elkaar snijden, anders None."""
    rx, ry = b[0] - a[0], b[1] - a[1]
    sx, sy = d[0] - c[0], d[1] - c[1]
    noemer = rx * sy - ry * sx
    if abs(noemer) < 1e-12:
        return None  # evenwijdig
    qx, qy = c[0] - a[0], c[1] - a[1]
    t = (qx * sy - qy * sx) / noemer
    u = (qx * ry - qy * rx) / noemer
    return (t, u) if 0 <= t <= 1 and 0 <= u <= 1 else None


def kruisingen(
    punten: list[Punt], aanleg: Aanleg, lagen: list[dict], soorten: dict[str, dict]
) -> list[dict]:
    """Elke plek waar het tracé een bestaande lijn kruist, met de verticale tussenruimte."""
    langs = afstanden(punten)
    uit = []
    for laag in lagen:
        kabel_diepte = soorten[laag["soort"]]["diepte_m"]
        for lijn in laag["lijnen"]:
            for i in range(len(punten) - 1):
                for c, d in zip(lijn, lijn[1:], strict=False):
                    raak = snijpunt(punten[i], punten[i + 1], tuple(c), tuple(d))
                    if raak is None:
                        continue
                    s = langs[i] + raak[0] * (langs[i + 1] - langs[i])
                    nieuw = diepte_op(s, langs[-1], aanleg)
                    ruimte = abs(nieuw - kabel_diepte)
                    x, y = plek_op(punten, langs, s)
                    uit.append({
                        "x": round(x, 2), "y": round(y, 2), "s": round(s, 1),
                        "soort": laag["soort"], "beheerder": laag["beheerder"],
                        "kabel_diepte": kabel_diepte, "nieuw_diepte": round(nieuw, 2),
                        "tussenruimte": round(ruimte, 2), "ok": ruimte >= MIN_TUSSENRUIMTE_M,
                    })  # fmt: skip
    return sorted(uit, key=lambda k: k["s"])


def geojson(
    naam: str, profiel_ll: list[list[float]], aanleg: Aanleg, uitkomst: dict, kruisingen_ll: list
) -> dict:
    """Tracé en kruisingen als GeoJSON (WGS84). Diepte per hoekpunt staat in de eigenschappen."""
    hoekpunten = [[lon, lat] for lon, lat, _ in profiel_ll]
    lijn = {
        "type": "Feature",
        "geometry": {"type": "LineString", "coordinates": hoekpunten},
        "properties": {
            "naam": naam, **aanleg.model_dump(mode="json"), **uitkomst,
            "diepte_per_punt_m": [d for *_, d in profiel_ll],
            "let_op": "Indicatief ontwerp; diepte onder maaiveld. Geen vervanging van KLIC.",
        },
    }  # fmt: skip
    punten = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {"soort": "kruising", **k},
        }
        for (lon, lat), k in kruisingen_ll
    ]
    return {"type": "FeatureCollection", "features": [lijn, *punten]}
