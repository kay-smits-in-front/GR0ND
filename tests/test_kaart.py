import numpy as np
import pytest

from gr0nd import kaart
from gr0nd.kaart import (
    DRENTS,
    KAARTLAGEN,
    KUSTKLEI,
    LOESS,
    RIVIEREN,
    ZAND,
    kaartlagen,
    lees_punt,
    nederland,
    rd_naar_wgs84,
    wgs84_naar_rd,
    zoek_locatie,
    zoek_locaties,
    zone_index,
)


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
