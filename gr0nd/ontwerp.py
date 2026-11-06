"""Ontwerp in het 0-zicht: leidingtypen, bestaande leidingen, controles en checklist.

Een leiding is in het 0-zicht een cirkel op positie (u, diepte): u is de afstand haaks op het
tracé, diepte is de afstand van het maaiveld tot het hart van de leiding (positief naar beneden).
De leiding loopt langs het hele tracé op die positie.

De drempelwaarden komen uit de richtlijn van Stedin (dekking) en de Uniforme aanwijzingen van
Netbeheer Nederland (afstanden); zie docs/stations-en-kabels.md. De leidingen die al in de grond
liggen zijn VOORBEELDDATA.
"""

import math
from dataclasses import dataclass

from pydantic import BaseModel, field_validator

from gr0nd.kaart import DIEPTE_M

DEKKING_MIN_M = 0.8  # middenspanning en buizen (laagspanning: 0,6 m, nog geen type)
AFSTAND_MIN_M = 0.5  # tot bestaande kabels en leidingen van een netbeheerder
SLOOT_PUNTEN = 16  # aantal punten waarmee de rand van een leiding op de sloot wordt getoetst


@dataclass(frozen=True)
class LeidingType:
    id: str
    soort: str  # "kabel", "buis" of "leiding"
    naam: str
    diameter_m: float
    kleur: str
    kern: str | None  # kleur van de geleider, alleen voor kabels
    plaatsbaar: bool
    bron: str


KABEL_KERN = "#b9bec2"
BIBLIOTHEEK = (
    LeidingType("ms150", "kabel", "MS-kabel XLPE Al 150 mm²", 0.031, "#1d1d1f", KABEL_KERN, True,
                "datasheet 6/10 kV eenader, indicatief"),
    LeidingType("ms240", "kabel", "MS-kabel XLPE Al 240 mm²", 0.036, "#1d1d1f", KABEL_KERN, True,
                "datasheet 6/10 kV eenader, indicatief"),
    LeidingType("ms400", "kabel", "MS-kabel XLPE Al 400 mm²", 0.041, "#1d1d1f", KABEL_KERN, True,
                "datasheet 6/10 kV eenader, indicatief"),
    LeidingType("ms630", "kabel", "MS-kabel XLPE Al 630 mm²", 0.049, "#1d1d1f", KABEL_KERN, True,
                "datasheet 6/10 kV eenader, indicatief"),
    LeidingType("gplk300", "kabel", "GPLK 3×300 (papier-lood)", 0.040, "#6b6f73", KABEL_KERN,
                False, "KPN-overzicht, ca. 40 mm"),
    LeidingType("buis110", "buis", "Mantelbuis Ø 110 mm", 0.110, "#7b8591", None, True,
                "buismaten uit KPN-overzicht"),
    LeidingType("buis125", "buis", "Stalen mantelbuis Ø 125 mm", 0.125, "#7b8591", None, True,
                "buismaten uit KPN-overzicht"),
    LeidingType("buis160", "buis", "Mantelbuis Ø 160 mm", 0.160, "#7b8591", None, True,
                "buismaten uit KPN-overzicht"),
    LeidingType("hoofd400", "leiding", "Hoofdleiding (voorbeeld)", 0.400, "#5c7a8c", None, False,
                "voorbeeld, geen echte data"),
)  # fmt: skip
TYPE_PER_ID = {leidingtype.id: leidingtype for leidingtype in BIBLIOTHEEK}


@dataclass(frozen=True)
class ChecklistItem:
    id: str
    tekst: str
    bron: str
    auto: tuple[str, ...] = ()  # meldingscodes die dit punt automatisch toetsen


CHECKLIST = (
    ChecklistItem("dekking", "Dekking voldoet (middenspanning en buizen minimaal 80 cm)",
                  "Stedin-richtlijn", ("dekking", "bovengronds", "diepte")),
    ChecklistItem("afstand", "Minimaal 50 cm tot bestaande kabels en leidingen",
                  "Netbeheer Nederland", ("afstand", "buis_vol")),
    ChecklistItem("sloot", "Niet in of door een sloot of waterloop", "Ontwerpregel", ("sloot",)),
    ChecklistItem("bestaand", "Ligging bestaande leidingen gecontroleerd (proefsleuf of radar)",
                  "Netbeheer Nederland"),
    ChecklistItem("klic", "KLIC-melding gedaan voor het graven", "WIBON"),
    ChecklistItem("kruisen", "Kruisingen lopen onder de bestaande kabel door",
                  "Netbeheer Nederland"),
    ChecklistItem("bomen", "Minimaal 2,5 m tot bomen en 1 m tot struiken", "Stedin-richtlijn"),
    ChecklistItem("kasten", "Minimaal 1 m vrij rond kasten en stations", "Netbeheer Nederland"),
    ChecklistItem("boren", "Heien, boren en sonderen op minimaal 2 m van bestaande kabels",
                  "Netbeheer Nederland"),
    ChecklistItem("aanvullen", "Aanvullen: met de hand binnen 0,2 m naast en 0,4 m boven de kabel",
                  "Netbeheer Nederland"),
    ChecklistItem("toestemming", "Toestemming geregeld (eigenaar, natuur, spoor, gemeente)",
                  "Eigen lijst"),
    ChecklistItem("grond", "Grondsoort en grondwaterstand gecontroleerd", "Eigen lijst"),
)  # fmt: skip


class Leiding(BaseModel):
    id: str
    type_id: str
    u: float
    diepte: float
    nieuw: bool = False
    buis_id: str | None = None

    @field_validator("type_id")
    @classmethod
    def bekend_type(cls, waarde: str) -> str:
        if waarde not in TYPE_PER_ID:
            raise ValueError(f"Onbekend leidingtype: {waarde}")
        return waarde

    @property
    def straal(self) -> float:
        return TYPE_PER_ID[self.type_id].diameter_m / 2


class Melding(BaseModel):
    code: str
    niveau: str  # "fout", "waarschuwing" of "info"
    tekst: str
    leiding_ids: list[str]


def cm(meters: float) -> str:
    return f"{meters * 100:.0f} cm"


def sloot_diepte(bovengrond: dict, u: float) -> float:
    """Diepte van de slootbodem onder maaiveld op positie u (0 buiten de sloot)."""
    sloot = bovengrond["sloot"]
    afstand = abs(u - sloot["u_midden"])
    half_boven, half_bodem = sloot["breedte_boven"] / 2, sloot["breedte_bodem"] / 2
    if afstand >= half_boven:
        return 0.0
    if afstand <= half_bodem:
        return sloot["diepte"]
    return sloot["diepte"] * (half_boven - afstand) / (half_boven - half_bodem)


def oppervlak_hoogte(bovengrond: dict, u: float) -> float:
    """Hoogte van het oppervlak boven het maaiveld (berm positief, sloot negatief)."""
    weg = bovengrond["weg"]
    if weg["teen_l"] <= u < weg["kruin0"]:
        return weg["hoogte"] * (u - weg["teen_l"]) / (weg["kruin0"] - weg["teen_l"])
    if weg["kruin0"] <= u <= weg["kruin1"]:
        return weg["hoogte"]
    if weg["kruin1"] < u <= weg["teen_r"]:
        return weg["hoogte"] * (weg["teen_r"] - u) / (weg["teen_r"] - weg["kruin1"])
    return -sloot_diepte(bovengrond, u)


def raakt_sloot(bovengrond: dict, u: float, diepte: float, straal: float) -> bool:
    """Ligt (een deel van) de leiding in de sloot, tussen oppervlak en slootbodem?"""
    for i in range(SLOOT_PUNTEN + 1):
        hoek = 2 * math.pi * i / SLOOT_PUNTEN
        pu = u + straal * math.cos(hoek) if i < SLOOT_PUNTEN else u
        pd = diepte + straal * math.sin(hoek) if i < SLOOT_PUNTEN else diepte
        if 0 <= pd < sloot_diepte(bovengrond, pu):
            return True
    return False


def raakt_fundering(bovengrond: dict, u: float, diepte: float, straal: float) -> bool:
    """Raakt de leiding de funderingsstroken onder de gevels van het huis?"""
    huis = bovengrond["huis"]
    halve_breedte = huis["fundering_breedte"] / 2
    for gevel in (huis["u0"], huis["u1"]):
        dichtstbij_u = min(max(u, gevel - halve_breedte), gevel + halve_breedte)
        dichtstbij_d = min(max(diepte, 0.0), huis["fundering_diepte"])
        if math.hypot(u - dichtstbij_u, diepte - dichtstbij_d) <= straal:
            return True
    return False


def bundel_posities(buis: Leiding, kabels: list[Leiding]) -> dict[str, tuple[float, float]]:
    """Posities van kabels in een buis: één in het midden, meer op een ring."""
    if len(kabels) == 1:
        return {kabels[0].id: (buis.u, buis.diepte)}
    grootste = max(TYPE_PER_ID[k.type_id].diameter_m for k in kabels)
    ring = (TYPE_PER_ID[buis.type_id].diameter_m - grootste) / 2
    posities = {}
    for i, kabel in enumerate(kabels):
        hoek = 2 * math.pi * i / len(kabels) - math.pi / 2
        posities[kabel.id] = (buis.u + ring * math.cos(hoek), buis.diepte + ring * math.sin(hoek))
    return posities


def bundel_past(buis: Leiding, kabels: list[Leiding]) -> bool:
    """Passen de kabels naast elkaar op een ring in de buis?"""
    diameters = [TYPE_PER_ID[k.type_id].diameter_m for k in kabels]
    buisdiameter = TYPE_PER_ID[buis.type_id].diameter_m
    if len(diameters) <= 1:
        return all(d <= buisdiameter * 0.9 for d in diameters)
    ring = (buisdiameter - max(diameters)) / 2
    if ring <= 0 or any(d / (2 * ring) > 1 for d in diameters):
        return False
    return sum(2 * math.asin(d / (2 * ring)) for d in diameters) <= 2 * math.pi


def controleer_leiding(
    bovengrond: dict, leiding: Leiding, bestaand: list[Leiding]
) -> list[Melding]:
    """Alle controles voor één nieuwe leiding die niet in een buis ligt."""
    meldingen = []
    straal = leiding.straal

    def melding(code: str, niveau: str, tekst: str) -> None:
        meldingen.append(Melding(code=code, niveau=niveau, tekst=tekst, leiding_ids=[leiding.id]))

    if leiding.diepte + straal > DIEPTE_M:
        melding("diepte", "fout", f"Dieper dan {DIEPTE_M:.0f} m: buiten het model.")
    if raakt_sloot(bovengrond, leiding.u, leiding.diepte, straal):
        melding("sloot", "fout", "De leiding ligt in de sloot.")
    else:
        dekking = leiding.diepte - straal + oppervlak_hoogte(bovengrond, leiding.u)
        if dekking < 0:
            melding("bovengronds", "fout", "De leiding ligt (deels) boven de grond.")
        elif dekking < DEKKING_MIN_M:
            melding("dekking", "fout",
                    f"Te weinig dekking: {cm(dekking)}, minimaal {cm(DEKKING_MIN_M)}.")  # fmt: skip
    weg = bovengrond["weg"]
    if weg["teen_l"] <= leiding.u <= weg["teen_r"]:
        melding("weg", "waarschuwing", "U gaat onder de weg door.")
    huis = bovengrond["huis"]
    if raakt_fundering(bovengrond, leiding.u, leiding.diepte, straal):
        melding("huis", "fout", "De leiding raakt de fundering van een huis.")
    elif huis["u0"] < leiding.u < huis["u1"]:
        melding("huis", "waarschuwing", "U gaat onder een huis door.")
    for ander in bestaand:
        tussenruimte = (
            math.hypot(leiding.u - ander.u, leiding.diepte - ander.diepte) - straal - ander.straal
        )
        if tussenruimte < 0:
            melding("afstand", "fout", "De leiding botst met een bestaande leiding.")
        elif tussenruimte < AFSTAND_MIN_M:
            tekst = f"{cm(tussenruimte)} tot een bestaande leiding, min. {cm(AFSTAND_MIN_M)}."
            melding("afstand", "fout", tekst)
    return meldingen


def controleer(
    bovengrond: dict, leidingen: list[Leiding]
) -> tuple[list[Melding], dict[str, tuple[float, float]]]:
    """Geef alle meldingen en de positie van elke leiding (kabels in een buis zijn herberekend)."""
    per_id = {leiding.id: leiding for leiding in leidingen}
    groepen: dict[str, list[Leiding]] = {}
    for leiding in leidingen:
        if not leiding.buis_id:
            continue
        buis = per_id.get(leiding.buis_id)
        if buis is None or TYPE_PER_ID[buis.type_id].soort != "buis":
            raise ValueError(f"Leiding {leiding.id} verwijst naar een buis die niet bestaat.")
        if TYPE_PER_ID[leiding.type_id].soort != "kabel":
            raise ValueError("Alleen kabels kunnen in een buis liggen.")
        groepen.setdefault(leiding.buis_id, []).append(leiding)
    posities = {
        leiding.id: (leiding.u, leiding.diepte) for leiding in leidingen if not leiding.buis_id
    }
    meldingen = []
    for buis_id, kabels in groepen.items():
        posities |= bundel_posities(per_id[buis_id], kabels)
        nieuwe = [k.id for k in kabels if k.nieuw]
        if nieuwe and not bundel_past(per_id[buis_id], kabels):
            tekst = "De kabel past niet in de buis."
            meldingen.append(
                Melding(code="buis_vol", niveau="fout", tekst=tekst, leiding_ids=nieuwe)
            )
    bestaand = [leiding for leiding in leidingen if not leiding.nieuw and not leiding.buis_id]
    for leiding in leidingen:
        if leiding.nieuw and not leiding.buis_id:
            meldingen += controleer_leiding(bovengrond, leiding, bestaand)
    return meldingen, posities


def checklist_status(meldingen: list[Melding], heeft_nieuwe_leiding: bool) -> dict[str, str]:
    """Status van de automatisch getoetste punten: 'open', 'ok' of 'fout'."""
    status = {}
    for punt in CHECKLIST:
        if not punt.auto:
            continue
        fout = any(m.code in punt.auto and m.niveau == "fout" for m in meldingen)
        status[punt.id] = "open" if not heeft_nieuwe_leiding else ("fout" if fout else "ok")
    return status


def bestaande_leidingen(bovengrond: dict) -> list[Leiding]:
    """Voorbeeldleidingen die al in de grond liggen, passend bij de bovengrond."""
    sloot, weg, huis = bovengrond["sloot"], bovengrond["weg"], bovengrond["huis"]
    u_kabel = round((sloot["u_midden"] + sloot["breedte_boven"] / 2 + weg["teen_l"]) / 2, 2)
    u_buis = round((weg["kruin0"] + weg["kruin1"]) / 2, 2)
    u_hoofd = round(huis["u1"] + 5.0, 2)
    leidingen = [
        Leiding(id="bestaand-ms", type_id="ms240", u=u_kabel, diepte=0.95),
        Leiding(id="bestaand-buis", type_id="buis125", u=u_buis, diepte=1.4),
        Leiding(id="bestaand-hoofd", type_id="hoofd400", u=u_hoofd, diepte=2.2),
    ]
    leidingen += [
        Leiding(id=f"bestaand-gplk{i}", type_id="gplk300", u=u_buis, diepte=1.4,
                buis_id="bestaand-buis")
        for i in range(1, 4)
    ]  # fmt: skip
    return leidingen
