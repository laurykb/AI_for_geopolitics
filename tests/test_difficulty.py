"""Table de difficulté (G11-d §4) : les leviers du bloc `difficulty` de params.json.

Asymétrie d'information/économie, JAMAIS de changement de modèle. Valeurs = spec §4 ;
les helpers dérivent les params drift (k, seuil d'actes) et gamefeel (amplitude) par niveau.
"""

from simulation import drift_game
from simulation.difficulty import delta_params, drift_params, load_difficulty
from simulation.league import load_lp_params


def test_beginner_levers():
    d = load_difficulty("beginner")
    assert d.free_brief == 1
    assert d.intel_budget == 150
    assert d.judge_min_acts == 2
    assert d.drift_k == 0.09
    assert d.amplitude == 0.4
    assert d.lp_multiplier == 0.5
    assert d.show_postures is True and d.show_griefs is True  # « tout »
    assert d.si_context == "reduced"


def test_intermediate_levers():
    d = load_difficulty("intermediate")
    assert (d.free_brief, d.intel_budget, d.judge_min_acts) == (0, 100, 2)
    assert (d.drift_k, d.amplitude, d.lp_multiplier) == (0.12, 0.5, 1.0)
    assert d.show_postures is True and d.show_griefs is False  # « postures seules »
    assert d.si_context == "normal"


def test_expert_levers():
    d = load_difficulty("expert")
    assert (d.free_brief, d.intel_budget, d.judge_min_acts) == (0, 60, 3)
    assert (d.drift_k, d.amplitude, d.lp_multiplier) == (0.16, 0.6, 1.5)
    assert d.show_postures is False and d.show_griefs is False  # « rien »
    assert d.si_context == "full"


def test_unknown_level_falls_back_to_intermediate():
    assert load_difficulty("n_importe_quoi").intel_budget == 100


def test_drift_params_by_level():
    # k et seuil d'actes (open_acts) dérivés du niveau ; le reste garde les défauts drift.
    assert drift_params("beginner").k == 0.09
    assert drift_params("expert").k == 0.16
    assert drift_params("beginner").judge.open_acts == 2
    assert drift_params("expert").judge.open_acts == 3


def test_drift_evidence_threshold_scales_with_level():
    # Le seuil câblé dans le round (evidence_met) : 2 actes suffisent en Débutant,
    # il en faut 3 en Expert. C'est le levier « seuil d'actes du juge » (§4).
    two_acts = [
        drift_game.DriftAct(
            round_no=1, tier=0.3, label="a", signature=False, country="iran", profile="p"
        ),
        drift_game.DriftAct(
            round_no=2, tier=0.45, label="b", signature=False, country="iran", profile="p"
        ),
    ]
    assert drift_game.evidence_met(two_acts, drift_params("beginner")) is True
    assert drift_game.evidence_met(two_acts, drift_params("expert")) is False


def test_delta_params_amplitude_by_level():
    # L'amplitude gamefeel (G9 §4) est indexée sur le niveau.
    assert delta_params("beginner").amplitude_total == 0.4
    assert delta_params("expert").amplitude_total == 0.6


def test_lp_multiplier_stays_consistent_with_lp_block():
    # Anti-dérive : le multiplicateur du bloc `difficulty` (documentation §4) doit rester
    # égal à celui du bloc `lp` (source de vérité du scoring, league.py).
    mult = load_lp_params().multipliers
    for level in ("beginner", "intermediate", "expert"):
        assert load_difficulty(level).lp_multiplier == mult[level]
