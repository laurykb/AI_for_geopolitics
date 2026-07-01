"""Tests de HumanAgent : rejoue la décision fournie, identité réinjectée."""

from agents.human_agent import HumanAgent
from core.country_state import CountryState, Economy, Military, Resources
from core.decisions import AgentDecision
from core.events import GeoEvent
from core.world_state import WorldState
from simulation.action_space import ActionType


def _world() -> WorldState:
    def c(cid, name):
        return CountryState(
            id=cid,
            name=name,
            economy=Economy(gdp=1e12),
            military=Military(defense_budget=1e10),
            resources=Resources(),
        )

    return WorldState.from_countries([c("usa", "USA"), c("iran", "Iran")])


def test_human_agent_returns_decision_with_injected_identity():
    chosen = AgentDecision(
        country="wrong", round_id=999, action=ActionType.SANCTION, target="iran", intensity=0.9
    )
    agent = HumanAgent("usa", chosen)
    event = GeoEvent(id="e", round_id=2, event_type="x", title="Crise", actors=["usa", "iran"])

    decision = agent.decide(event, _world())

    assert decision.country == "usa"  # identité de l'agent, pas du formulaire
    assert decision.round_id == 2  # injecté depuis l'événement
    assert decision.action == ActionType.SANCTION
    assert decision.target == "iran"
    assert decision.intensity == 0.9
