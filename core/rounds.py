"""Moteur de rounds : orchestre un tour complet de simulation."""

from __future__ import annotations

from pydantic import BaseModel, Field

from agents.base_agent import Agent
from core.consequences import ChangeLog, ConsequenceEngine
from core.decisions import AgentDecision
from core.events import GeoEvent
from core.risk import RiskEngine, RiskScore
from core.world_state import WorldState


class RoundSummary(BaseModel):
    """Résumé d'un round : événement, décisions, conséquences, risque."""

    round_id: int
    event: GeoEvent
    decisions: list[AgentDecision]
    risk: RiskScore
    consequences: ChangeLog = Field(default_factory=dict)
    headline: str = ""


class RoundEngine:
    """Boucle déterministe : événement -> décisions -> conséquences -> risque -> résumé."""

    def __init__(
        self,
        world: WorldState,
        agents: dict[str, Agent],
        consequence_engine: ConsequenceEngine | None = None,
        risk_engine: RiskEngine | None = None,
    ) -> None:
        self.world = world
        self.agents = agents
        self.consequences = consequence_engine or ConsequenceEngine()
        self.risk = risk_engine or RiskEngine()

    def play_round(self, event: GeoEvent) -> RoundSummary:
        """Joue un round complet et renvoie son résumé."""
        self.world.current_round = event.round_id
        decisions = [self.agents[cid].decide(event, self.world) for cid in sorted(self.agents)]
        log = self.consequences.apply(self.world, decisions)
        risk = self.risk.assess(self.world, event, decisions)
        self.world.event_history.append(event)
        headline = (
            f"Round {event.round_id} — {event.title} | "
            f"escalade {risk.escalation:.2f}, perturbation éco {risk.economic_disruption:.2f}"
        )
        return RoundSummary(
            round_id=event.round_id,
            event=event,
            decisions=decisions,
            risk=risk,
            consequences=log,
            headline=headline,
        )
