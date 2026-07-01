"""Modèle de vue du dashboard : joue le scénario mer Rouge (rule-based) et collecte le run.

Lecture seule, déterministe, sans GPU : le dashboard ne fait que *consommer* le moteur
de simulation existant (`RoundEngine`).
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

from agents.rule_based_agent import RuleBasedAgent
from core.country_state import CountryState
from core.decisions import DiplomaticMessage
from core.events import GeoEvent
from core.rounds import RoundEngine, RoundSummary
from core.world_state import WorldState

COUNTRIES_DIR = Path("data/countries")
SCENARIO_FILE = Path("data/scenarios/red_sea.json")

_PACT_PREFIX = "pact:"


class DashboardData(BaseModel):
    """Données nécessaires au rendu d'un run complet."""

    countries: list[CountryState]
    summaries: list[RoundSummary]
    tensions: dict[str, dict[str, float]] = Field(default_factory=dict)
    alliances: dict[str, list[str]] = Field(default_factory=dict)
    pacts: list[str] = Field(default_factory=list)
    messages: list[DiplomaticMessage] = Field(default_factory=list)

    @property
    def country_ids(self) -> list[str]:
        return [c.id for c in self.countries]


def _load_world() -> WorldState:
    paths = sorted(COUNTRIES_DIR.glob("*.json"))
    return WorldState.from_countries([CountryState.from_json_file(p) for p in paths])


def _load_events() -> list[GeoEvent]:
    data = json.loads(SCENARIO_FILE.read_text(encoding="utf-8"))
    return [GeoEvent(**event) for event in data["events"]]


def run_red_sea() -> DashboardData:
    """Joue le scénario mer Rouge en rule-based et renvoie l'état du run."""
    world = _load_world()
    agents = {cid: RuleBasedAgent(cid) for cid in world.countries}
    engine = RoundEngine(world, agents)
    summaries = [engine.play_round(event) for event in _load_events()]

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
