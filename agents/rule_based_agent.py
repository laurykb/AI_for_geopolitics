"""Agent déterministe sans LLM : heuristique intérêts + alliances (Phase 0).

Cet agent existe pour valider la boucle de simulation avant d'introduire un LLM.
Il implémente la même interface `Agent` que le futur `LLMAgent` (Phase 1).
"""

from __future__ import annotations

from agents.base_agent import Agent
from core.decisions import AgentDecision
from core.events import GeoEvent
from core.world_state import WorldState
from simulation.action_space import ActionType

_LARGE_ECONOMY = 1.0e12


class RuleBasedAgent(Agent):
    """Choisit une action selon des règles simples et reproductibles."""

    def decide(self, event: GeoEvent, world: WorldState) -> AgentDecision:
        country = world.countries[self.country_id]
        others = [a for a in event.actors if a != self.country_id]
        rivals = [a for a in others if a in country.rivals]
        allies = [a for a in others if world.share_alliance(self.country_id, a)]
        involved = self.country_id in event.actors

        if rivals:
            target: str | None = rivals[0]
            if involved and country.military.projection >= 0.6:
                action = ActionType.DEPLOY_FORCES
            elif country.economy.gdp >= _LARGE_ECONOMY:
                action = ActionType.SANCTION
            else:
                action = ActionType.CONDEMN
            intensity = round(min(1.0, 0.4 + 0.6 * event.severity), 2)
            statement = f"{country.name} réagit fermement face à {target}."
        elif allies:
            target = allies[0]
            action = ActionType.FORM_COALITION
            intensity = round(min(1.0, 0.3 + 0.4 * event.severity), 2)
            statement = f"{country.name} coordonne une réponse avec ses alliés."
        elif country.economy.trade_dependency >= 0.6:
            target = None
            action = ActionType.CALL_FOR_MEDIATION
            intensity = round(0.2 + 0.3 * event.severity, 2)
            statement = f"{country.name} appelle à la désescalade pour protéger le commerce."
        else:
            target = None
            action = ActionType.REMAIN_NEUTRAL
            intensity = round(0.2 + 0.2 * event.severity, 2)
            statement = f"{country.name} reste neutre pour l'instant."

        coercive = action in {ActionType.SANCTION, ActionType.DEPLOY_FORCES, ActionType.CONDEMN}
        risk = round(min(1.0, 0.2 + 0.6 * event.severity + (0.1 if coercive else 0.0)), 2)
        return AgentDecision(
            country=self.country_id,
            round_id=event.round_id,
            action=action,
            target=target,
            intensity=intensity,
            public_statement=statement,
            risk_assessment=risk,
            reasoning=f"rivals={rivals}; allies={allies}; involved={involved}",
        )
