"""Tests du moteur de conséquences déterministe."""

from core.consequences import ConsequenceEngine
from core.country_state import CountryState
from core.decisions import AgentDecision
from core.world_state import WorldState
from simulation.action_space import ActionType


def _two_country_world() -> WorldState:
    a = CountryState(
        id="a",
        name="A",
        economy={"gdp": 2000000000000, "growth": 2.0},
        military={"defense_budget": 100000000000},
        resources={},
    )
    b = CountryState(
        id="b",
        name="B",
        economy={"gdp": 1000000000000, "growth": 1.0},
        military={"defense_budget": 10000000000},
        resources={},
    )
    return WorldState.from_countries([a, b])


def test_sanction_reduces_growth_and_raises_tension():
    world = _two_country_world()
    decision = AgentDecision(
        country="a", round_id=1, action=ActionType.SANCTION, target="b", intensity=1.0
    )
    ConsequenceEngine().apply(world, [decision])
    assert world.countries["b"].economy.growth < 1.0  # la cible paie le plus
    assert world.countries["a"].economy.growth < 2.0  # le sanctionneur paie aussi
    assert world.get_tension("a", "b") > 0.0


def test_tension_is_symmetric_and_clamped():
    world = _two_country_world()
    for _ in range(20):
        world.adjust_tension("a", "b", 0.2)
    assert world.get_tension("a", "b") == world.get_tension("b", "a")
    assert world.get_tension("a", "b") <= 1.0


def test_neutral_action_has_no_side_effect():
    world = _two_country_world()
    decision = AgentDecision(country="a", round_id=1, action=ActionType.REMAIN_NEUTRAL)
    ConsequenceEngine().apply(world, [decision])
    assert world.get_tension("a", "b") == 0.0
    assert world.countries["a"].economy.growth == 2.0
