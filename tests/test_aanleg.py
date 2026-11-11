import math

import pytest

from gr0nd import aanleg
from gr0nd.aanleg import Wijze

RECHT = [(0.0, 0.0), (100.0, 0.0)]
SOORTEN = {"ls": {"diepte_m": 0.6}}
DWARS = [{"soort": "ls", "beheerder": "Test", "lijnen": [[[50, -10], [50, 10]]]}]


def test_ontgraven_ligt_overal_op_de_gekozen_diepte():
    assert [p[2] for p in aanleg.profiel(RECHT, Wijze.ONTGRAVEN, 1.2)] == [1.2, 1.2]


def test_boring_begint_en_eindigt_op_maaiveld_en_zakt_onder_de_intredehoek():
    profiel = aanleg.profiel(RECHT, Wijze.BORING, 4.0)
    assert profiel[0][2] == 0 and profiel[-1][2] == 0
    assert max(p[2] for p in profiel) == 4.0
    op_tien_meter = next(p for p in profiel if p[0] == 10)
    assert op_tien_meter[2] == pytest.approx(10 * math.tan(math.radians(10)), abs=0.01)


def test_snijpunt_van_kruis_en_evenwijdige_lijnen():
    assert aanleg.snijpunt((0, 0), (10, 0), (5, -5), (5, 5)) == (0.5, 0.5)
    assert aanleg.snijpunt((0, 0), (10, 0), (0, 1), (10, 1)) is None
    assert aanleg.snijpunt((0, 0), (10, 0), (20, -5), (20, 5)) is None


def test_ontgraven_op_ls_diepte_is_te_dicht_en_boring_eronder_is_ok():
    [ontgraven] = aanleg.kruisingen(RECHT, Wijze.ONTGRAVEN, 0.8, DWARS, SOORTEN)
    assert (ontgraven["s"], ontgraven["tussenruimte"], ontgraven["ok"]) == (50.0, 0.2, False)
    [boring] = aanleg.kruisingen(RECHT, Wijze.BORING, 4.0, DWARS, SOORTEN)
    assert boring["nieuw_diepte"] == 4.0 and boring["ok"]


def test_plek_op_volgt_een_bocht():
    punten = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)]
    assert aanleg.plek_op(punten, aanleg.afstanden(punten), 15) == (10.0, 5.0)
