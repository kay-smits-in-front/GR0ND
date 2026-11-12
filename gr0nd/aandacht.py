"""Aandachtspunten langs een tracé: grond, eigendom, kabels, obstakels, natuur en regels.

Elk punt heeft een plek (RD) en een afstand langs het tracé, een korte titel, uitleg en de bron.
Alles is indicatief en uit open data; het vervangt geen KLIC-melding, vergunning of veldonderzoek.
Water en rijbanen leveren een voorstel voor een gestuurde boring.
"""

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

import numpy as np

from gr0nd import geotop, netten, projectdata, wereld

Punt = tuple[float, float]
Gebied = tuple[float, float, float, float]

STAP_M = 1.0  # het tracé wordt elke meter bekeken
MARGE_M = 15.0  # zoveel rond het tracé wordt data opgehaald
BOOM_AFSTAND_M = 2.5  # Handboek Den Helder: bomen eerste grootte min. 2,5 m tot tracé
GEBOUW_AFSTAND_M = 1.0
EVENWIJDIG_AFSTAND_M = 0.5  # Netbeheer Nederland: parallel min. 0,5 m
EVENWIJDIG_LENGTE_M = 5.0
BOOR_MARGE_M = 10.0  # een voorgestelde boring begint en eindigt zo ver voor en na het obstakel
GROND_STAP_M = 10.0
BGT = wereld.BGT
PERCELEN = "https://api.pdok.nl/kadaster/brk-kadastrale-kaart/ogc/v1/collections/perceel"
ZACHTE_GROND = {1: "veen: zettingsgevoelig, let op ondersteuning", 2: "klei: slecht doorlatend"}


# ---------- meetkunde ----------


def bemonster(punten: list[Punt], stap: float = STAP_M) -> np.ndarray:
    """Punten om de `stap` langs het tracé, als rijen [x, y, s]."""
    uit = []
    s = 0.0
    for (x0, y0), (x1, y1) in zip(punten, punten[1:], strict=False):
        lengte = float(np.hypot(x1 - x0, y1 - y0))
        for a in np.arange(0, lengte, stap):
            t = a / lengte
            uit.append((x0 + t * (x1 - x0), y0 + t * (y1 - y0), s + a))
        s += lengte
    uit.append((*punten[-1], s))
    return np.array(uit)


def afstand_tot_lijn(x: np.ndarray, y: np.ndarray, lijn: list) -> np.ndarray:
    """Kortste afstand van elk punt (x, y) tot een lijn van hoekpunten."""
    a = np.asarray(lijn, float)[:-1, None, :2]
    b = np.asarray(lijn, float)[1:, None, :2]
    p = np.stack([x, y], axis=-1)[None, :, :]
    ab = b - a
    t = np.clip(((p - a) * ab).sum(-1) / np.maximum((ab * ab).sum(-1), 1e-12), 0, 1)
    dichtst = a + t[..., None] * ab
    return np.sqrt(((p - dichtst) ** 2).sum(-1)).min(axis=0)


def intervallen(masker: np.ndarray, s: np.ndarray) -> list[tuple[float, float]]:
    """Stukken (van, tot) langs het tracé waar het masker aan staat; tot = eerste punt erbuiten."""
    uit = []
    begin = None
    for aan, afstand in zip(masker, s, strict=True):
        if aan and begin is None:
            begin = afstand
        elif not aan and begin is not None:
            uit.append((float(begin), float(afstand)))
            begin = None
    if begin is not None:
        uit.append((float(begin), float(s[-1])))
    return uit


def ringen(geometrie: dict) -> list[list]:
    """De buitenringen van een (Multi)Polygon."""
    if geometrie["type"] == "Polygon":
        return [geometrie["coordinates"][0]]
    if geometrie["type"] == "MultiPolygon":
        return [delen[0] for delen in geometrie["coordinates"]]
    return []


def in_vlakken(monsters: np.ndarray, features: list[dict]) -> list[tuple[dict, np.ndarray]]:
    """Per vlak dat het tracé raakt: het vlak en het masker van tracépunten erbinnen."""
    uit = []
    for f in features:
        masker = np.zeros(len(monsters), bool)
        for ring in ringen(f["geometry"]):
            xy = np.asarray(ring, float)[:, :2]
            dicht = (monsters[:, 0] >= xy[:, 0].min()) & (monsters[:, 0] <= xy[:, 0].max())
            dicht &= (monsters[:, 1] >= xy[:, 1].min()) & (monsters[:, 1] <= xy[:, 1].max())
            if dicht.any():
                masker[dicht] |= wereld.binnen(
                    monsters[dicht, 0], monsters[dicht, 1], [tuple(p) for p in xy]
                )
        if masker.any():
            uit.append((f, masker))
    return uit


def punt(soort: str, titel: str, tekst: str, monster: np.ndarray, bron: str, **extra) -> dict:
    """Eén aandachtspunt op de plek van een tracémonster [x, y, s]."""
    x, y, s = (round(float(v), 1) for v in monster)
    return {
        "soort": soort,
        "titel": titel,
        "tekst": tekst,
        "x": x,
        "y": y,
        "s": s,
        "bron": bron,
        **extra,
    }


# ---------- per onderwerp ----------


def vlak_punten(monsters, features, soort, titel, tekst, bron, boring=False) -> list[dict]:
    """Een punt per stuk van het tracé dat door een vlak loopt (water, rijbaan, erf)."""
    uit = []
    for _, masker in in_vlakken(monsters, features):
        for van, tot in intervallen(masker, monsters[:, 2]):
            midden = monsters[np.abs(monsters[:, 2] - (van + tot) / 2).argmin()]
            extra = {"van": round(van, 1), "tot": round(tot, 1)}
            if boring:
                extra["voorstel_boring"] = [
                    round(max(0.0, van - BOOR_MARGE_M), 1),
                    round(tot + BOOR_MARGE_M, 1),
                ]
            uit.append(punt(soort, titel, f"{tekst} ({tot - van:.0f} m).", midden, bron, **extra))
    return uit


def water_en_wegen(monsters: np.ndarray, gebied: Gebied, ophalen) -> list[dict]:
    water = wereld.ogc_items(f"{BGT}/waterdeel", gebied, ophalen)
    wegen = [
        f for f in wereld.ogc_items(f"{BGT}/wegdeel", gebied, ophalen)
        if "rijbaan" in (f["properties"].get("functie") or "")
    ]  # fmt: skip
    return vlak_punten(
        monsters, water, "obstakel", "Kruist water",
        "Open water: boring of zinker, min. 1 m onder de waterbodem", "BGT waterdeel", True,
    ) + vlak_punten(
        monsters, wegen, "obstakel", "Kruist een rijbaan",
        "Rijbaan: boren, of graven met mantelbuis tot 0,5 m na de verharding", "BGT wegdeel", True,
    )  # fmt: skip


def prive_terrein(monsters: np.ndarray, gebied: Gebied, ophalen) -> list[dict]:
    erven = [
        f for f in wereld.ogc_items(f"{BGT}/onbegroeidterreindeel", gebied, ophalen)
        if f["properties"].get("fysiek_voorkomen") == "erf"
    ]  # fmt: skip
    return vlak_punten(
        monsters, erven, "eigendom", "Privéterrein (erf)",
        "Waarschijnlijk privéterrein: toestemming van de eigenaar nodig (indicatief)", "BGT erf",
    )  # fmt: skip


def percelen(monsters: np.ndarray, gebied: Gebied, ophalen) -> list[dict]:
    """Elk kadastraal perceel dat het tracé kruist, met nummer en grootte."""
    uit = []
    for f, masker in in_vlakken(monsters, wereld.ogc_items(PERCELEN, gebied, ophalen)):
        p = f["properties"]
        naam = f"{p.get('kadastrale_gemeente_waarde')} {p.get('sectie')} {p.get('perceelnummer')}"
        tekst = (
            f"Perceel {naam}, {p.get('kadastrale_grootte_waarde', '?')} m². "
            "De eigenaar staat in het Kadaster (betaald opvragen)."
        )
        uit.append(
            punt(
                "perceel",
                f"Perceel {naam}",
                tekst,
                monsters[masker][len(monsters[masker]) // 2],
                "Kadaster BRK",
            )
        )
    return uit


def bomen(monsters: np.ndarray, boompunten: list) -> list[dict]:
    uit = []
    for bx, by in boompunten:
        afstanden = np.hypot(monsters[:, 0] - bx, monsters[:, 1] - by)
        i = int(afstanden.argmin())
        if afstanden[i] < BOOM_AFSTAND_M:
            tekst = f"Boom op {afstanden[i]:.1f} m: wortels; houd {BOOM_AFSTAND_M} m aan of boor."
            uit.append(
                punt("obstakel", "Boom te dichtbij", tekst, monsters[i], "BGT boom", bx=bx, by=by)
            )
    return uit


def gebouwen(monsters: np.ndarray, panden: list[dict]) -> list[dict]:
    uit = []
    for pand in panden:
        rand = pand["rand"] + pand["rand"][:1]
        afstanden = afstand_tot_lijn(monsters[:, 0], monsters[:, 1], rand)
        binnen = wereld.binnen(monsters[:, 0], monsters[:, 1], [tuple(p) for p in pand["rand"]])
        i = int(afstanden.argmin())
        if binnen.any():
            uit.append(
                punt(
                    "obstakel",
                    "Tracé door een gebouw",
                    "Het tracé loopt door een pand: verleggen.",
                    monsters[binnen][0],
                    "3D BAG",
                )
            )
        elif afstanden[i] < GEBOUW_AFSTAND_M:
            tekst = f"Gebouw op {afstanden[i]:.1f} m: let op fundering en gevelaansluitingen."
            uit.append(punt("obstakel", "Gebouw dichtbij", tekst, monsters[i], "3D BAG"))
    return uit


def evenwijdige_kabels(monsters: np.ndarray, lagen: list[dict]) -> list[dict]:
    """Stukken waar het tracé over EVENWIJDIG_LENGTE_M te dicht langs een bestaande kabel loopt."""
    uit = []
    for laag in lagen:
        for lijn in laag["lijnen"]:
            masker = afstand_tot_lijn(monsters[:, 0], monsters[:, 1], lijn) < EVENWIJDIG_AFSTAND_M
            for van, tot in intervallen(masker, monsters[:, 2]):
                if tot - van < EVENWIJDIG_LENGTE_M:
                    continue
                midden = monsters[np.abs(monsters[:, 2] - (van + tot) / 2).argmin()]
                tekst = (
                    f"{tot - van:.0f} m evenwijdig binnen {EVENWIJDIG_AFSTAND_M} m van een "
                    f"{netten.SOORTEN[laag['soort']].naam.lower()}kabel van {laag['beheerder']}."
                )
                uit.append(
                    punt("kabels", "Kabel evenwijdig te dicht", tekst, midden, laag["beheerder"])
                )
    return uit


def grond(
    monsters: np.ndarray, gebied: Gebied, diepte: float, ophalen_tekst, ophalen
) -> list[dict]:
    """Grondsoort op leidingdiepte (GeoTOP), samengevat per stuk met dezelfde soort."""
    raster = wereld.maaiveld(gebied, ophalen)
    om = monsters[:: max(1, int(GROND_STAP_M / STAP_M))]
    hoogtes = [wereld.hoogte_op(raster, gebied, x, y) - diepte for x, y, _ in om]
    half = geotop.STAP_XY
    uitsnede = geotop.haal_uitsnede(
        (gebied[0] - half, gebied[1] - half, gebied[2] + half, gebied[3] + half),
        (min(hoogtes) - 1, max(hoogtes) + 1), ophalen_tekst,
    )  # fmt: skip
    namen = {k.code: k.naam for k in geotop.LITHOKLASSEN}
    soorten = []
    for (x, y, _), z in zip(om, hoogtes, strict=True):
        i, j = int(np.abs(uitsnede.x - x).argmin()), int(np.abs(uitsnede.y - y).argmin())
        k = int(np.abs(uitsnede.z - z).argmin())
        soorten.append(int(uitsnede.lithok[i, j, k]))
    uit = []
    begin = 0
    for nr in range(1, len(soorten) + 1):
        if nr < len(soorten) and soorten[nr] == soorten[begin]:
            continue
        code = soorten[begin]
        if code in namen:
            midden = om[(begin + nr - 1) // 2]
            tekst = f"Op {diepte:.1f} m diepte: {namen[code].lower()}"
            tekst += f" — {ZACHTE_GROND[code]}." if code in ZACHTE_GROND else "."
            stuk = {"van": round(float(om[begin][2]), 1), "tot": round(float(om[nr - 1][2]), 1)}
            uit.append(punt("grond", namen[code], tekst, midden, "GeoTOP (100 m raster)", **stuk))
        begin = nr
    return uit


def natuur(monsters: np.ndarray, ophalen_json) -> list[dict]:
    """Beschermde natuur en cultuurhistorie op het tracé, plus de algemene regels."""
    lon, lat = projectdata.rd_naar_ll().transform(monsters[:, 0], monsters[:, 1])
    ll = np.column_stack([lon, lat, monsters[:, 2]])
    bbox = (float(lon.min()), float(lat.min()), float(lon.max()), float(lat.max()))
    uit = []
    for bron in projectdata.BRONNEN:
        if bron.categorie not in ("natuur", "erfgoed"):
            continue
        features = projectdata.haal_bron(bron, bbox, ophalen_json)["features"]
        for _, masker in in_vlakken(ll, features):
            tekst = f"Het tracé loopt door {bron.naam}: vergunning of toets nodig."
            uit.append(punt("natuur", bron.naam, tekst, monsters[masker][0], bron.naam))
    eerste = monsters[0]
    for regel in projectdata.AANDACHTSPUNTEN:
        uit.append(
            punt("regels", regel["titel"], regel["tekst"], eerste, "GR0ND regels", algemeen=True)
        )
    return uit


# ---------- alles samen ----------


def aandachtspunten(
    punten: list[Punt],
    diepte: float = 1.2,
    ophalen: Callable[[str], bytes] = wereld.haal,
    ophalen_tekst: Callable[[str], str] = geotop.haal_tekst,
    ophalen_json: Callable[[str], dict] = projectdata.haal_json,
) -> dict:
    """Alle aandachtspunten, op volgorde langs het tracé, met voorgestelde boringen."""
    monsters = bemonster(punten)
    gebied = (
        float(monsters[:, 0].min() - MARGE_M), float(monsters[:, 1].min() - MARGE_M),
        float(monsters[:, 0].max() + MARGE_M), float(monsters[:, 1].max() + MARGE_M),
    )  # fmt: skip
    ring = [
        (gebied[0], gebied[1]),
        (gebied[2], gebied[1]),
        (gebied[2], gebied[3]),
        (gebied[0], gebied[3]),
    ]
    taken = {
        "water_en_wegen": lambda: water_en_wegen(monsters, gebied, ophalen),
        "prive": lambda: prive_terrein(monsters, gebied, ophalen),
        "percelen": lambda: percelen(monsters, gebied, ophalen),
        "bomen": lambda: bomen(monsters, wereld.bomen(gebied, ring, ophalen)),
        "gebouwen": lambda: gebouwen(monsters, wereld.gebouwen(gebied, ring, ophalen)),
        "kabels": lambda: evenwijdige_kabels(monsters, netten.haal_netten(gebied)["lagen"]),
        "grond": lambda: grond(monsters, gebied, diepte, ophalen_tekst, ophalen),
        "natuur": lambda: natuur(monsters, ophalen_json),
    }
    uit, fouten = [], []
    with ThreadPoolExecutor(len(taken)) as pool:
        lopend = {naam: pool.submit(taak) for naam, taak in taken.items()}
        for naam, taak in lopend.items():
            try:
                uit += taak.result()
            except (
                OSError,
                ValueError,
                KeyError,
            ) as fout:  # één bron die uitvalt stopt de rest niet
                fouten.append(f"{naam}: {str(fout)[:120]}")
    return {
        "punten": sorted(uit, key=lambda p: (p.get("algemeen", False), p["s"])),
        "voorstel_boringen": samenvoegen(
            [tuple(p["voorstel_boring"]) for p in uit if "voorstel_boring" in p]
        ),
        "fouten": fouten,
    }


def samenvoegen(stukken: list[tuple[float, float]]) -> list[list[float]]:
    """Overlappende stukken (van, tot) samenvoegen tot één."""
    uit: list[list[float]] = []
    for van, tot in sorted(stukken):
        if uit and van <= uit[-1][1]:
            uit[-1][1] = max(uit[-1][1], tot)
        else:
            uit.append([van, tot])
    return uit
