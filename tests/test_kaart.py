import numpy as np
import pytest

from gr0nd.kaart import (
    DIEPTE_M,
    DRENTS,
    KUSTKLEI,
    LAGEN,
    LOESS,
    RIVIEREN,
    ZAND,
    Trace,
    dwarsprofiel,
    nederland,
    voorbeeld_bovengrond,
    zone_index,
)

AMSTERDAM = (121000, 487000)


def test_trace_noord_heeft_azimut_nul_en_positieve_u_is_west() -> None:
    trace = Trace(121000, 487000, 121000, 487500)
    x, y = trace.punten(100, np.array([10.0]))

    assert trace.lengte == 500
    assert trace.azimut == 0
    assert (x[0], y[0]) == (120990, 487100)


def test_trace_oost_heeft_azimut_negentig() -> None:
    assert Trace(121000, 487000, 121500, 487000).azimut == 90


@pytest.mark.parametrize(
    ("hoeken", "melding"),
    [
        ((121000, 487000, 121005, 487000), "te kort"),
        ((121000, 487000, 221000, 487000), "te lang"),
        ((-50000, 487000, -49800, 487000), "buiten"),
    ],
)
def test_trace_weigert_onbruikbare_trace(hoeken, melding) -> None:
    with pytest.raises(ValueError, match=melding):
        Trace(*hoeken)


def test_seed_is_stabiel_per_stuk_van_100_meter() -> None:
    trace = Trace(121000, 487000, 121000, 487500)

    assert trace.seed(10) == trace.seed(90)
    assert trace.seed(10) != trace.seed(110)


@pytest.mark.parametrize(
    ("plaats", "x", "y", "zone"),
    [
        ("Amsterdam", 121000, 487000, KUSTKLEI),
        ("Middelburg", 28000, 388000, KUSTKLEI),
        ("Lelystad", 155000, 490000, KUSTKLEI),
        ("Groningen", 233000, 582000, KUSTKLEI),
        ("Nijmegen", 187000, 428000, RIVIEREN),
        ("Eindhoven", 161000, 383000, ZAND),
        ("Assen", 233000, 553000, DRENTS),
        ("Maastricht", 176000, 318000, LOESS),
    ],
)
def test_zone_per_plaats(plaats, x, y, zone) -> None:
    assert zone_index(np.array([x]), np.array([y]))[0] == zone, plaats


def test_dwarsprofiel_heeft_stijgende_lagen_tot_vijftig_meter() -> None:
    profiel = dwarsprofiel(Trace(*AMSTERDAM, 121000, 487500), 100)
    onder = np.array([laag["onderkant"] for laag in profiel["lagen"]])

    assert profiel["bron"] == "voorbeelddata"
    assert profiel["zone"] == "Kustklei en veen"
    assert onder.shape == (len(LAGEN), 61)
    assert np.all(np.diff(onder, axis=0) >= -1e-9)
    assert np.all(onder[-1] == DIEPTE_M)


def test_dwarsprofiel_is_deterministisch() -> None:
    trace = Trace(*AMSTERDAM, 121000, 487500)

    assert dwarsprofiel(trace, 100) == dwarsprofiel(trace, 100)


@pytest.mark.parametrize("s", [-1, 501])
def test_dwarsprofiel_buiten_het_trace_geeft_fout(s) -> None:
    with pytest.raises(ValueError, match="buiten het tracé"):
        dwarsprofiel(Trace(*AMSTERDAM, 121000, 487500), s)


def test_bovengrond_heeft_logische_volgorde_voor_veel_seeds() -> None:
    for seed in range(200):
        grond = voorbeeld_bovengrond(seed)
        huis, sloot, weg = grond["huis"], grond["sloot"], grond["weg"]

        assert huis["u0"] < huis["u1"] < sloot["u_midden"] - sloot["breedte_boven"] / 2
        assert sloot["u_midden"] + sloot["breedte_boven"] / 2 < weg["teen_l"]
        assert weg["teen_l"] < weg["kruin0"] < weg["kruin1"] < weg["teen_r"]
        assert weg["teen_r"] < 30
        assert huis["goot"] < huis["nok"]


def test_nederland_heeft_omtrek_en_zonekaart() -> None:
    kaart = nederland()
    zonekaart = kaart["zonekaart"]

    assert kaart["crs"] == "EPSG:28992"
    assert len(zonekaart["zones"]) == zonekaart["nx"] * zonekaart["ny"]
    assert len(kaart["legenda"]) == 5
