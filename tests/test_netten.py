from gr0nd import netten


def test_lijnen_leest_line_en_multiline():
    geojson = {
        "features": [
            {"geometry": {"type": "LineString", "coordinates": [[1, 2], [3, 4]]}},
            {"geometry": {"type": "MultiLineString", "coordinates": [[[5, 6], [7, 8, 0]]]}},
            {"geometry": None},
        ]
    }
    assert netten.lijnen(geojson) == [[[1, 2], [3, 4]], [[5, 6], [7, 8]]]


def test_haal_netten_zonder_netwerk_meldt_fouten_per_laag():
    def ophalen(url: str) -> dict:
        if "Stedin" in url:
            raise OSError("time-out")
        return {"features": [{"geometry": {"type": "LineString", "coordinates": [[0, 0], [1, 1]]}}]}

    data = netten.haal_netten((0, 0, 10, 10), ophalen)
    stedin = [laag for laag in data["lagen"] if laag["beheerder"].startswith("Stedin")]
    assert all(laag["lijnen"] == [] and "fout" in laag for laag in stedin)
    assert any(laag["lijnen"] for laag in data["lagen"])
    assert {s["id"] for s in data["soorten"]} == {"ls", "ms", "hs", "gas"}


def test_query_adres_in_rd():
    adres = netten.query_adres(netten.LAGEN[0], (1.4, 2, 3, 4))
    assert "inSR=28992" in adres and "outSR=28992" in adres and "geometry=1%2C2%2C3%2C4" in adres
