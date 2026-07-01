"""Game Master piloté par un LLM : génère le prochain événement géopolitique.

Réutilise le pattern de robustesse du `LLMAgent` (parse tolérant + fallback) : le GM
propose un `GeoEvent` en JSON validé ; en cas d'échec, un événement de repli est émis.
"""

from __future__ import annotations

import random

from pydantic import BaseModel, Field

from agents.llm_agent import _extract_json
from core.events import GeoEvent
from core.world_state import WorldState
from inference.backend import InferenceBackend

GM_SYSTEM = (
    "Tu es le Game Master d'une simulation géopolitique. À partir de l'état du monde et de la "
    "date, invente UN événement plausible et concret (crise, incident, initiative diplomatique). "
    "Réponds UNIQUEMENT par un objet JSON, sans texte autour."
)


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


class GMEvent(BaseModel):
    """Schéma de sortie attendu du Game Master (contraint la génération)."""

    event_type: str = "incident"
    title: str
    description: str = ""
    actors: list[str] = Field(default_factory=list)
    severity: float = Field(0.5, ge=0.0, le=1.0)
    uncertainty: float = Field(0.5, ge=0.0, le=1.0)


class GameMasterAgent:
    """Génère l'événement d'un round à partir de l'état du monde."""

    def __init__(
        self, backend: InferenceBackend, *, max_tokens: int = 300, temperature: float = 0.9
    ) -> None:
        self.backend = backend
        self.max_tokens = max_tokens
        self.temperature = temperature
        self._schema = GMEvent.model_json_schema()

    def generate_event(
        self, world: WorldState, round_id: int, *, date: str = "", recent: list[str] | None = None
    ) -> GeoEvent:
        prompt = self._prompt(world, date, recent or [])
        try:
            result = self.backend.generate(
                prompt,
                system=GM_SYSTEM,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                schema=self._schema,
            )
            data = _extract_json(result.text)
        except Exception:
            data = None
        return self._coerce(data, world, round_id, date) or self._fallback(world, round_id, date)

    def _prompt(self, world: WorldState, date: str, recent: list[str]) -> str:
        ids = ", ".join(sorted(world.countries))
        history = "; ".join(recent[-3:]) if recent else "aucun"
        return (
            f"DATE : {date or 'n/a'}\n"
            f"PAYS (ids) : {ids}\n"
            f"Événements récents : {history}\n\n"
            f"Invente le prochain événement. JSON : {{event_type, title, description, "
            f"actors (ids existants), severity (0-1), uncertainty (0-1)}}."
        )

    def _coerce(
        self, data: dict | None, world: WorldState, round_id: int, date: str
    ) -> GeoEvent | None:
        if not isinstance(data, dict):
            return None
        title = str(data.get("title", "")).strip()
        if not title:
            return None
        actors = [a for a in data.get("actors", []) if isinstance(a, str) and a in world.countries]
        try:
            severity = _clamp(float(data.get("severity", 0.5)))
            uncertainty = _clamp(float(data.get("uncertainty", 0.5)))
        except (TypeError, ValueError):
            severity, uncertainty = 0.5, 0.5
        return GeoEvent(
            id=f"gm-{round_id}",
            round_id=round_id,
            date=date,
            event_type=str(data.get("event_type", "incident"))[:40],
            title=title[:120],
            description=str(data.get("description", ""))[:500],
            actors=actors or sorted(world.countries)[:1],
            severity=severity,
            uncertainty=uncertainty,
        )

    def _fallback(self, world: WorldState, round_id: int, date: str) -> GeoEvent:
        actors = random.sample(sorted(world.countries), k=min(2, len(world.countries)))
        return GeoEvent(
            id=f"gm-{round_id}",
            round_id=round_id,
            date=date,
            event_type="incident",
            title="Regain de tensions régionales",
            description="Le Game Master signale une montée des tensions (événement de repli).",
            actors=actors,
            severity=0.5,
            uncertainty=0.6,
        )
