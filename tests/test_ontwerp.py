import pytest

from gr0nd.ontwerp import (
    Leiding,
    bestaande_leidingen,
    checklist_status,
    controleer,
)

BOVENGROND = {
    "huis": {"u0": -22.0, "u1": -13.0, "goot": 5.5, "nok": 9.5,
             "fundering_diepte": 0.8, "fundering_breedte": 0.5},
    "sloot": {"u_midden": -3.0, "breedte_boven": 4.0, "breedte_bodem": 1.5,
              "diepte": 1.0, "waterpeil": 0.4},
    "weg": {"teen_l": 3.0, "kruin0": 4.5, "kruin1": 11.5, "teen_r": 13.0,
            "hoogte": 0.5, "asfalt": 0.2},
    "lantaarn": {"u": 10.7, "hoogte": 5.0},
}  # fmt: skip


def nieuwe_kabel(u: float, diepte: float, id_: str = "nieuw") -> Leiding:
    return Leiding(id=id_, type_id="ms240", u=u, diepte=diepte, nieuw=True)


def codes(leidingen: list[Leiding]) -> list[tuple[str, str]]:
    meldingen, _ = controleer(BOVENGROND, leidingen)
    return [(m.code, m.niveau) for m in meldingen]


def test_bestaande_leidingen_geven_geen_meldingen() -> None:
    assert codes(bestaande_leidingen(BOVENGROND)) == []


def test_nieuwe_kabel_in_de_tuin_is_goed() -> None:
    leidingen = [*bestaande_leidingen(BOVENGROND), nieuwe_kabel(-8, 1.2)]

    assert codes(leidingen) == []


def test_te_weinig_dekking() -> None:
    assert codes([nieuwe_kabel(-8, 0.5)]) == [("dekking", "fout")]


def test_boven_de_grond() -> None:
    assert codes([nieuwe_kabel(-8, 0.0)]) == [("bovengronds", "fout")]


def test_in_de_sloot() -> None:
    assert ("sloot", "fout") in codes([nieuwe_kabel(-3, 0.5)])


def test_onder_de_weg_geeft_waarschuwing() -> None:
    assert codes([nieuwe_kabel(8, 2.5)]) == [("weg", "waarschuwing")]


def test_onder_een_huis_geeft_waarschuwing() -> None:
    assert codes([nieuwe_kabel(-17, 1.5)]) == [("huis", "waarschuwing")]


def test_raken_van_de_fundering_is_een_fout() -> None:
    assert ("huis", "fout") in codes([nieuwe_kabel(-13, 0.5)])


def test_te_dicht_bij_een_bestaande_kabel() -> None:
    leidingen = [*bestaande_leidingen(BOVENGROND), nieuwe_kabel(1.0, 1.2)]

    assert ("afstand", "fout") in codes(leidingen)


def test_kabel_past_in_een_bestaande_buis() -> None:
    buis = Leiding(id="buis", type_id="buis125", u=-8, diepte=1.5)
    kabels = [nieuwe_kabel(0, 0, f"k{i}").model_copy(update={"buis_id": "buis"}) for i in range(2)]

    assert codes([buis, *kabels]) == []


def test_buis_wordt_vol() -> None:
    buis = Leiding(id="buis", type_id="buis125", u=-8, diepte=1.5)
    kabels = [
        Leiding(id=f"k{i}", type_id="ms630", u=0, diepte=0, nieuw=True, buis_id="buis")
        for i in range(6)
    ]

    assert ("buis_vol", "fout") in codes([buis, *kabels])


def test_kabels_in_een_buis_krijgen_een_nieuwe_positie() -> None:
    buis = Leiding(id="buis", type_id="buis125", u=-8, diepte=1.5)
    kabel = Leiding(id="k", type_id="ms150", u=0, diepte=0, buis_id="buis")

    _, posities = controleer(BOVENGROND, [buis, kabel])

    assert posities["k"] == (-8, 1.5)


def test_verwijzing_naar_ontbrekende_buis_geeft_fout() -> None:
    kabel = Leiding(id="k", type_id="ms150", u=0, diepte=0, buis_id="weg")

    with pytest.raises(ValueError, match="buis die niet bestaat"):
        controleer(BOVENGROND, [kabel])


def test_alleen_kabels_mogen_in_een_buis() -> None:
    buis = Leiding(id="buis", type_id="buis160", u=0, diepte=1)
    andere = Leiding(id="b2", type_id="buis110", u=0, diepte=1, buis_id="buis")

    with pytest.raises(ValueError, match="Alleen kabels"):
        controleer(BOVENGROND, [buis, andere])


def test_onbekend_type_wordt_geweigerd() -> None:
    with pytest.raises(ValueError, match="Onbekend leidingtype"):
        Leiding(id="x", type_id="bestaat-niet", u=0, diepte=1)


def test_checklist_is_open_zonder_nieuwe_leiding() -> None:
    status = checklist_status([], heeft_nieuwe_leiding=False)

    assert set(status) == {"dekking", "afstand", "sloot"}
    assert set(status.values()) == {"open"}


def test_checklist_wordt_fout_bij_dekkingsmelding() -> None:
    meldingen, _ = controleer(BOVENGROND, [nieuwe_kabel(-8, 0.5)])

    assert checklist_status(meldingen, True) == {"dekking": "fout", "afstand": "ok", "sloot": "ok"}
