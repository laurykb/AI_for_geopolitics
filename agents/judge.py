"""Juge LLM : arbitre la négociation et fixe les variations d'attributs.

Comme un G7/G20, l'issue n'est pas déterministe : le juge lit toute la négociation,
raisonne à voix haute (streamé, visible), puis rend un `Verdict` chiffré. Le garde-fou
`apply_verdict` (dans `simulation.negotiation`) borne ensuite ce verdict.
"""

from __future__ import annotations

from collections.abc import Iterator

from agents.llm_agent import _extract_json
from agents.prompts import (
    COMMUNIQUE_SYSTEM,
    JUDGE_SYSTEM,
    build_communique_prompt,
    build_judge_rationale_prompt,
    build_judge_verdict_prompt,
)
from core.events import GeoEvent
from core.world_state import WorldState
from inference.backend import InferenceBackend
from simulation.negotiation import NegotiationMessage, Verdict, format_transcript


class JudgeAgent:
    """Arbitre LLM : raisonnement streamé + verdict structuré (avec repli neutre)."""

    def __init__(
        self, backend: InferenceBackend, *, max_tokens: int = 400, temperature: float = 0.4
    ) -> None:
        self.backend = backend
        self.max_tokens = max_tokens
        self.temperature = temperature

    @property
    def model_tag(self) -> str:
        return getattr(self.backend, "model", type(self.backend).__name__)

    def stream_rationale(
        self, event: GeoEvent, world: WorldState, transcript: list[NegotiationMessage]
    ) -> Iterator[str]:
        """Streame le raisonnement d'arbitrage (qui a gagné, alliances, tensions)."""
        prompt = build_judge_rationale_prompt(event, world, format_transcript(transcript))
        try:
            yield from self.backend.stream_generate(
                prompt,
                system=JUDGE_SYSTEM,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
            )
        except Exception:
            yield "[arbitrage indisponible — backend hors service]"

    def verdict(
        self, event: GeoEvent, world: WorldState, transcript: list[NegotiationMessage]
    ) -> Verdict:
        """Verdict chiffré (JSON libre, parse tolérant) ; verdict neutre si invalide."""
        prompt = build_judge_verdict_prompt(event, world, format_transcript(transcript))
        try:
            result = self.backend.generate(
                prompt,
                system=JUDGE_SYSTEM,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
            )
            data = _extract_json(result.text)
        except Exception:
            data = None
        if not isinstance(data, dict):
            return Verdict()
        try:
            return Verdict.model_validate(data)
        except Exception:
            return Verdict()

    def stream_communique(
        self, event: GeoEvent, world: WorldState, transcript: list[NegotiationMessage]
    ) -> Iterator[str]:
        """Streame le communiqué commun (type G7) issu de la négociation."""
        prompt = build_communique_prompt(event, world, format_transcript(transcript))
        try:
            yield from self.backend.stream_generate(
                prompt,
                system=COMMUNIQUE_SYSTEM,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
            )
        except Exception:
            yield "[communiqué indisponible — backend hors service]"
