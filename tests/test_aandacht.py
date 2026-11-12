import numpy as np

from gr0nd import aandacht

RECHT = [(0.0, 0.0), (100.0, 0.0)]


def test_bemonster_om_de_meter_tot_het_eind():
    monsters = aandacht.bemonster(RECHT)
    assert len(monsters) == 101 and monsters[-1].tolist() == [100, 0, 100]


def test_afstand_tot_lijn():
    afstand = aandacht.afstand_tot_lijn(
        np.array([5.0, 20.0]), np.array([3.0, 0.0]), [[0, 0], [10, 0]]
    )
    assert afstand.tolist() == [3.0, 10.0]


def test_intervallen_van_een_masker():
    masker = np.array([False, True, True, False, True])
    assert aandacht.intervallen(masker, np.arange(5.0)) == [(1.0, 3.0), (4.0, 4.0)]


def test_water_geeft_een_voorgestelde_boring():
    vlak = {
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[40, -5], [60, -5], [60, 5], [40, 5], [40, -5]]],
        }
    }
    [punt] = aandacht.vlak_punten(
        aandacht.bemonster(RECHT), [vlak], "obstakel", "Water", "Uitleg", "BGT", True
    )
    assert (punt["van"], punt["tot"]) == (40.0, 60.0)
    assert punt["voorstel_boring"] == [30.0, 70.0]


def test_boom_dichtbij_wel_en_veraf_niet():
    punten = aandacht.bomen(aandacht.bemonster(RECHT), [[50, 1.5], [50, 8]])
    assert len(punten) == 1 and punten[0]["s"] == 50


def test_evenwijdige_kabel_alleen_als_het_stuk_lang_genoeg_is():
    lang = {"soort": "ls", "beheerder": "Test", "lijnen": [[[10, 0.3], [40, 0.3]]]}
    kort = {"soort": "ms", "beheerder": "Test", "lijnen": [[[70, 0.3], [72, 0.3]]]}
    [punt] = aandacht.evenwijdige_kabels(aandacht.bemonster(RECHT), [lang, kort])
    assert "31 m evenwijdig" in punt["tekst"]  # tot het eerste punt erbuiten: nauwkeurig op 1 m


def test_samenvoegen_van_overlappende_stukken():
    assert aandacht.samenvoegen([(50, 70), (10, 20), (60, 90)]) == [[10, 20], [50, 90]]
