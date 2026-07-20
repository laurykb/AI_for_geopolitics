"""Juge LLM : arbitre la négociation et fixe les variations d'attributs.

Comme un G7/G20, l'issue n'est pas déterministe : le juge lit toute la négociation,
raisonne à voix haute (streamé, visible), puis rend un `Verdict` chiffré. Le garde-fou
`apply_verdict` (dans `simulation.negotiation`) borne ensuite ce verdict.
"""

from __future__ import annotations

from collections.abc import Iterator

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
from inference.json_extract import extract_json
from simulation.negotiation import NegotiationMessage, Verdict, format_transcript
from simulation.private_deliberation import restream_without_think, strip_think

# POLISH-1 — budget de sortie DÉDIÉ au verdict structuré. Le JSON a grossi avec le lot
# G18-G23 (actions classées + intentions annoncées + promesses + demand_satisfied) : à
# 400 tokens, un round à 3+ pays se tronque sur mistral et `extract_json` échoue —
# TOUT le verdict retombe alors au neutre (escalade 0,5, deltas perdus). Constaté au
# smoke réel POLISH-1. Le budget de prose (rationale/communiqué) reste `max_tokens`.
# Remonté 900 -> 1300 : `attribute_reasons` ajoute une phrase de
# justification par delta non nul (même risque de troncature mistral 7B qu'au
# POLISH-1). À mesurer en live (troncature mistral 7B) — la mesure réelle est faite
# par le contrôleur en phase finale.
VERDICT_MAX_TOKENS = 1300


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
            # Collecte-puis-strip : chaque token part en JudgeTokenStep PUBLIC — la trace
            # <think> d'un juge de raisonnement (émise inline même sans l'option) ne doit
            # jamais l'atteindre.
            yield from restream_without_think(
                self.backend.stream_generate(
                    prompt,
                    system=JUDGE_SYSTEM,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                )
            )
        except Exception:
            yield "[arbitrage indisponible — backend hors service]"

    def verdict(
        self,
        event: GeoEvent,
        world: WorldState,
        transcript: list[NegotiationMessage],
        *,
        demand: str | None = None,
    ) -> Verdict:
        """Verdict chiffré (JSON libre, parse tolérant) ; verdict neutre si invalide.

        `demand` (G21) : exigence d'un ultimatum à échéance CE round — le juge constate
        en plus « demande satisfaite o/n » (`Verdict.demand_satisfied`)."""
        prompt = build_judge_verdict_prompt(event, world, format_transcript(transcript), demand)
        try:
            result = self.backend.generate(
                prompt,
                system=JUDGE_SYSTEM,
                # Le verdict structuré a son propre budget (voir VERDICT_MAX_TOKENS) :
                # un JSON tronqué coûte TOUT le round, pas seulement un champ.
                max_tokens=max(self.max_tokens, VERDICT_MAX_TOKENS),
                temperature=self.temperature,
            )
            # verdict() est la SEULE sortie du juge non protégée par
            # restream_without_think (rationale/communiqué le sont déjà) : un deepseek-r1
            # casté juge au lobby émet <think> inline même sans l'option think. Sans ce
            # strip, un faux JSON dans la pensée casse `extract_json` (ou pire, se fait
            # parser à la place du vrai verdict).
            data = extract_json(strip_think(result.text))
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
            # Même garde que stream_rationale : le communiqué finit en CommuniqueStep public.
            yield from restream_without_think(
                self.backend.stream_generate(
                    prompt,
                    system=COMMUNIQUE_SYSTEM,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                )
            )
        except Exception:
            yield "[communiqué indisponible — backend hors service]"
