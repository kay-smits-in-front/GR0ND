import os

import numpy as np
import pytest

from gr0nd import geotop


def test_index_bereik_neemt_middens_binnen_het_gebied():
    assert geotop.index_bereik(13_600, 13_800, geotop.X0, 100, 10) == range(0, 3)
    assert geotop.index_bereik(13_650, 13_790, geotop.X0, 100, 10) == range(1, 2)


def test_index_bereik_buiten_het_model_geeft_fout():
    with pytest.raises(ValueError):
        geotop.index_bereik(0, 100, geotop.X0, 100, 10)


def test_opendap_adres_bevat_de_indexen():
    adres = geotop.opendap_adres(range(1, 3), range(4, 5), range(6, 9))
    assert adres.endswith("lithok%5B1:1:2%5D%5B4:1:4%5D%5B6:1:8%5D")


ASCII = """Dataset: geotop.nc
lithok.lithok, [2][1][3]
lithok.z, -50, -49.5, -49
lithok.lithok[lithok.x=13600][lithok.y=338500], 2, 1, -127
lithok.lithok[lithok.x=13700][lithok.y=338500], 5, 6, 7
"""


def test_lees_ascii_geeft_array_in_x_y_z_volgorde():
    lithok = geotop.lees_ascii(ASCII, (2, 1, 3))
    assert lithok[1, 0].tolist() == [5, 6, 7]
    assert lithok[0, 0, 2] == geotop.GEEN_DATA


def test_lees_ascii_met_verkeerde_vorm_geeft_fout():
    with pytest.raises(ValueError):
        geotop.lees_ascii(ASCII, (3, 1, 3))


def test_haal_uitsnede_zonder_netwerk():
    gevraagd = []

    def ophalen(url: str) -> str:
        gevraagd.append(url)
        return ASCII

    uitsnede = geotop.haal_uitsnede((13_600, 338_500, 13_700, 338_500), (-50, -49), ophalen)
    assert "lithok%5B0:1:1%5D%5B0:1:0%5D%5B0:1:2%5D" in gevraagd[0]
    assert uitsnede.x.tolist() == [13_600, 13_700]
    assert uitsnede.z.tolist() == [-50, -49.5, -49]
    assert uitsnede.lithok.shape == (2, 1, 3)


def test_haal_uitsnede_te_groot_geeft_fout():
    with pytest.raises(ValueError):
        geotop.haal_uitsnede((13_600, 338_500, 278_000, 619_000), (-50, 100), lambda _: "")


@pytest.mark.skipif(not os.environ.get("GR0ND_NETWERK_TESTS"), reason="alleen met netwerk")
def test_haal_uitsnede_echt_utrecht():
    uitsnede = geotop.haal_uitsnede((136_000, 455_000, 136_200, 455_200), (-10, 5))
    assert uitsnede.lithok.shape == (3, 3, 31)
    assert np.isin(uitsnede.lithok, [k.code for k in geotop.LITHOKLASSEN]).any()


def test_wanden_neemt_halve_voxel_rond_het_gebied_mee():
    gevraagd = []

    def ophalen(url: str) -> str:
        gevraagd.append(url)
        kolom = ", ".join(["2", "5"] + ["-127"] * (geotop.AANTAL_Z - 2))
        aantal = 3 if "%5B0:1:2%5D%5B" in url else 1
        return "\n".join(f"lithok.lithok[a][b], {kolom}" for _ in range(aantal))

    wanden = geotop.wanden((13_620, 338_520, 13_780, 338_520), ophalen)
    assert wanden["zijden"]["zuid"]["posities"] == [13_600, 13_700, 13_800]
    assert wanden["referentie_nap"] == geotop.Z0 + 0.75  # bovenkant van de voxel op Z0 + 0,5
    assert wanden["zijden"]["zuid"]["kolommen"][0]["lithok"] == [5, 2]


def test_maaiveld_zonder_grond_is_none():
    assert geotop.maaiveld(np.full(4, geotop.GEEN_DATA)) is None
