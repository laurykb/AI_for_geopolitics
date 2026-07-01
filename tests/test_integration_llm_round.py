"""Intégration : un round complet avec des LLMAgent (backend mock) via RoundEngine.

Prouve que LLMAgent est un drop-in du moteur de rounds, sans GPU ni Ollama.
"""

import json
from pathlib import Path

from agents.llm_agent import LLMAgent
from core.country_state import CountryState
from core.events import GeoEvent
from core.rounds import RoundEngine
from core.world_state import WorldState
from inference.mock_backend import MockBackend


def _load_world() -> WorldState:
    paths = sorted(Path("data/countries").glob("*.json"))
    return WorldState.from_countries([CountryState.from_json_file(p) for p in paths])


def _load_events() -> list[GeoEvent]:
    data = json.loads(Path("data/scenarios/red_sea.json").read_text(encoding="utf-8"))
    return [GeoEvent(**event) for event in data["events"]]


def test_red_sea_runs_end_to_end_with_llm_agents():
    world = _load_world()
    # chaque pays renvoie un JSON valide et neutre via le mock
    canned = json.dumps(
        {
            "action": "call_for_mediation",
            "target": None,
            "intensity": 0.4,
            "reasoning": "désescalade",
        }
    )
    agents = {cid: LLMAgent(cid, MockBackend(canned)) for cid in world.countries}
    engine = RoundEngine(world, agents)
    events = _load_events()

    summaries = [engine.play_round(event) for event in events]

    assert len(summaries) == len(events)
    assert world.current_round == events[-1].round_id
    for summary in summaries:
        assert summary.decisions
        assert 0.0 <= summary.risk.escalation <= 1.0
        assert summary.risk.explanation
        for decision in summary.decisions:
            assert decision.round_id == summary.round_id
            assert decision.country in world.countries
