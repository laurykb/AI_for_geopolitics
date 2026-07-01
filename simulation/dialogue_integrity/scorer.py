"""Score d'intégrité du dialogue — agrégat **signaling + listening** (§2.3).

Par message : `signaling` (1 − dégénérescence) et `listening` (responsivité au message cité +
pertinence au contexte). Par round : ajoute la **différenciation inter-agents** (1 − self-BLEU) et
la **part de non-responsifs** (round flaggé si `> 1/3`, §10.A). Poids et seuils **configurables et
visibles** → panneau « santé du dialogue ». Pur, déterministe (le NLI reste un enhancer optionnel).
Cf. `docs/spec_dialogue_integrity.md`.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from simulation.dialogue_integrity.message import SpeechAct
from simulation.dialogue_integrity.metrics import degeneration, relevance, self_bleu
from simulation.dialogue_integrity.nli import (
    NLIScorer,
    Responsiveness,
    assess_responsiveness,
    round_responsiveness,
)


class IntegrityWeights(BaseModel):
    """Poids du composite (visibles/ajustables). Somme des paires normalisée par construction."""

    signaling: float = 0.4
    listening: float = 0.6
    responsiveness_in_listening: float = 0.6  # le reste va à la pertinence
    round_differentiation: float = 0.4
    round_messages: float = 0.6
    flag_penalty: float = 0.8  # multiplicateur du score de round si trop de non-responsifs


DEFAULT_WEIGHTS = IntegrityWeights()


class MessageIntegrity(BaseModel):
    """Intégrité d'un message : signaling + listening -> score composite."""

    signaling: float = Field(0.0, ge=0.0, le=1.0)  # 1 − dégénérescence
    listening: float = Field(0.0, ge=0.0, le=1.0)  # responsivité + pertinence
    responsiveness: float | None = None  # None = message d'ouverture (rien à citer)
    relevance: float = 0.0
    degeneration: float = 0.0
    mismatch: bool = False  # performative ↔ contenu incohérents (tromperie)
    score: float = Field(0.0, ge=0.0, le=1.0)


def score_message(
    message: SpeechAct,
    *,
    cited: SpeechAct | None = None,
    context: str = "",
    nli: NLIScorer | None = None,
    weights: IntegrityWeights = DEFAULT_WEIGHTS,
    responsiveness: Responsiveness | None = None,
) -> MessageIntegrity:
    """Intègre un message. `cited` = le message référencé (`in_reply_to`) ; `context` = événement /
    monde. `responsiveness` peut être fourni (évite un double appel NLI côté round)."""
    deg = degeneration(message.content).score
    signaling = 1.0 - deg
    rel = relevance(message.content, context) if context else 0.0

    resp_val: float | None = None
    mismatch = False
    if responsiveness is None and cited is not None and message.is_reply:
        responsiveness = assess_responsiveness(message, cited, nli=nli)
    if responsiveness is not None:
        resp_val, mismatch = responsiveness.score, responsiveness.mismatch

    if resp_val is not None:
        w = weights.responsiveness_in_listening
        listening = w * resp_val + (1.0 - w) * rel
    else:
        listening = rel

    score = weights.signaling * signaling + weights.listening * listening
    return MessageIntegrity(
        signaling=round(signaling, 4), listening=round(listening, 4),
        responsiveness=(round(resp_val, 4) if resp_val is not None else None),
        relevance=round(rel, 4), degeneration=round(deg, 4), mismatch=mismatch,
        score=round(max(0.0, min(1.0, score)), 4),
    )


class RoundIntegrity(BaseModel):
    """Intégrité du dialogue sur un round (observabilité : panneau « santé du dialogue »)."""

    self_bleu: float = 0.0  # ↑ = messages trop semblables (signaling faible)
    differentiation: float = 0.0  # 1 − self_bleu
    mean_message: float = 0.0
    non_responsive_fraction: float = 0.0
    mismatches: int = 0
    flagged: bool = False
    score: float = Field(0.0, ge=0.0, le=1.0)


def score_round(
    messages: list[SpeechAct],
    *,
    context: str = "",
    nli: NLIScorer | None = None,
    weights: IntegrityWeights = DEFAULT_WEIGHTS,
) -> RoundIntegrity:
    """Intégrité d'un round : différenciation inter-agents + moyenne des messages, pénalisée si
    trop de non-responsifs. Le lien `in_reply_to` est résolu dans la liste des `messages`."""
    by_id = {m.id: m for m in messages}
    per: list[MessageIntegrity] = []
    assessments: list[Responsiveness] = []
    for m in messages:
        cited = by_id.get(m.in_reply_to) if m.is_reply else None
        resp = assess_responsiveness(m, cited, nli=nli) if cited is not None else None
        if resp is not None:
            assessments.append(resp)
        per.append(
            score_message(m, cited=cited, context=context, nli=nli, weights=weights,
                          responsiveness=resp)
        )

    sb = self_bleu([m.content for m in messages])
    differentiation = 1.0 - sb
    mean_msg = sum(p.score for p in per) / len(per) if per else 0.0
    rr = round_responsiveness(assessments)
    score = weights.round_differentiation * differentiation + weights.round_messages * mean_msg
    if rr.flagged:
        score *= weights.flag_penalty
    return RoundIntegrity(
        self_bleu=round(sb, 4), differentiation=round(differentiation, 4),
        mean_message=round(mean_msg, 4),
        non_responsive_fraction=round(rr.non_responsive_fraction, 4),
        mismatches=rr.mismatches, flagged=rr.flagged,
        score=round(max(0.0, min(1.0, score)), 4),
    )
