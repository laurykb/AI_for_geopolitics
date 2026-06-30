"""Pays-agent piloté par un LLM (Phase 1) : décision en JSON validé + fallback.

Même interface `Agent` que `RuleBasedAgent` : un `LLMAgent` se branche tel quel
dans `RoundEngine`. Robustesse : on n'accorde aucune confiance aveugle au modèle
(parse tolérant, bornes clampées, identité injectée, repli déterministe).
"""

from __future__ import annotations

import json

from agents.base_agent import Agent
from agents.prompts import SYSTEM_PROMPT, LLMDecision, build_decision_prompt
from agents.rule_based_agent import RuleBasedAgent
from core.decisions import AgentDecision
from core.events import GeoEvent
from core.world_state import WorldState
from inference.backend import InferenceBackend
from simulation.action_space import ActionType


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


def _extract_json(text: str) -> dict | None:
    """Extrait un objet JSON d'une sortie LLM (gère fences et prose autour)."""
    text = text.strip()
    if not text:
        return None
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else None
    except (json.JSONDecodeError, ValueError):
        pass
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            obj = json.loads(text[start : end + 1])
            return obj if isinstance(obj, dict) else None
        except (json.JSONDecodeError, ValueError):
            return None
    return None


class LLMAgent(Agent):
    """Décide via un `InferenceBackend`, avec repli déterministe en cas d'échec."""

    def __init__(
        self,
        country_id: str,
        backend: InferenceBackend,
        *,
        fallback: Agent | None = None,
        max_tokens: int = 400,
        temperature: float = 0.7,
    ) -> None:
        super().__init__(country_id)
        self.backend = backend
        self.fallback = fallback or RuleBasedAgent(country_id)
        self.max_tokens = max_tokens
        self.temperature = temperature
        self._schema = LLMDecision.model_json_schema()

    def decide(self, event: GeoEvent, world: WorldState) -> AgentDecision:
        country = world.countries[self.country_id]
        prompt = build_decision_prompt(country, event, world)
        try:
            result = self.backend.generate(
                prompt,
                system=SYSTEM_PROMPT,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                schema=self._schema,
            )
        except Exception:
            return self._fallback(event, world)

        data = _extract_json(result.text)
        if data is not None:
            decision = self._coerce(data, event, world)
            if decision is not None:
                return decision
        return self._fallback(event, world)

    def _fallback(self, event: GeoEvent, world: WorldState) -> AgentDecision:
        decision = self.fallback.decide(event, world)
        decision.reasoning = f"[fallback LLM] {decision.reasoning}".strip()
        return decision

    def _coerce(self, data: dict, event: GeoEvent, world: WorldState) -> AgentDecision | None:
        """Transforme un dict LLM en `AgentDecision` borné, ou None si invalide."""
        try:
            action = ActionType(str(data.get("action", "")).strip().lower())
        except ValueError:
            return None

        target = data.get("target")
        if (
            not isinstance(target, str)
            or target not in world.countries
            or target == self.country_id
        ):
            target = None

        try:
            intensity = _clamp(float(data.get("intensity", 0.5)))
            risk = _clamp(float(data.get("risk_assessment", 0.5)))
        except (TypeError, ValueError):
            return None

        return AgentDecision(
            country=self.country_id,
            round_id=event.round_id,
            action=action,
            target=target,
            intensity=intensity,
            public_statement=str(data.get("public_statement", ""))[:300],
            risk_assessment=risk,
            reasoning=str(data.get("reasoning", ""))[:500],
        )
