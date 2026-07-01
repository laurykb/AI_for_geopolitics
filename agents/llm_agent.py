"""Pays-agent piloté par un LLM (Phase 1) : décision en JSON validé + fallback.

Même interface `Agent` que `RuleBasedAgent` : un `LLMAgent` se branche tel quel
dans `RoundEngine`. Robustesse : on n'accorde aucune confiance aveugle au modèle
(parse tolérant, bornes clampées, identité injectée, repli déterministe).
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator

from agents.base_agent import Agent
from agents.prompts import (
    DELIBERATION_SYSTEM,
    NEGOTIATION_SYSTEM,
    SYSTEM_PROMPT,
    LLMDecision,
    build_decision_prompt,
    build_deliberation_prompt,
    build_negotiation_prompt,
)
from agents.rule_based_agent import RuleBasedAgent
from core.decisions import AgentDecision
from core.events import GeoEvent
from core.world_state import WorldState
from inference.backend import InferenceBackend, InferenceResult
from simulation.action_space import ActionType
from simulation.negotiation import NegotiationMessage, format_transcript
from simulation.perception import PerceivedEvent, perceive


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


# Variantes fréquentes du LLM -> action canonique (parsing de la ligne DECISION).
_ACTION_SYNONYMS: dict[str, str] = {
    "neutral": "remain_neutral",
    "condamn": "condemn",
    "condemns": "condemn",
    "sanctions": "sanction",
    "mediation": "call_for_mediation",
    "mediate": "call_for_mediation",
    "coalition": "form_coalition",
    "mobilise": "mobilize",
    "deploy": "deploy_forces",
}


def _match_action(normalized: str) -> ActionType | None:
    """Trouve l'action mentionnée le plus tôt (valeurs canoniques, puis synonymes)."""
    best: ActionType | None = None
    best_idx = len(normalized) + 1
    for action in ActionType:
        idx = normalized.find(action.value)
        if idx != -1 and idx < best_idx:
            best, best_idx = action, idx
    if best is not None:
        return best
    for key, value in _ACTION_SYNONYMS.items():
        if key in normalized:
            return ActionType(value)
    return None


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

    @property
    def model_tag(self) -> str:
        """Identifiant du modèle qui incarne ce pays (badge de traçabilité UI)."""
        return getattr(self.backend, "model", type(self.backend).__name__)

    def stream_negotiation_message(
        self,
        event: GeoEvent,
        world: WorldState,
        transcript: list[NegotiationMessage],
        perceived: PerceivedEvent | None = None,
    ) -> Iterator[str]:
        """Streame une prise de parole (sur la perception fournie, sinon fog déterministe).

        En mode Fog Engine, `perceived` peut diverger de la vérité (désinformation) : l'agent
        négocie alors sur sa croyance, pas sur l'événement réel.
        """
        country = world.countries[self.country_id]
        perceived = perceived or perceive(event, country)
        prompt = build_negotiation_prompt(
            country, event, world, format_transcript(transcript), perceived
        )
        try:
            # Budget plus large : la génération porte la pensée privée PUIS le message public.
            yield from self.backend.stream_generate(
                prompt, system=NEGOTIATION_SYSTEM, max_tokens=360, temperature=self.temperature
            )
        except Exception:
            yield f"[{self.country_id} garde le silence — backend indisponible]"

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
        """Extrait la ligne `DECISION: <action> [cible] [intensité]` (robuste aux variantes).

        La ligne DECISION peut être au début ou à la fin : on l'isole et on garde le reste
        comme raisonnement affiché. Action tolérante (multi-mots, casse, synonymes).
        """
        decision_line: str | None = None
        kept: list[str] = []
        for line in text.splitlines():
            if decision_line is None and "decision:" in line.lower():
                decision_line = line
            else:
                kept.append(line)
        if decision_line is None:
            return None

        tail = decision_line[decision_line.lower().index("decision:") + len("decision:") :]
        action = _match_action(re.sub(r"[\s\-]+", "_", tail.strip().lower()))
        if action is None:
            return None

        words = re.split(r"[\s,]+", tail.strip().lower())
        target = next((w for w in words if w in world.countries and w != self.country_id), None)
        intensity = 0.5
        for word in words:
            try:
                intensity = _clamp(float(word))
                break
            except ValueError:
                continue

        reasoning = "\n".join(kept).strip()
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
