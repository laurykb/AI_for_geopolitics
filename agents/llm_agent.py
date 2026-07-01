"""Pays-agent piloté par un LLM (Phase 1) : décision en JSON validé + fallback.

Même interface `Agent` que `RuleBasedAgent` : un `LLMAgent` se branche tel quel
dans `RoundEngine`. Robustesse : on n'accorde aucune confiance aveugle au modèle
(parse tolérant, bornes clampées, identité injectée, repli déterministe).
"""

from __future__ import annotations

import json
from collections.abc import Iterator

from agents.base_agent import Agent
from agents.prompts import (
    DELIBERATION_SYSTEM,
    SYSTEM_PROMPT,
    LLMDecision,
    build_decision_prompt,
    build_deliberation_prompt,
)
from agents.rule_based_agent import RuleBasedAgent
from core.decisions import AgentDecision
from core.events import GeoEvent
from core.world_state import WorldState
from inference.backend import InferenceBackend, InferenceResult
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
        # Télémétrie du dernier appel (lecture par le bench / l'UI).
        self.last_result: InferenceResult | None = None
        self.last_used_fallback: bool = False
        # Décision issue de la dernière délibération streamée (round observable).
        self.last_decision: AgentDecision | None = None

    def decide(self, event: GeoEvent, world: WorldState) -> AgentDecision:
        country = world.countries[self.country_id]
        prompt = build_decision_prompt(country, event, world)
        self.last_used_fallback = True  # par défaut, sauf succès LLM ci-dessous
        try:
            result = self.backend.generate(
                prompt,
                system=SYSTEM_PROMPT,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                schema=self._schema,
            )
        except Exception:
            self.last_result = None
            return self._fallback(event, world)

        self.last_result = result
        data = _extract_json(result.text)
        if data is not None:
            decision = self._coerce(data, event, world)
            if decision is not None:
                self.last_used_fallback = False
                return decision
        return self._fallback(event, world)

    def _fallback(self, event: GeoEvent, world: WorldState) -> AgentDecision:
        decision = self.fallback.decide(event, world)
        decision.reasoning = f"[fallback LLM] {decision.reasoning}".strip()
        return decision

    def stream_deliberation(self, event: GeoEvent, world: WorldState) -> Iterator[str]:
        """Streame le raisonnement de l'agent (round observable), token par token.

        Le modèle « réfléchit à voix haute » puis termine par une ligne
        `DECISION: <action> <cible|none> <intensité>`. Après épuisement du flux, la
        décision est parsée dans `self.last_decision` (repli déterministe si absente).
        """
        country = world.countries[self.country_id]
        prompt = build_deliberation_prompt(country, event, world)
        chunks: list[str] = []
        try:
            for piece in self.backend.stream_generate(
                prompt,
                system=DELIBERATION_SYSTEM,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
            ):
                chunks.append(piece)
                yield piece
        except Exception:
            self.last_decision = self._fallback(event, world)
            return

        decision = self._parse_decision("".join(chunks), event, world)
        self.last_decision = decision if decision is not None else self._fallback(event, world)

    def _parse_decision(
        self, text: str, event: GeoEvent, world: WorldState
    ) -> AgentDecision | None:
        """Extrait la ligne `DECISION: <action> [cible] [intensité]` du texte streamé."""
        marker = text.lower().rfind("decision:")
        if marker == -1:
            return None
        tail = text[marker + len("decision:") :].strip().splitlines()[0]
        tokens = tail.replace(",", " ").split()
        if not tokens:
            return None
        try:
            action = ActionType(tokens[0].strip().lower())
        except ValueError:
            return None

        target: str | None = None
        intensity = 0.5
        for token in tokens[1:]:
            item = token.strip().lower()
            try:
                intensity = _clamp(float(item))
                continue
            except ValueError:
                pass
            if item in world.countries and item != self.country_id:
                target = item

        reasoning = text[:marker].strip()
        return AgentDecision(
            country=self.country_id,
            round_id=event.round_id,
            action=action,
            target=target,
            intensity=intensity,
            public_statement=reasoning[:300],
            reasoning=reasoning[:500],
        )

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
