"""Tests G9 §4 — amplitude des deltas indexée sur l'horizon, momentum, postures."""

from core.country_state import CountryState, Economy, Military, Resources
from core.world_state import WorldState
from simulation.gamefeel import (
    POSTURE_DESPERATE,
    POSTURE_PRESSURE,
    POSTURE_PROSPER,
    POSTURE_STABLE,
    IndexHistory,
    delta_scale,
    posture,
    posture_note,
    record_round,
    tuning_for,
)
from simulation.grudges import load_gamefeel_params
from simulation.negotiation import Verdict, apply_verdict


def _country(cid: str, name: str, **kw) -> CountryState:
    return CountryState(
        id=cid,
        name=name,
        economy=Economy(gdp=1.0e12, growth=2.0, trade_dependency=0.5),
        military=Military(defense_budget=1.0e10, projection=0.7),
        resources=Resources(),
        **kw,
    )


def _world() -> WorldState:
    return WorldState.from_countries(
        [_country("usa", "USA"), _country("iran", "Iran", political_stability=0.5)]
    )


# --- amplitude indexée sur l'horizon (§4-a) ---------------------------------------


def test_delta_scale_is_budget_over_horizon():
    p = load_gamefeel_params().deltas
    # A = 0.5 : horizon 5 → amplitude de round 0.10 (facteur 1, parité avec l'existant)
    assert delta_scale(5, p) == 1.0
    # horizon 20 → érosion lente : facteur 0.25
    assert delta_scale(20, p) == 0.25


def test_apply_verdict_scales_deltas_with_horizon():
    world = _world()
    before = world.countries["iran"].political_stability
    verdict = Verdict(attribute_deltas={"iran": {"stabilité": -0.10}})
    deltas = apply_verdict(world, verdict, tuning=tuning_for(horizon=20))
    assert len(deltas) == 1
    # -0.10 × 0.25 = -0.025 (le même round pèse 4× moins sur une partie 4× plus longue)
    assert abs(deltas[0].change - (-0.025)) < 1e-9
    assert abs(world.countries["iran"].political_stability - (before - 0.025)) < 1e-9


def test_judge_cannot_exceed_cap_times_round_amplitude():
    world = _world()
    verdict = Verdict(attribute_deltas={"iran": {"stabilité": -0.9}})
    deltas = apply_verdict(world, verdict, tuning=tuning_for(horizon=5))
    # cap = 1.5 × 0.10 = 0.15 à l'horizon 5
    assert abs(deltas[0].change - (-0.15)) < 1e-9


def test_floor_keeps_indices_above_zero():
    world = _world()
    world.countries["iran"].political_stability = 0.10
    verdict = Verdict(attribute_deltas={"iran": {"stabilité": -0.15}})
    apply_verdict(world, verdict, tuning=tuning_for(horizon=5))
    p = load_gamefeel_params().deltas
    assert world.countries["iran"].political_stability == p.floor  # jamais à zéro absolu


def test_apply_verdict_without_tuning_keeps_legacy_behaviour():
    world = _world()
    verdict = Verdict(attribute_deltas={"iran": {"stabilité": -0.9}})
    deltas = apply_verdict(world, verdict)
    assert abs(deltas[0].change - (-0.15)) < 1e-9  # cap historique inchangé


# --- momentum (§4-b) ----------------------------------------------------------------


def _falling_history(cid: str = "iran", label: str = "stabilité") -> IndexHistory:
    history = IndexHistory()
    for value in (0.8, 0.7, 0.6, 0.5):  # 3 baisses consécutives
        history.record(cid, label, value)
    return history


def test_three_consecutive_drops_amplify_the_next_drop():
    world = _world()
    world.countries["iran"].political_stability = 0.5
    tuning = tuning_for(horizon=5, history=_falling_history())
    verdict = Verdict(attribute_deltas={"iran": {"stabilité": -0.10}})
    deltas = apply_verdict(world, verdict, tuning=tuning)
    assert abs(deltas[0].change - (-0.13)) < 1e-9  # ×1.3 : spirale de crise


def test_momentum_broken_by_a_round_without_drop():
    history = _falling_history()
    history.record("iran", "stabilité", 0.5)  # round sans baisse → remise à zéro
    world = _world()
    world.countries["iran"].political_stability = 0.5
    tuning = tuning_for(horizon=5, history=history)
    verdict = Verdict(attribute_deltas={"iran": {"stabilité": -0.10}})
    deltas = apply_verdict(world, verdict, tuning=tuning)
    assert abs(deltas[0].change - (-0.10)) < 1e-9  # pas de multiplicateur


def test_three_consecutive_rises_amplify_the_next_rise_capped():
    history = IndexHistory()
    for value in (0.3, 0.4, 0.5, 0.6):
        history.record("iran", "stabilité", value)
    world = _world()
    world.countries["iran"].political_stability = 0.6
    tuning = tuning_for(horizon=5, history=history)
    verdict = Verdict(attribute_deltas={"iran": {"stabilité": 0.10}})
    deltas = apply_verdict(world, verdict, tuning=tuning)
    assert abs(deltas[0].change - 0.12) < 1e-9  # ×1.2 : cercle vertueux


def test_momentum_is_per_country_and_per_index():
    tuning = tuning_for(horizon=5, history=_falling_history("iran", "stabilité"))
    world = _world()
    verdict = Verdict(attribute_deltas={"usa": {"stabilité": -0.10}})
    deltas = apply_verdict(world, verdict, tuning=tuning)
    assert abs(deltas[0].change - (-0.10)) < 1e-9  # la spirale de l'iran n'atteint pas les usa


# --- postures (§4-b) ------------------------------------------------------------------


def test_record_round_tracks_world_values():
    world = _world()
    history = IndexHistory()
    record_round(world, history)
    assert history.series("iran", "stabilité") == [0.5]
    assert history.series("usa", "croissance") == [2.0]


def test_posture_states_from_three_round_trend():
    history = IndexHistory()
    for stab, tech in ((0.8, 0.6), (0.7, 0.55), (0.6, 0.5), (0.5, 0.45)):
        history.record("iran", "stabilité", stab)
        history.record("iran", "techno", tech)
    assert posture(history, "iran") == POSTURE_DESPERATE

    slow = IndexHistory()
    for stab in (0.62, 0.60, 0.58, 0.55):
        slow.record("iran", "stabilité", stab)
    assert posture(slow, "iran") == POSTURE_PRESSURE

    up = IndexHistory()
    for stab in (0.5, 0.55, 0.6, 0.65):
        up.record("iran", "stabilité", stab)
    assert posture(up, "iran") == POSTURE_PROSPER

    flat = IndexHistory()
    for stab in (0.5, 0.5, 0.51, 0.5):
        flat.record("iran", "stabilité", stab)
    assert posture(flat, "iran") == POSTURE_STABLE
    assert posture(IndexHistory(), "iran") == POSTURE_STABLE  # sans historique : stable


def test_posture_note_speaks_the_fall():
    history = IndexHistory()
    for growth, stab in ((3.0, 0.8), (2.5, 0.7), (2.0, 0.6), (1.5, 0.5)):
        history.record("iran", "croissance", growth)
        history.record("iran", "stabilité", stab)
    note = posture_note(history, "iran")
    assert "aux abois" in note
    assert "stabilité" in note or "économie" in note

    assert posture_note(IndexHistory(), "iran") == ""  # stable → pas de ligne


def test_history_roundtrips_through_snapshot():
    history = _falling_history()
    restored = IndexHistory.model_validate(history.model_dump(mode="json"))
    assert restored.series("iran", "stabilité") == history.series("iran", "stabilité")
