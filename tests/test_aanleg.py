import math

import pytest

from gr0nd import aanleg
from gr0nd.aanleg import Aanleg, Wijze

RECHT = [(0.0, 0.0), (100.0, 0.0)]
SOORTEN = {"ls": {"diepte_m": 0.6}}
DWARS = [{"soort": "ls", "beheerder": "Test", "lijnen": [[[50, -10], [50, 10]]]}]


def test_ontgraven_ligt_overal_op_de_gekozen_diepte():
    assert [p[2] for p in aanleg.profiel(RECHT, Aanleg(wijze=Wijze.ONTGRAVEN, diepte=1.2))] == [
        1.2,
        1.2,
    ]


def test_boring_begint_en_eindigt_op_maaiveld_en_zakt_onder_de_intredehoek():
    profiel = aanleg.profiel(RECHT, Aanleg(wijze=Wijze.BORING, diepte=4.0))
    assert profiel[0][2] == 0 and profiel[-1][2] == 0
    assert max(p[2] for p in profiel) == 4.0
    op_tien_meter = next(p for p in profiel if p[0] == 10)
    assert op_tien_meter[2] == pytest.approx(10 * math.tan(math.radians(10)), abs=0.01)


def test_snijpunt_van_kruis_en_evenwijdige_lijnen():
    assert aanleg.snijpunt((0, 0), (10, 0), (5, -5), (5, 5)) == (0.5, 0.5)
    assert aanleg.snijpunt((0, 0), (10, 0), (0, 1), (10, 1)) is None
    assert aanleg.snijpunt((0, 0), (10, 0), (20, -5), (20, 5)) is None


def test_ontgraven_op_ls_diepte_is_te_dicht_en_boring_eronder_is_ok():
    [ontgraven] = aanleg.kruisingen(
        RECHT, Aanleg(wijze=Wijze.ONTGRAVEN, diepte=0.8), DWARS, SOORTEN
    )
    assert (ontgraven["s"], ontgraven["tussenruimte"], ontgraven["ok"]) == (50.0, 0.2, False)
    [boring] = aanleg.kruisingen(RECHT, Aanleg(wijze=Wijze.BORING, diepte=4.0), DWARS, SOORTEN)
    assert boring["nieuw_diepte"] == 4.0 and boring["ok"]


def test_plek_op_volgt_een_bocht():
    punten = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)]
    assert aanleg.plek_op(punten, aanleg.afstanden(punten), 15) == (10.0, 5.0)


def test_steilere_intrede_bereikt_de_diepte_eerder():
    vlak = aanleg.profiel(RECHT, Aanleg(wijze=Wijze.BORING, diepte=4.0, intrede_graden=10))
    steil = aanleg.profiel(RECHT, Aanleg(wijze=Wijze.BORING, diepte=4.0, intrede_graden=30))
    eerste = lambda p: next(x for x, _, d in p if d == 4.0)  # noqa: E731
    assert eerste(steil) < eerste(vlak)


def test_duur_en_grondverzet():
    graven = Aanleg(wijze=Wijze.ONTGRAVEN, diepte=1.2, sleuf_breedte=0.5, snelheid_m_per_uur=20)
    assert aanleg.duur_uren(100, graven) == 5
    assert aanleg.grondverzet_m3(100, graven) == pytest.approx(65)
    assert aanleg.grondverzet_m3(100, Aanleg(wijze=Wijze.BORING)) == 0


def test_geojson_heeft_lijn_met_diepte_en_kruisingen():
    profiel = [[5.0, 52.0, 0.0], [5.001, 52.0, 1.2]]
    kruising = ((5.0005, 52.0), {"ok": False, "tussenruimte": 0.2})
    data = aanleg.geojson(
        "Test", profiel, Aanleg(wijze=Wijze.ONTGRAVEN), {"lengte": 70}, [kruising]
    )
    lijn, punt = data["features"]
    assert lijn["geometry"]["coordinates"] == [[5.0, 52.0], [5.001, 52.0]]
    assert lijn["properties"]["diepte_per_punt_m"] == [0.0, 1.2]
    assert lijn["properties"]["wijze"] == "ontgraven" and lijn["properties"]["lengte"] == 70
    assert punt["properties"]["ok"] is False


def test_aanleg_weigert_onmogelijke_waarden():
    with pytest.raises(ValueError):
        Aanleg(wijze=Wijze.BORING, intrede_graden=80)


def test_boring_alleen_op_het_gekozen_stuk():
    instelling = Aanleg(wijze=Wijze.ONTGRAVEN, diepte=1.0, boringen=[(40, 60)], boor_diepte=3)
    diepte = {x: d for x, _, d in aanleg.profiel(RECHT, instelling)}
    assert diepte[0] == diepte[100] == 1.0  # gegraven
    assert diepte[40] == 0 and diepte[60] == 0  # in- en uittredepunt aan het maaiveld
    assert diepte[50] == pytest.approx(10 * math.tan(math.radians(10)), abs=0.01)


def test_duur_en_grondverzet_met_een_boring():
    instelling = Aanleg(
        wijze=Wijze.ONTGRAVEN, diepte=1.2, sleuf_breedte=0.5, snelheid_m_per_uur=10,
        boringen=[(20, 60), (50, 200)], boor_snelheid_m_per_uur=40,
    )  # fmt: skip
    assert aanleg.boorstukken(100, instelling) == [(20, 100)]  # overlap wordt één boring
    assert aanleg.duur_uren(100, instelling) == pytest.approx(20 / 10 + 80 / 40)
    assert aanleg.grondverzet_m3(100, instelling) == pytest.approx(20 * 0.5 * 1.3)
