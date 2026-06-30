"""Test d'intégration : un scénario complet (mer Rouge) de bout en bout."""

import json
from pathlib import Path

from agents.rule_based_agent import RuleBasedAgent
from core.country_state import CountryState
from core.events import GeoEvent
from core.rounds import RoundEngine
from core.world_state import WorldState


def _load_world() -> WorldState:
    paths = sorted(Path("data/countries").glob("*.json"))
    return WorldState.from_countries([CountryState.from_json_file(p) for p in paths])


def _load_events() -> list[GeoEvent]:
    data = json.loads(Path("data/scenarios/red_sea.json").read_text(encoding="utf-8"))
    return [GeoEvent(**event) for event in data["events"]]


def test_red_sea_scenario_runs_end_to_end():
    world = _load_world()
    agents = {cid: RuleBasedAgent(cid) for cid in world.countries}
    engine = RoundEngine(world, agents)
    events = _load_events()
    assert len(events) >= 3

    summaries = [engine.play_round(event) for event in events]

    assert len(summaries) == len(events)
    assert world.current_round == events[-1].round_id
    # USA est rival de l'Iran, présent dans plusieurs événements -> la tension monte.
    assert world.get_tension("usa", "iran") > 0.0
    # Tous les scores de risque restent bornés et expliqués.
    for summary in summaries:
        assert 0.0 <= summary.risk.escalation <= 1.0
        assert summary.risk.explanation
        assert summary.decisions  # chaque pays a décidé
