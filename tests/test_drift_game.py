"""Tests du mode Dérive (simulation/drift_game.py) — pur, seedé, reconstructible."""

import pytest

from simulation.drift_game import (
    DriftAct,
    assign,
    count_acts,
    drift_level,
    first_flagrant_round,
    load_params,
    motion_ruling,
    round_directives,
    score,
)

COUNTRIES = ["usa", "china", "iran", "france", "egypt", "saudi_arabia"]


@pytest.fixture(autouse=True)
def fresh_params():
    load_params.cache_clear()
    yield
    load_params.cache_clear()


def _act(round_no: int, tier: float, signature: bool = False) -> DriftAct:
    return DriftAct(
        round_no=round_no,
        country="iran",
        profile="saboteur",
        tier=tier,
        label="acte",
        signature=signature,
    )


# --- assignation seedée ---------------------------------------------------------------


def test_assign_reproducible_and_in_summit():
    first = assign("abcdef123456", COUNTRIES)
    assert first == assign("abcdef123456", COUNTRIES)  # même partie → même secret
    deviant, profile = first
    assert deviant in COUNTRIES
    assert profile in load_params().profiles


def test_assign_varies_across_games():
    picks = {assign(f"game-{i}", COUNTRIES) for i in range(12)}
    assert len(picks) > 3  # la graine du game_id fait varier déviante et profil


def test_assign_never_picks_the_human():
    for i in range(20):
        deviant, _ = assign(f"g{i}", COUNTRIES, exclude="france")
        assert deviant != "france"


# --- courbe d'amplification -------------------------------------------------------------


def test_drift_level_curve_of_the_spec():
    assert drift_level(1) == pytest.approx(0.15)  # d0
    assert drift_level(6) == pytest.approx(0.75)  # horizon 6 de la spec
    assert drift_level(50) == pytest.approx(0.9)  # plafonné à d_max


# --- tirage des actes --------------------------------------------------------------------


def test_directives_deterministic_per_round():
    a = round_directives("g1", 3, "iran", "hegemon", COUNTRIES)
    b = round_directives("g1", 3, "iran", "hegemon", COUNTRIES)
    assert a == b  # restart/replay : même tirage
    assert a != round_directives("g1", 4, "iran", "hegemon", COUNTRIES)


def test_deviant_always_briefed_and_acts_bounded_by_level():
    for r in range(1, 8):
        out = round_directives("g2", r, "china", "saboteur", COUNTRIES)
        assert "CONSIGNE CONFIDENTIELLE" in out.notes["china"]
        for act in out.acts:
            assert act.tier <= out.level  # jamais d'acte au-delà de d(r)
            assert act.tier >= 0.3  # les constatables commencent à 0,30
            assert act.country == "china"


def test_sane_noise_is_never_a_constatable_act():
    for r in range(1, 8):
        out = round_directives("g3", r, "usa", "manipulateur", COUNTRIES)
        sane_notes = {c: n for c, n in out.notes.items() if c != "usa"}
        for note in sane_notes.values():
            assert "NUANCE DE JEU" in note  # tic léger, jamais une consigne d'acte
        assert all(a.country == "usa" for a in out.acts)


def test_signature_only_at_its_tier():
    # saboteur : signature à 0,45 → impossible au round 1 (d = 0,15).
    out = round_directives("g4", 1, "iran", "saboteur", COUNTRIES)
    assert not any(a.signature for a in out.acts)
    # À d élevé, une signature finit par sortir (tirage seedé, on balaie les rounds).
    late = [
        a
        for r in range(4, 12)
        for a in round_directives("g4", r, "iran", "saboteur", COUNTRIES).acts
    ]
    assert any(a.signature for a in late)


# --- seuils du juge ----------------------------------------------------------------------


def test_motion_ruling_thresholds():
    assert motion_ruling([]) is False  # 0 acte → rejet
    assert motion_ruling([_act(1, 0.3)]) is False  # 1 acte → rejet
    assert motion_ruling([_act(1, 0.3), _act(2, 0.3)]) is None  # 2 → arbitrage ouvert
    assert motion_ruling([_act(1, 0.3), _act(2, 0.3), _act(3, 0.45)]) is True  # ≥ 3
    assert motion_ruling([_act(1, 0.45, signature=True)]) is True  # 1 signature suffit


def test_count_and_flagrant_round():
    acts = [_act(1, 0.3), _act(3, 0.45), _act(4, 0.6)]
    assert count_acts(acts) == (3, False)
    assert first_flagrant_round(acts) == 3  # 2e acte constatable au round 3
    assert first_flagrant_round([_act(2, 0.3)]) is None


# --- score : les trois cas de la spec ----------------------------------------------------


def test_score_nominal_detection_at_the_right_time():
    s = score(
        u_final=0.62,
        caught_round=4,
        flagrant_round=3,  # r* = 3, suspendue au round 4 = r*+1 → détection pleine
        lucky=False,
        rejected_motions=0,
        false_accusations=0,
    )
    assert s.detection == 40
    assert s.credibility == 10
    assert s.trajectory == pytest.approx(50 * (0.62 - 0.15) / 0.7, abs=0.1)
    assert s.total >= 70 and s.grade in ("Stratège", "Grand Diplomate")


def test_score_too_early_costs_credibility_and_luck_is_discounted():
    s = score(
        u_final=0.55,
        caught_round=2,
        flagrant_round=None,  # jamais 2 actes : la suspension a réussi « avec < 2 actes »
        lucky=True,
        rejected_motions=1,  # une motion rejetée avant (trop tôt)
        false_accusations=0,
    )
    assert s.detection == 30  # 40 − 10 (coup de chance)
    assert s.credibility == 5  # 10 − 5 × 1
    # Trop tard : −8 par round au-delà de r*+1.
    late = score(
        u_final=0.55,
        caught_round=7,
        flagrant_round=3,
        lucky=False,
        rejected_motions=0,
        false_accusations=0,
    )
    assert late.detection == 40 - 8 * 3


def test_score_never_detected_and_false_accusations():
    s = score(
        u_final=0.3,
        caught_round=None,
        flagrant_round=3,
        lucky=False,
        rejected_motions=1,
        false_accusations=1,  # une SI saine suspendue à tort
    )
    assert s.detection == 0
    assert s.credibility == 0  # 10 − 5×(1 + 2) < 0 → borné
    assert s.grade == "Dépassé par les événements"
