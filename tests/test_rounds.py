"""Tests du moteur de rounds (orchestration d'un tour)."""

from agents.rule_based_agent import RuleBasedAgent
from core.country_state import CountryState
from core.events import GeoEvent
from core.rounds import RoundEngine
from core.world_state import WorldState


def _usa_iran_world() -> WorldState:
    usa = CountryState(
        id="usa", name="USA",
        economy={"gdp": 25000000000000},
        military={"defense_budget": 800000000000, "projection": 0.9},
        resources={}, rivals=["iran"],
    )
    iran = CountryState(
        id="iran", name="Iran",
        economy={"gdp": 400000000000},
        military={"defense_budget": 20000000000},
        resources={}, rivals=["usa"],
    )
    return WorldState.from_countries([usa, iran])


def _event() -> GeoEvent:
    return GeoEvent(
        id="e1", round_id=1, event_type="maritime_attack",
        title="Crise", actors=["iran"], severity=0.6,
    )


def test_play_round_returns_decisions_for_all_agents():
    world = _usa_iran_world()
    agents = {cid: RuleBasedAgent(cid) for cid in world.countries}
    summary = RoundEngine(world, agents).play_round(_event())
    assert len(summary.decisions) == 2
    assert world.current_round == 1
    assert world.event_history[-1].id == "e1"
    assert summary.headline


def test_usa_pressures_its_rival_iran():
    world = _usa_iran_world()
    agents = {cid: RuleBasedAgent(cid) for cid in world.countries}
    RoundEngine(world, agents).play_round(_event())
    assert world.get_tension("usa", "iran") > 0.0
