"""Sérialisation des `RoundStep` du moteur en trames SSE.

Traduit chaque étape de round (dataclass `*Step`) en événement nommé + charge JSON
(`step_event`) et formate une trame `event:`/`data:` (`sse_frame`). Rendu récursivement
sérialisable par `_jsonable`. Extrait de `app/game_api.py` (dette D1) ; `step_event` et
`sse_frame` y restent ré-exportés pour la rétro-compat des imports (tests, orchestration).
"""

from __future__ import annotations

import dataclasses
import json
import re

from pydantic import BaseModel

from simulation.live_round import RoundStep

_SNAKE = re.compile(r"(?<!^)(?=[A-Z])")


def _jsonable(value: object) -> object:
    """Rend récursivement sérialisable en JSON (Pydantic, dataclasses, conteneurs)."""
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {f.name: _jsonable(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


def step_event(step: RoundStep) -> tuple[str, dict]:
    """`TurnStartStep` → ("turn_start", {champs…}) : nom SSE + charge utile JSON."""
    name = _SNAKE.sub("_", type(step).__name__.removesuffix("Step")).lower()
    payload = _jsonable(step)
    assert isinstance(payload, dict)
    return name, payload


def sse_frame(event: str, payload: dict) -> str:
    """Trame SSE `event:`/`data:` (une ligne JSON, UTF-8 non échappé)."""
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
