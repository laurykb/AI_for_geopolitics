"""Tests du GameMasterAgent : génération d'événement valide + fallback."""

import json

from agents.game_master import GameMasterAgent
from core.country_state import CountryState, Economy, Military, Resources
from core.world_state import WorldState
from inference.mock_backend import MockBackend


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


def test_generates_valid_event_from_json():
    payload = json.dumps(
        {
            "event_type": "maritime",
            "title": "Blocus du détroit",
            "description": "Tensions",
            "actors": ["usa", "iran", "atlantis"],
            "severity": 1.5,
            "uncertainty": 0.4,
        }
    )
    gm = GameMasterAgent(MockBackend(payload))
    event = gm.generate_event(_world(), round_id=1, date="2025-07-01")

    assert event.title == "Blocus du détroit"
    assert event.round_id == 1
    assert event.date == "2025-07-01"
    assert event.actors == ["usa", "iran"]  # 'atlantis' inconnu filtré
    assert event.severity == 1.0  # clampé


def test_invalid_output_falls_back():
    gm = GameMasterAgent(MockBackend("pas du json"))
    event = gm.generate_event(_world(), round_id=3, date="2026-01-01")
    assert event.round_id == 3
    assert event.title  # événement de repli valide
    assert set(event.actors) <= set(_world().countries)
