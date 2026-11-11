import json
from pathlib import Path

import numpy as np

from gr0nd import wereld

VIERKANT = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]


def test_binnen_volgt_de_ring():
    assert wereld.binnen(np.array([5, 15, -1]), np.array([5, 5, 5]), VIERKANT).tolist() == [
        True,
        False,
        False,
    ]


def test_lees_hoogtes_echte_ahn_tegel_utrecht():
    # 200 × 200 AHN-cellen bij Utrecht (deflate met float-predictor), opgehaald bij PDOK
    raster = wereld.lees_hoogtes((Path(__file__).parent / "ahn_klein.tif").read_bytes())
    assert raster.shape == (200, 200)
    assert -2 < np.nanmin(raster) and np.nanmax(raster) < 8
    assert 0.05 < np.isnan(raster).mean() < 0.4  # gebouwen en water zijn leeg


def test_vul_gaten_vult_alles_lineair():
    raster = np.array([[1.0, np.nan, 3.0], [np.nan, np.nan, np.nan], [1.0, 2.0, 3.0]])
    gevuld = wereld.vul_gaten(raster)
    assert np.isfinite(gevuld).all()
    assert gevuld[0, 1] == 2.0 and gevuld[1, 0] == 1.0


def test_randpunten_sluiten_de_ring_om_de_stap():
    punten = wereld.randpunten(VIERKANT, stap=5)
    assert len(punten) == 9 and punten[0] == punten[-1] == (0.0, 0.0)


def test_tegels_dekken_het_gebied():
    delen = wereld.tegels((0, 0, 1000, 500), 400)
    assert len(delen) == 6 and delen[0][:2] == (0, 0) and delen[-1][2:] == (1000, 500)


def test_gebouwen_alleen_binnen_de_ring_met_hoogtes():
    def ophalen(url: str) -> bytes:
        rand = [[1, 1], [3, 1], [3, 3], [1, 1]]
        buiten = [[20, 20], [22, 20], [22, 22], [20, 20]]
        return json.dumps({"features": [
            {"geometry": {"type": "Polygon", "coordinates": [rand]},
             "properties": {"b3_h_70p": 9.0, "b3_h_maaiveld": 1.0, "b3_dak_type": "slanted"}},
            {"geometry": {"type": "Polygon", "coordinates": [buiten]},
             "properties": {"b3_h_70p": 9.0, "b3_h_maaiveld": 1.0}},
        ]}).encode()  # fmt: skip

    [pand] = wereld.gebouwen((0, 0, 30, 30), VIERKANT, ophalen)
    assert pand["dak"] == 9.0 and pand["voet"] == 1.0 and pand["schuin"]
    assert len(pand["rand"]) == 3


def test_bomen_zonder_oude_versies_en_dubbelen():
    def ophalen(url: str) -> bytes:
        boom = {"geometry": {"coordinates": [5, 5]}, "properties": {"plus_type": "boom"}}
        oud = {"geometry": {"coordinates": [6, 6]}, "properties": {"eind_registratie": "2020"}}
        return json.dumps({"features": [boom, boom, oud], "links": []}).encode()

    assert wereld.bomen((0, 0, 10, 10), VIERKANT, ophalen) == [[5.0, 5.0]]
