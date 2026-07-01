"""Intégration : un round complet où une coalition se forme via la phase diplomatie."""

from agents.base_agent import Agent
from core.country_state import CountryState, Economy, Military, Resources
from core.events import GeoEvent
from core.rounds import RoundEngine
from core.world_state import WorldState
from simulation.action_space import ActionType
from simulation.diplomacy import pact_id


class _ProposerAgent(Agent):
    """Agent de test : propose une coalition à une cible fixe."""

    def __init__(self, country_id: str, target: str) -> None:
        super().__init__(country_id)
        self.target = target

    def decide(self, event, world):
        from core.decisions import AgentDecision

        return AgentDecision(
            country=self.country_id,
            round_id=event.round_id,
            action=ActionType.FORM_COALITION,
            target=self.target,
        )


def _country(cid: str, name: str, **kw) -> CountryState:
    return CountryState(
        id=cid,
        name=name,
        economy=Economy(gdp=1.0e12),
        military=Military(defense_budget=1.0e10),
        resources=Resources(),
        **kw,
    )


def test_round_forms_pact_and_reports_it():
    world = WorldState.from_countries([_country("france", "France"), _country("usa", "USA")])
    agents = {
        "france": _ProposerAgent("france", "usa"),
        "usa": _ProposerAgent("usa", "france"),
    }
    engine = RoundEngine(world, agents)
    event = GeoEvent(id="e1", round_id=1, event_type="test", title="Coalition", actors=["france"])

    summary = engine.play_round(event)

    # un pacte s'est formé et il est visible dans le résumé public
    assert world.share_alliance("france", "usa")
    assert pact_id("france", "usa") in world.countries["usa"].alliances
    assert "Pactes" in summary.diplomatic_summary
    assert "pacte" in summary.headline
    # négociation visible + tracée dans l'historique du monde
    assert summary.diplomacy
    assert world.diplomatic_history
    # risque toujours borné et expliqué
    assert 0.0 <= summary.risk.alliance_fracture <= 1.0
    assert summary.risk.explanation
