import pytest

from gr0nd.kaart import (
    blok,
    georeferentie,
)


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
