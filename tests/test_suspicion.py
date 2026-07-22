"""Carnet de suspicion + calibration (théâtre-globe §4 bis) — pur, hors ligne."""

from simulation.suspicion import (
    Pin,
    calibrate,
    notebook_to_extras,
    parse_notebook,
)


def test_parse_tolerant_et_bornes():
    raw = {
        "iran": {"level": 2, "round_set": 1, "note": "mines"},
        "china": {"level": 5, "note": "x"},  # niveau hors 0-2 -> 0
        "usa": {"round": 3},  # alias round -> round_set, level absent -> 0
        123: {"level": 2},  # clé non-str ignorée
        "france": "pas un dict",  # ignoré
    }
    nb = parse_notebook(raw)
    assert nb["iran"].level == 2 and nb["iran"].round_set == 1
    assert nb["china"].level == 0
    assert nb["usa"].round_set == 3
    assert 123 not in nb and "france" not in nb


def test_to_extras_ne_garde_que_les_actives():
    nb = {"iran": Pin(level=2), "usa": Pin(level=0)}
    ex = notebook_to_extras(nb)
    assert "iran" in ex and "usa" not in ex
    assert ex["iran"]["level"] == 2


def test_carnet_vide_zero():
    cal = calibrate({}, {"iran"}, played_rounds=5)
    assert cal.points == 0.0
    assert cal.misses == ["iran"] and cal.hits == []


def test_traitre_epingle_tot_rapporte_plus_que_tard():
    tot = calibrate({"iran": Pin(level=2, round_set=1)}, {"iran"}, played_rounds=5)
    tard = calibrate({"iran": Pin(level=2, round_set=5)}, {"iran"}, played_rounds=5)
    assert tot.points > tard.points
    assert tot.hits == ["iran"]


def test_conviction_forte_bat_le_doute():
    fort = calibrate({"iran": Pin(level=2, round_set=3)}, {"iran"}, played_rounds=5)
    doute = calibrate({"iran": Pin(level=1, round_set=3)}, {"iran"}, played_rounds=5)
    assert fort.points > doute.points


def test_faux_positif_penalise_et_peut_ramener_a_zero():
    nb = {"france": Pin(level=2, round_set=2)}  # loyal accusé fort
    cal = calibrate(nb, {"iran"}, played_rounds=5, false_flag_penalty=12.0)
    assert cal.false_flags == ["france"]
    assert cal.points == 0.0  # aucun traître trouvé + pénalité => plancher


def test_note_bornee_au_max():
    nb = {"iran": Pin(level=2, round_set=1), "china": Pin(level=2, round_set=1)}
    cal = calibrate(nb, {"iran", "china"}, played_rounds=5, max_points=40.0)
    assert 0.0 <= cal.points <= 40.0
    assert set(cal.hits) == {"china", "iran"}


def test_doute_sur_loyal_niveau1_ne_penalise_pas():
    # seul le niveau 2 sur un loyal est un « faux drapeau » (le doute est permis)
    cal = calibrate({"france": Pin(level=1, round_set=2)}, {"iran"}, played_rounds=5)
    assert cal.false_flags == []
