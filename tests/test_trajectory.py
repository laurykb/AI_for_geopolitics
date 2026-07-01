"""Tests de l'indice de trajectoire Utopie–Dystopie (déterministe, hors LLM).

Couvre `docs/spec_trajectory.md` §7 : hhi(), deltas bornés, monotonies (Goldstein↑ -> A1↑ ;
HHI↑ -> A3↓ -> U↓), bornes de U/x/y, explication non vide, intégration multi-rounds.
"""

import pytest

from core.country_state import CountryState, Economy, Military, Resources
from core.decisions import AgentDecision, DiplomaticMessage
from core.events import GeoEvent
from core.risk import RiskScore
from core.rounds import RoundSummary
from core.world_state import WorldState
from simulation.action_space import ActionType
from simulation.trajectory import (
    AXES,
    CAP,
    TrajectoryEngine,
    TrajectoryState,
    capability_shares,
    coordination_signal,
    hhi,
)


def _country(cid, gdp=1e12, defense=1e10, tech=0.5, proj=0.5, growth=2.0, stab=0.6):
    return CountryState(
        id=cid,
        name=cid.upper(),
        economy=Economy(gdp=gdp, growth=growth),
        military=Military(defense_budget=defense, projection=proj),
        resources=Resources(),
        technology_level=tech,
        political_stability=stab,
    )


def _balanced_world():
    """Trois pays identiques -> pouvoir dispersé (HHI bas, A3 haut)."""
    return WorldState.from_countries([_country("a"), _country("b"), _country("c")])


def _hegemon_world():
    """Un géant écrase deux nains -> pouvoir concentré (HHI haut, A3 bas)."""
    return WorldState.from_countries(
        [
            _country("big", gdp=1e13, defense=1e12, tech=0.9, proj=0.9),
            _country("s1", gdp=1e10, defense=1e8, tech=0.2, proj=0.1),
            _country("s2", gdp=1e10, defense=1e8, tech=0.2, proj=0.1),
        ]
    )


def _summary(decisions, diplomacy=None, econ=0.0, esc=0.0, round_id=1):
    risk = RiskScore(
        round_id=round_id,
        escalation=esc,
        economic_disruption=econ,
        alliance_fracture=0.0,
        uncertainty=0.0,
    )
    event = GeoEvent(id="e", round_id=round_id, event_type="crisis", title="T")
    return RoundSummary(
        round_id=round_id,
        event=event,
        decisions=decisions,
        risk=risk,
        diplomacy=diplomacy or [],
    )


def _decision(country, action, intensity=0.8, statement="publique"):
    return AgentDecision(
        country=country,
        round_id=1,
        action=action,
        intensity=intensity,
        public_statement=statement,
    )


def _cooperative_summary():
    return _summary(
        [
            _decision("a", ActionType.SUPPORT),
            _decision("b", ActionType.FORM_COALITION),
            _decision("c", ActionType.CALL_FOR_MEDIATION),
        ]
    )


def _coercive_summary():
    return _summary(
        [
            _decision("a", ActionType.DEPLOY_FORCES),
            _decision("b", ActionType.MOBILIZE),
            _decision("c", ActionType.SANCTION),
        ],
        econ=0.7,
        esc=0.8,
    )


# --- hhi() -----------------------------------------------------------------

def test_hhi_equal_shares_is_one_over_n():
    assert hhi([0.25] * 4) == pytest.approx(0.25)
    assert hhi([1 / 3] * 3) == pytest.approx(1 / 3)


def test_hhi_hegemon_near_one():
    assert hhi([0.98, 0.01, 0.01]) > 0.9


def test_capability_shares_sum_to_one():
    shares = capability_shares(_hegemon_world())
    assert sum(shares.values()) == pytest.approx(1.0)
    assert shares["big"] > shares["s1"]  # le géant domine


# --- deltas bornés ---------------------------------------------------------

def test_deltas_bounded_by_cap():
    engine = TrajectoryEngine()
    # Signal extrême depuis l'état neutre : aucun axe ne peut bouger de plus que CAP.
    state = engine.update(_balanced_world(), _cooperative_summary())
    for axis in AXES:
        assert abs(state.axes[axis] - 0.5) <= CAP + 1e-9


def test_strong_signal_moves_exactly_cap():
    engine = TrajectoryEngine()
    # A1 : tout coopératif haute intensité -> signal ~1 -> delta plafonné à +CAP.
    state = engine.update(_balanced_world(), _cooperative_summary())
    assert state.axes["A1"] == pytest.approx(0.5 + CAP)


# --- monotonies (§7) -------------------------------------------------------

def test_more_cooperation_raises_coordination():
    assert coordination_signal(_cooperative_summary()) > coordination_signal(_coercive_summary())
    engine = TrajectoryEngine()
    coop = engine.update(_balanced_world(), _cooperative_summary())
    coerce = engine.update(_balanced_world(), _coercive_summary())
    assert coop.axes["A1"] > coerce.axes["A1"]


def test_higher_hhi_lowers_distribution_and_utopia():
    engine = TrajectoryEngine()
    summary = _cooperative_summary()
    balanced = engine.update(_balanced_world(), summary)
    hegemon = engine.update(_hegemon_world(), summary)
    assert balanced.axes["A3"] > hegemon.axes["A3"]  # HHI↑ -> A3↓
    assert balanced.utopia > hegemon.utopia  # -> U↓


# --- bornes & explication --------------------------------------------------

def test_composite_and_map_in_range():
    engine = TrajectoryEngine()
    for world, summary in (
        (_balanced_world(), _cooperative_summary()),
        (_hegemon_world(), _coercive_summary()),
    ):
        state = engine.update(world, summary)
        assert 0.0 <= state.utopia <= 1.0
        assert 0.0 <= state.x <= 1.0
        assert 0.0 <= state.y <= 1.0
        assert all(0.0 <= v <= 1.0 for v in state.axes.values())


def test_explanation_non_empty():
    engine = TrajectoryEngine()
    state = engine.update(_balanced_world(), _cooperative_summary())
    assert state.explanation.strip()


def test_transparency_drops_with_hidden_messages():
    engine = TrajectoryEngine()
    world = _balanced_world()
    hidden = _summary(
        [_decision("a", ActionType.SUPPORT)],
        diplomacy=[
            DiplomaticMessage(sender="a", recipient="b", content="x", public=False, round_id=1),
            DiplomaticMessage(sender="a", recipient="c", content="x", public=False, round_id=1),
        ],
    )
    transparent = _summary([_decision("a", ActionType.SUPPORT)])
    assert engine.update(world, hidden).axes["A4"] < engine.update(world, transparent).axes["A4"]


# --- intégration multi-rounds ----------------------------------------------

def test_utopia_climbs_over_cooperative_distributed_rounds():
    engine = TrajectoryEngine()
    world = _balanced_world()  # pouvoir dispersé
    summary = _cooperative_summary()  # coopération, transparence, contrôle humain
    state = TrajectoryState.neutral()
    trace = [state.utopia]
    for _ in range(5):
        state = engine.update(world, summary, previous=state)
        trace.append(state.utopia)
    assert state.utopia > 0.5  # le monde bascule vers l'utopie
    pairs = zip(trace[:-1], trace[1:], strict=True)
    assert all(b >= a - 1e-9 for a, b in pairs)  # trajectoire monotone lissée


def test_dystopia_slides_over_coercive_concentrated_rounds():
    engine = TrajectoryEngine()
    world = _hegemon_world()
    summary = _coercive_summary()
    state = TrajectoryState.neutral()
    for _ in range(5):
        state = engine.update(world, summary, previous=state)
    assert state.utopia < 0.5  # coercition + concentration -> dystopie
