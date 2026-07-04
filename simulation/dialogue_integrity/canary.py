"""Canary — le « test unitaire » du dialogue (§3, §10.C).

Injecte une **question directe** de A qui **exige** une réponse précise, et vérifie que B
l'**adresse vraiment** : `in_reply_to` correct **+** prise de position (engagé) **+** au sujet **+**
**influence causale** (`div ≥ 0,25` via le contrefactuel par leurre). Déterministe contre
`MockBackend` → **gate CI** ; en live (Ollama) c'est un canary optionnel hors CI (sinon *flaky*).
Cf. `docs/spec_dialogue_integrity.md`.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from simulation.dialogue_integrity.causal import (
    LISTEN_THRESHOLD,
    conditioning_test,
)
from simulation.dialogue_integrity.message import SpeechAct
from simulation.dialogue_integrity.metrics import relevance
from simulation.dialogue_integrity.nli import NLIScorer, assess_responsiveness

_ON_SUBJECT: float = 0.15  # pertinence minimale de la réponse au sujet de la question


class CanaryResult(BaseModel):
    """Verdict du canary : passe seulement si TOUS les critères sont réunis."""

    passed: bool = False
    correct_reply_to: bool = False  # la réponse référence bien la question
    engaged: bool = False  # prise de position (positive listening)
    on_subject: bool = False  # pertinence au sujet de la question
    listens: bool = False  # influence causale (div ≥ seuil)
    divergence: float = Field(0.0, ge=0.0, le=1.0)
    reasons: list[str] = Field(default_factory=list)  # pourquoi ça échoue (le cas échéant)


def run_canary(
    backend,
    query: SpeechAct,
    decoy: SpeechAct,
    build_prompt: Callable[[SpeechAct], str],
    *,
    responder: str,
    nli: NLIScorer | None = None,
) -> CanaryResult:
    """Joue le canary : conditionne la réponse de `responder` sur `query` (réel) vs `decoy`
    (leurre de même performative), puis vérifie les quatre critères."""
    causal = conditioning_test(backend, build_prompt, query, decoy, responder=responder)
    real = causal.real
    correct = bool(real and real.in_reply_to == query.id)
    resp = assess_responsiveness(real, query, nli=nli) if real else None
    engaged = bool(resp and resp.engaged)
    on_subject = bool(real and relevance(real.content, query.content) >= _ON_SUBJECT)
    listens = causal.listens

    reasons: list[str] = []
    if not correct:
        reasons.append("in_reply_to ne référence pas la question")
    if not engaged:
        reasons.append("pas de prise de position sur la question")
    if not on_subject:
        reasons.append("réponse hors sujet")
    if not listens:
        reasons.append(f"pas d'influence causale (div {causal.divergence} < {LISTEN_THRESHOLD})")

    return CanaryResult(
        passed=correct and engaged and on_subject and listens,
        correct_reply_to=correct, engaged=engaged, on_subject=on_subject, listens=listens,
        divergence=causal.divergence, reasons=reasons,
    )


if TYPE_CHECKING:  # aide au typage sans dépendance runtime
    from inference.backend import InferenceBackend  # noqa: F401
