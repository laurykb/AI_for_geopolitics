"""Modèle de vue d'un run : joue le scénario mer Rouge (rule-based) et collecte l'état.

Sert le point d'API `GET /api/run` (backend) et reste réutilisable par d'autres vues.
Lecture seule, déterministe, sans GPU.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from agents.rule_based_agent import RuleBasedAgent
from core.country_state import CountryState
from core.decisions import DiplomaticMessage
from core.rounds import RoundEngine, RoundSummary
from simulation.loader import load_scenario_countries, load_scenario_events, load_world

_PACT_PREFIX = "pact:"


class DashboardData(BaseModel):
    """Données d'un run complet (sérialisable par l'API)."""

    countries: list[CountryState]
    summaries: list[RoundSummary]
    tensions: dict[str, dict[str, float]] = Field(default_factory=dict)
    alliances: dict[str, list[str]] = Field(default_factory=dict)
    pacts: list[str] = Field(default_factory=list)
    messages: list[DiplomaticMessage] = Field(default_factory=list)

    @property
    def country_ids(self) -> list[str]:
        return [c.id for c in self.countries]


def run_red_sea() -> DashboardData:
    """Joue le scénario mer Rouge en rule-based et renvoie l'état du run."""
    world = load_world(only=load_scenario_countries())
    agents = {cid: RuleBasedAgent(cid) for cid in world.countries}
    engine = RoundEngine(world, agents)
    summaries = [engine.play_round(event) for event in load_scenario_events()]

    pacts = sorted(
        {a for c in world.countries.values() for a in c.alliances if a.startswith(_PACT_PREFIX)}
    )
    return DashboardData(
        countries=sorted(world.countries.values(), key=lambda c: c.id),
        summaries=summaries,
        tensions=world.tensions,
        alliances={cid: c.alliances for cid, c in sorted(world.countries.items())},
        pacts=pacts,
        messages=world.diplomatic_history,
    )
