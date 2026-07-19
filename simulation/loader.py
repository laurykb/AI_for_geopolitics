"""Chargement du monde et des scénarios depuis `data/` (factorisé, Phase 5)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from core.country_state import CountryState
from core.events import GeoEvent
from core.world_state import WorldState

COUNTRIES_DIR = Path("data/countries")
DEFAULT_SCENARIO = Path("data/scenarios/red_sea.json")


def load_world(
    countries_dir: str | Path = COUNTRIES_DIR,
    only: list[str] | None = None,
) -> WorldState:
    """Construit un `WorldState` depuis les profils `data/countries/*.json`.

    `only` restreint le monde à un sous-ensemble d'ids (le casting d'un scénario,
    la sélection du lobby) ; None charge tout le roster disponible.
    """
    paths = sorted(Path(countries_dir).glob("*.json"))
    countries = [CountryState.from_json_file(p) for p in paths]
    if only is not None:
        wanted = set(only)
        unknown = wanted - {c.id for c in countries}
        if unknown:
            raise ValueError(f"pays inconnus : {sorted(unknown)}")
        countries = [c for c in countries if c.id in wanted]
    return WorldState.from_countries(countries)


@lru_cache(maxsize=1)
def known_country_ids(countries_dir: str | Path = COUNTRIES_DIR) -> frozenset[str]:
    """Ids du registre STANDARD (data/countries) — sans parser chaque fichier : le nom
    du fichier vaut `CountryState.id` par convention (P4, vérifié en tests). Sert à
    repérer un pays INVENTÉ (country_forge) sans le persister nulle part : un id du
    monde d'une partie absent de ce registre EST le pays inventé (game_api._view)."""
    return frozenset(p.stem for p in Path(countries_dir).glob("*.json"))


def load_scenario_events(path: str | Path = DEFAULT_SCENARIO) -> list[GeoEvent]:
    """Charge la liste d'événements d'un scénario."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [GeoEvent(**event) for event in data["events"]]


def load_scenario_countries(path: str | Path = DEFAULT_SCENARIO) -> list[str] | None:
    """Casting déclaré par le scénario (None si le scénario n'en fixe pas)."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data.get("countries")
