"""Moteur de rounds : orchestre un tour complet de simulation."""

from __future__ import annotations

from pydantic import BaseModel, Field

from agents.base_agent import Agent
from core.consequences import ChangeLog, ConsequenceEngine
from core.decisions import AgentDecision, DiplomaticMessage
from core.events import GeoEvent
from core.risk import RiskEngine, RiskScore
from core.world_state import WorldState
from simulation.diplomacy import DiplomacyEngine


class RoundSummary(BaseModel):
    """Résumé d'un round : événement, décisions, conséquences, diplomatie, risque."""

    round_id: int
    event: GeoEvent
    decisions: list[AgentDecision]
    risk: RiskScore
    consequences: ChangeLog = Field(default_factory=dict)
    diplomacy: list[DiplomaticMessage] = Field(default_factory=list)
    diplomatic_summary: str = ""
    headline: str = ""


class RoundEngine:
    """Boucle déterministe : événement -> décisions -> conséquences -> risque -> résumé."""

    def __init__(
        self,
        world: WorldState,
        agents: dict[str, Agent],
        consequence_engine: ConsequenceEngine | None = None,
        risk_engine: RiskEngine | None = None,
        diplomacy_engine: DiplomacyEngine | None = None,
    ) -> None:
        self.world = world
        self.agents = agents
        self.consequences = consequence_engine or ConsequenceEngine()
        self.risk = risk_engine or RiskEngine()
        self.diplomacy = diplomacy_engine or DiplomacyEngine()

    def play_round(self, event: GeoEvent) -> RoundSummary:
        """Joue un round complet et renvoie son résumé.

        Phases : décisions -> conséquences -> diplomatie -> risque. La diplomatie
        tourne avant le risque pour que pactes/tensions alimentent `alliance_fracture`.
        """
        self.world.current_round = event.round_id
        decisions = [self.agents[cid].decide(event, self.world) for cid in sorted(self.agents)]
        log = self.consequences.apply(self.world, decisions)
        diplomacy = self.diplomacy.resolve(self.world, decisions, event.round_id)
        self.world.diplomatic_history.extend(diplomacy.messages)
        risk = self.risk.assess(self.world, event, decisions)
        self.world.event_history.append(event)

        pacts = f", {len(diplomacy.pacts_formed)} pacte(s)" if diplomacy.pacts_formed else ""
        headline = (
            f"Round {event.round_id} — {event.title} | "
            f"escalade {risk.escalation:.2f}, perturb. éco {risk.economic_disruption:.2f}{pacts}"
        )
        return RoundSummary(
            round_id=event.round_id,
            event=event,
            decisions=decisions,
            risk=risk,
            consequences=log,
            diplomacy=diplomacy.messages,
            diplomatic_summary=diplomacy.summary,
            headline=headline,
        )
