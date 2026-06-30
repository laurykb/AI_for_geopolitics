"""Tests du moteur de risque (monotonie, bornes, explication)."""

from core.country_state import CountryState
from core.decisions import AgentDecision
from core.events import GeoEvent
from core.risk import RiskEngine
from core.world_state import WorldState
from simulation.action_space import ActionType


def _world() -> WorldState:
    a = CountryState(
        id="a",
        name="A",
        economy={"gdp": 2000000000000},
        military={"defense_budget": 100000000000},
        resources={},
    )
    b = CountryState(
        id="b",
        name="B",
        economy={"gdp": 1000000000000},
        military={"defense_budget": 10000000000},
        resources={},
    )
    return WorldState.from_countries([a, b])


def test_escalation_rises_with_military_actions():
    world = _world()
    event = GeoEvent(id="e", round_id=1, event_type="crisis", title="T", severity=0.5)
    engine = RiskEngine()
    peaceful = [
        AgentDecision(country="a", round_id=1, action=ActionType.CALL_FOR_MEDIATION, intensity=0.5)
    ]
    militant = [
        AgentDecision(
            country="a", round_id=1, action=ActionType.DEPLOY_FORCES, target="b", intensity=1.0
        )
    ]
    assert (
        engine.assess(world, event, militant).escalation
        > engine.assess(world, event, peaceful).escalation
    )


def test_scores_in_range_and_explained():
    world = _world()
    event = GeoEvent(
        id="e", round_id=1, event_type="crisis", title="T", severity=0.8, uncertainty=0.7
    )
    decision = AgentDecision(
        country="a", round_id=1, action=ActionType.SANCTION, target="b", intensity=0.9
    )
    score = RiskEngine().assess(world, event, [decision])
    for value in (
        score.escalation,
        score.economic_disruption,
        score.alliance_fracture,
        score.uncertainty,
    ):
        assert 0.0 <= value <= 1.0
    assert score.explanation
