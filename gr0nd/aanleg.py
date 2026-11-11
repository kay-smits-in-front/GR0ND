"""Aanleg van een tracé: open ontgraving of gestuurde boring, en kruisingen met bestaande netten.

Alles is indicatief. Coördinaten in RD (meters), diepte positief naar beneden vanaf maaiveld.
Bronnen: Netbeheer Nederland (0,5 m tussenruimte bij kruisen), boringen Heemstede (intrede 10°).
"""

import math
from enum import StrEnum

Punt = tuple[float, float]

MIN_TUSSENRUIMTE_M = 0.5  # verticaal, bij kruisen met een bestaande kabel of leiding
# shortcut: rechte intrede en uittrede zonder boogstraal; boog toevoegen als het boorplan dat vraagt
INTREDE_GRADEN = 10.0
UITTREDE_GRADEN = 10.0
PROFIEL_STAP_M = 2.0


class Wijze(StrEnum):
    ONTGRAVEN = "ontgraven"
    BORING = "boring"


def afstanden(punten: list[Punt]) -> list[float]:
    """Afstand langs het tracé tot elk knikpunt."""
    uit = [0.0]
    for (x0, y0), (x1, y1) in zip(punten, punten[1:], strict=False):
        uit.append(uit[-1] + math.hypot(x1 - x0, y1 - y0))
    return uit


def diepte_op(s: float, lengte: float, wijze: Wijze, diepte: float) -> float:
    """Diepte van de nieuwe leiding op afstand s. Een boring gaat schuin de grond in en weer uit."""
    if wijze is Wijze.ONTGRAVEN:
        return diepte
    erin = s * math.tan(math.radians(INTREDE_GRADEN))
    eruit = (lengte - s) * math.tan(math.radians(UITTREDE_GRADEN))
    return max(0.0, min(diepte, erin, eruit))


def plek_op(punten: list[Punt], langs: list[float], s: float) -> Punt:
    """Het punt op afstand s langs het tracé."""
    for i in range(1, len(punten)):
        if s <= langs[i] or i == len(punten) - 1:
            t = (s - langs[i - 1]) / max(langs[i] - langs[i - 1], 1e-9)
            (x0, y0), (x1, y1) = punten[i - 1], punten[i]
            return x0 + t * (x1 - x0), y0 + t * (y1 - y0)
    return punten[0]


def profiel(punten: list[Punt], wijze: Wijze, diepte: float) -> list[list[float]]:
    """Punten [x, y, diepte] van de nieuwe leiding; bij een boring om de PROFIEL_STAP_M."""
    langs = afstanden(punten)
    lengte = langs[-1]
    stappen = {0.0, lengte, *langs}
    if wijze is Wijze.BORING:
        stappen |= {i * PROFIEL_STAP_M for i in range(int(lengte / PROFIEL_STAP_M) + 1)}
    uit = []
    for s in sorted(stappen):
        x, y = plek_op(punten, langs, s)
        uit.append([round(x, 2), round(y, 2), round(diepte_op(s, lengte, wijze, diepte), 2)])
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
    punten: list[Punt], wijze: Wijze, diepte: float, lagen: list[dict], soorten: dict[str, dict]
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
                    nieuw = diepte_op(s, langs[-1], wijze, diepte)
                    ruimte = abs(nieuw - kabel_diepte)
                    x, y = plek_op(punten, langs, s)
                    uit.append({
                        "x": round(x, 2), "y": round(y, 2), "s": round(s, 1),
                        "soort": laag["soort"], "beheerder": laag["beheerder"],
                        "kabel_diepte": kabel_diepte, "nieuw_diepte": round(nieuw, 2),
                        "tussenruimte": round(ruimte, 2), "ok": ruimte >= MIN_TUSSENRUIMTE_M,
                    })  # fmt: skip
    return sorted(uit, key=lambda k: k["s"])
