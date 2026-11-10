import numpy as np
import pytest

from gr0nd import kaart
from gr0nd.kaart import (
    DIEPTE_M,
    DRENTS,
    KAARTLAGEN,
    KUSTKLEI,
    LAGEN,
    LOESS,
    RIVIEREN,
    ZAND,
    Trace,
    blok,
    dwarsprofiel,
    georeferentie,
    kaartlagen,
    lees_punt,
    nederland,
    rd_naar_wgs84,
    voorbeeld_bovengrond,
    wgs84_naar_rd,
    zoek_locatie,
    zoek_locaties,
    zone_index,
)

AMSTERDAM = (121000, 487000)


def test_trace_noord_heeft_azimut_nul_en_positieve_u_is_west() -> None:
    trace = Trace.recht(121000, 487000, 121000, 487500)
    x, y = trace.punten(100, np.array([10.0]))

    assert trace.lengte == 500
    assert trace.azimut() == 0
    assert (x[0], y[0]) == (120990, 487100)


def test_trace_oost_heeft_azimut_negentig() -> None:
    assert Trace.recht(121000, 487000, 121500, 487000).azimut() == 90


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
        Trace.recht(*hoeken)


def test_seed_is_stabiel_per_stuk_van_100_meter() -> None:
    trace = Trace.recht(121000, 487000, 121000, 487500)

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
    profiel = dwarsprofiel(Trace.recht(*AMSTERDAM, 121000, 487500), 100)
    onder = np.array([laag["onderkant"] for laag in profiel["lagen"]])

    assert profiel["bron"] == "voorbeelddata"
    assert profiel["zone"] == "Kustklei en veen"
    assert onder.shape == (len(LAGEN), 61)
    assert np.all(np.diff(onder, axis=0) >= -1e-9)
    assert np.all(onder[-1] == DIEPTE_M)


def test_dwarsprofiel_is_deterministisch() -> None:
    trace = Trace.recht(*AMSTERDAM, 121000, 487500)

    assert dwarsprofiel(trace, 100) == dwarsprofiel(trace, 100)


@pytest.mark.parametrize("s", [-1, 501])
def test_dwarsprofiel_buiten_het_trace_geeft_fout(s) -> None:
    with pytest.raises(ValueError, match="buiten het tracé"):
        dwarsprofiel(Trace.recht(*AMSTERDAM, 121000, 487500), s)


def test_bovengrond_heeft_logische_volgorde_voor_veel_seeds() -> None:
    for seed in range(200):
        grond = voorbeeld_bovengrond(seed)
        huis, sloot, weg = grond["huizen"][0], grond["sloten"][0], grond["wegen"][0]

        assert huis["u0"] < huis["u1"] < sloot["u_midden"] - sloot["breedte_boven"] / 2
        assert sloot["u_midden"] + sloot["breedte_boven"] / 2 < weg["teen_l"]
        assert weg["teen_l"] < weg["kruin0"] < weg["kruin1"] < weg["teen_r"]
        assert weg["teen_r"] < 30
        assert huis["goot"] < huis["nok"]
        assert (
            huis["u1"] < grond["perceel"]["grens"] < sloot["u_midden"] - sloot["breedte_boven"] / 2
        )


def test_nederland_heeft_omtrek_en_zonekaart() -> None:
    kaart = nederland()
    zonekaart = kaart["zonekaart"]

    assert kaart["crs"] == "EPSG:28992"
    assert len(zonekaart["zones"]) == zonekaart["nx"] * zonekaart["ny"]
    assert len(kaart["legenda"]) == 5


def test_amersfoort_is_het_rd_nulpunt() -> None:
    x, y = wgs84_naar_rd(5.38720621, 52.1551744)

    assert abs(x - 155000) < 2
    assert abs(y - 463000) < 2


def test_rd_en_wgs84_zijn_elkaars_omgekeerde() -> None:
    lon, lat = rd_naar_wgs84(121000, 487000)
    x, y = wgs84_naar_rd(lon, lat)

    assert abs(x - 121000) < 0.5
    assert abs(y - 487000) < 0.5


def test_kaartlagen_hebben_unieke_id_en_een_standaard_achtergrond() -> None:
    ids = [laag.id for laag in KAARTLAGEN]
    achtergronden = [laag for laag in KAARTLAGEN if laag.groep == "achtergrond"]

    assert len(ids) == len(set(ids))
    assert [laag.standaard for laag in achtergronden].count(True) == 1
    assert kaartlagen()["volgt"]


def test_wmts_tegels_laten_z_x_y_open_voor_de_kaart() -> None:
    tegels = KAARTLAGEN[0].tegels

    assert tegels.startswith("pdok://")
    assert "tilematrix={z}" in tegels
    assert "tilerow={y}" in tegels
    assert "tilecol={x}" in tegels


def test_lees_punt() -> None:
    assert lees_punt("POINT(4.89131478 52.36988606)") == (4.89131478, 52.36988606)
    with pytest.raises(ValueError, match="puntformaat"):
        lees_punt("LINESTRING(1 2, 3 4)")


def test_zoek_locaties_geeft_id_naam_en_type(monkeypatch) -> None:
    docs = [{"type": "weg", "weergavenaam": "Kalverstraat, Amsterdam", "id": "weg-1", "score": 9}]
    monkeypatch.setattr(kaart, "haal_json", lambda url: {"response": {"docs": docs}})

    assert zoek_locaties("Kalverstraat") == [
        {"id": "weg-1", "naam": "Kalverstraat, Amsterdam", "type": "weg"}
    ]
    assert zoek_locaties("K") == []


def test_zoek_locatie_geeft_zoom_per_type_en_fout_bij_niets(monkeypatch) -> None:
    doc = {"weergavenaam": "Amsterdam", "centroide_ll": "POINT(4.9 52.37)", "type": "woonplaats"}
    monkeypatch.setattr(kaart, "haal_json", lambda url: {"response": {"docs": [doc]}})

    assert zoek_locatie("wpl-1") == {"naam": "Amsterdam", "lon": 4.9, "lat": 52.37, "zoom": 13}

    monkeypatch.setattr(kaart, "haal_json", lambda url: {"response": {"docs": []}})
    with pytest.raises(LookupError):
        zoek_locatie("onbekend")


BOCHT = Trace(((121000, 487000), (121000, 487300), (121400, 487300)))


def test_trace_met_bocht_heeft_samengestelde_lengte_en_richting() -> None:
    assert BOCHT.lengte == 700
    assert BOCHT.afstanden == [0, 300, 700]
    assert BOCHT.azimut(100) == 0
    assert BOCHT.azimut(500) == 90


def test_plek_volgt_de_bocht() -> None:
    assert BOCHT.plek(150)[:2] == (121000, 487150)
    assert BOCHT.plek(400)[:2] == (121100, 487300)
    assert BOCHT.plek(9999)[:2] == (121400, 487300)


def test_dwarsprofiel_toont_de_knik_en_de_richting_op_die_plek() -> None:
    begin = dwarsprofiel(BOCHT, 100)
    na_bocht = dwarsprofiel(BOCHT, 500)

    assert begin["trace"]["knikken"] == [300.0]
    assert begin["trace"]["azimut"] == 0
    assert na_bocht["trace"]["azimut"] == 90


@pytest.mark.parametrize(
    ("punten", "melding"),
    [
        (((121000, 487000),), "minstens"),
        (((121000, 487000), (121000, 487000), (121000, 487500)), "dezelfde plek"),
        (tuple((121000 + i * 5, 487000) for i in range(201)), "maximaal"),
    ],
)
def test_trace_weigert_onbruikbare_punten(punten, melding) -> None:
    with pytest.raises(ValueError, match=melding):
        Trace(punten)


def test_blok_geeft_een_raster_per_laag_met_oplopende_diepte() -> None:
    antwoord = blok(120000, 480000, 124000, 484000, n=12)

    assert antwoord["n"] == 12
    assert len(antwoord["onderkant"]) == len(antwoord["lagen"])
    assert all(len(laag) == 144 for laag in antwoord["onderkant"])
    assert antwoord["onderkant"][-1] == [antwoord["diepte"]] * 144
    for boven, onder in zip(antwoord["onderkant"], antwoord["onderkant"][1:], strict=False):
        assert all(b <= o for b, o in zip(boven, onder, strict=True))


@pytest.mark.parametrize(
    ("gebied", "n"),
    [((10, 10, 5, 20), 12), ((0, 0, 20_000, 100), 12), ((0, 0, 100, 100), 4)],
)
def test_blok_weigert_onmogelijke_gebieden(gebied: tuple, n: int) -> None:
    with pytest.raises(ValueError):
        blok(*gebied, n=n)


def test_georeferentie_amsterdam_en_convergentie() -> None:
    plek = georeferentie(121_000, 487_000)

    assert plek["lon"] == pytest.approx(4.89, abs=0.05)
    assert plek["lat"] == pytest.approx(52.37, abs=0.05)
    # Amsterdam ligt dicht bij de RD-oorsprong (5,387° O): RD-noord wijkt slechts een fractie af.
    assert abs(plek["convergentie"]) < 0.5
    # Ten oosten van de centrale meridiaan (meridianen convergeren) wijst RD-noord naar het oosten.
    assert georeferentie(250_000, 487_000)["convergentie"] > 0.5
    assert georeferentie(20_000, 487_000)["convergentie"] < -0.5
