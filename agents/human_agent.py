"""Agent contrôlé par un humain (Phase 5) : renvoie la décision fournie par l'UI.

Implémente la même interface `Agent` que les autres → un humain peut incarner un pays
sans aucune modification du `RoundEngine`.
"""

from __future__ import annotations

from agents.base_agent import Agent
from core.decisions import AgentDecision
from core.events import GeoEvent
from core.world_state import WorldState


class HumanAgent(Agent):
    """Rejoue une décision choisie par l'humain, avec identité réinjectée."""

    def __init__(self, country_id: str, decision: AgentDecision) -> None:
        super().__init__(country_id)
        self.decision = decision

    def decide(self, event: GeoEvent, world: WorldState) -> AgentDecision:
        # Réinjecte country/round_id : l'identité est celle de l'agent, pas du formulaire.
        return self.decision.model_copy(
            update={"country": self.country_id, "round_id": event.round_id}
        )
