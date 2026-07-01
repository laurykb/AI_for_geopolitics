"""Chargement du monde et des scénarios depuis `data/` (factorisé, Phase 5)."""

from __future__ import annotations

import json
from pathlib import Path

from core.country_state import CountryState
from core.events import GeoEvent
from core.world_state import WorldState

COUNTRIES_DIR = Path("data/countries")
DEFAULT_SCENARIO = Path("data/scenarios/red_sea.json")


def load_world(countries_dir: str | Path = COUNTRIES_DIR) -> WorldState:
    """Construit un `WorldState` depuis les profils `data/countries/*.json`."""
    paths = sorted(Path(countries_dir).glob("*.json"))
    return WorldState.from_countries([CountryState.from_json_file(p) for p in paths])


def load_scenario_events(path: str | Path = DEFAULT_SCENARIO) -> list[GeoEvent]:
    """Charge la liste d'événements d'un scénario."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [GeoEvent(**event) for event in data["events"]]
