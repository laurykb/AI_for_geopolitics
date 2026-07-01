"""Fog Engine : chaque pays reçoit une perception potentiellement divergente (voire fausse).

Extension du fog déterministe (`perception.perceive`) : un **scénario de brouillard** fournit une
perception par pays (acteur suspecté, confiance, délai, narration) qui **prime** sur le calcul
déterministe et peut diverger de la vérité — désinformation / fake news. Les pays sans perception
fournie retombent sur `perceive` ; ceux listés `uninformed` n'ont « aucune information ». Tout est
déterministe (0 appel LLM en plus).
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

from core.country_state import CountryState
from core.events import GeoEvent
from simulation.perception import PerceivedEvent, perceive

FOG_DIR = Path("data/fog")
_UNINFORMED_CONFIDENCE = 0.05
_SURE_THRESHOLD = 0.6


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


class FogScenario(BaseModel):
    """Vérité d'un événement + ce que chaque pays en perçoit (croyances, parfois fausses)."""

    id: str
    title: str = ""
    description: str = ""
    true_event: GeoEvent
    perceptions: dict[str, dict] = Field(default_factory=dict)  # cid -> spec de croyance
    uninformed: list[str] = Field(default_factory=list)  # pays « pas au courant »


def perceived_from_spec(spec: dict) -> PerceivedEvent:
    """Construit une perception *authored* bornée depuis une spec brute (tolérante)."""
    try:
        confidence = _clamp(float(spec.get("confidence", 0.5)))
    except (TypeError, ValueError):
        confidence = 0.5
    suspected = str(spec.get("suspected_actor", "")).strip()
    narrative = str(spec.get("narrative", "")).strip()
    raw_delay = spec.get("delay_hours")
    try:
        delay = float(raw_delay) if raw_delay is not None else None
    except (TypeError, ValueError):
        delay = None
    sure = confidence >= _SURE_THRESHOLD and bool(suspected) and suspected.lower() != "unknown"
    default_note = f"acteur suspecté : {suspected}" if suspected else "origine floue"
    note = str(spec.get("note") or default_note)
    return PerceivedEvent(
        confidence=round(confidence, 2),
        attribution="sûre" if sure else "incertaine",
        note=note,
        suspected_actor=suspected,
        narrative=narrative,
        delay_hours=delay,
        authored=True,
    )


def _uninformed_perception() -> PerceivedEvent:
    return PerceivedEvent(
        confidence=_UNINFORMED_CONFIDENCE,
        attribution="incertaine",
        note="aucune information — le pays n'a pas encore connaissance de l'événement",
        authored=True,
    )


def resolve_perception(
    event: GeoEvent, country: CountryState, fog: FogScenario | None = None
) -> PerceivedEvent:
    """Perception de `country` : fournie (Fog) > `uninformed` > fog déterministe (`perceive`)."""
    if fog is not None:
        if country.id in fog.uninformed:
            return _uninformed_perception()
        spec = fog.perceptions.get(country.id)
        if spec is not None:
            return perceived_from_spec(spec)
    return perceive(event, country)


def load_fog_scenarios(directory: str | Path = FOG_DIR) -> list[FogScenario]:
    """Charge les scénarios de brouillard depuis `data/fog/*.json`."""
    paths = sorted(Path(directory).glob("*.json"))
    return [FogScenario.model_validate(json.loads(p.read_text(encoding="utf-8"))) for p in paths]
