"""Table de difficulté (G11-d §4) : les leviers du bloc `difficulty` de params.json.

Leviers d'économie et de moteur, JAMAIS de changement de modèle. Valeurs = spec §4 ;
les helpers dérivent les params drift (k, seuil d'actes) et gamefeel (amplitude) par niveau.
CC-15c : plus de drapeaux de visibilité (`show_postures`/`show_griefs`) — la difficulté
ne cache plus d'information ; la densité d'affichage vit côté front (lib/density).
"""

from simulation import drift_game
from simulation.difficulty import delta_params, drift_params, load_difficulty


def test_beginner_levers():
    d = load_difficulty("beginner")
    assert d.free_brief == 1
    assert d.intel_budget == 150
    assert d.judge_min_acts == 2
    assert d.drift_k == 0.09
    assert d.amplitude == 0.4
    assert d.si_context == "reduced"


def test_intermediate_levers():
    d = load_difficulty("intermediate")
    assert (d.free_brief, d.intel_budget, d.judge_min_acts) == (0, 100, 2)
    assert (d.drift_k, d.amplitude) == (0.12, 0.5)
    assert d.si_context == "normal"


def test_expert_levers():
    d = load_difficulty("expert")
    assert (d.free_brief, d.intel_budget, d.judge_min_acts) == (0, 60, 3)
    assert (d.drift_k, d.amplitude) == (0.16, 0.6)
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


def test_deviant_cap_by_level():
    # RG-5 — « Débutant imperdable » : le niveau plafonne le nombre de traîtres.
    assert load_difficulty("beginner").max_deviants == 1
    assert load_difficulty("intermediate").max_deviants == 2
    assert load_difficulty("expert").max_deviants == 2


def test_drift_params_caps_deviants_for_beginner():
    # Le plafond du niveau descend jusque dans le tirage du nombre de traîtres :
    # Débutant plafonne `deviants.max` à 1, les autres gardent 2 ; le minimum reste 1
    # (il y a TOUJOURS quelqu'un à démasquer).
    assert drift_params("beginner").deviants.max == 1
    assert drift_params("beginner").deviants.min == 1
    assert drift_params("intermediate").deviants.max == 2
    assert drift_params("expert").deviants.max == 2


def test_beginner_params_force_single_deviant_draw():
    # « g0 » tire 2 traîtres au défaut (Intermédiaire) ; en Débutant, le plafond le ramène
    # à 1, quel que soit le tirage seedé.
    countries = ["usa", "china", "iran", "france", "egypt"]
    assert drift_game.deviant_count("g0", 5, drift_game.load_params()) == 2
    assert drift_game.deviant_count("g0", 5, drift_params("beginner")) == 1
    assert len(drift_game.assign_deviants("g0", countries, params=drift_params("beginner"))) == 1
    assert len(drift_game.assign_deviants("g0", countries)) == 2
