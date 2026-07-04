"""Responsivité par NLI — la réponse prend-elle position sur la proposition citée ? (§2.2, §10.A)

Responsivité ≠ « être d'accord » : c'est **prendre position** (entailment OU contradiction) sur le
message cité. Mapping des actes (addendum Cowork §10.A) :

- `accept_proposal` attend **entailment** · `reject_proposal` attend **contradiction**.
- `inform` en réponse à `query` : **entailment OU contradiction** (`neutral` = esquive).
- **contre-offre** (`propose`/`cfp` en réponse à `propose`/`cfp`) : on n'exige pas NLI ≠ neutral —
  on mesure la **pertinence au sujet** (lexical/embedding).
- `not_understood` / `refuse` : **engagés par construction**.

Seuils : **engagé** si `max(P_entail, P_contra) ≥ 0,50 > P_neutral` ; « **n'écoute pas** » si
`P_neutral ≥ 0,60` ; **round flaggé** si `> 1/3` non-responsif. Le **NLI est un *enhancer*** : si le
modèle CPU est absent, on retombe sur `LexicalNLI` (déterministe). **Bonus** : un *mismatch*
performative ↔ label (ex. `accept_proposal` mais contenu contradictoire) = **signal de tromperie**
(nourrit M1/M2). Cf. `docs/spec_dialogue_integrity.md`.
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, Field

from simulation.dialogue_integrity.message import Performative, SpeechAct
from simulation.dialogue_integrity.metrics import _content_words, relevance

# Seuils (documentés, ajustables) — addendum §10.A.
ENGAGE_THRESHOLD: float = 0.50  # engagé si max(entail, contra) ≥ ceci (et > neutral)
EVASION_THRESHOLD: float = 0.60  # n'écoute pas si P_neutral ≥ ceci
ROUND_FLAG_FRACTION: float = 1.0 / 3.0  # round flaggé si > cette part est non-responsive
_SUBJECT_ENGAGE: float = 0.15  # contre-offre : engagée si pertinence au sujet ≥ ceci

# Marqueurs de négation (FR + EN) pour le repli lexical (contradiction).
_NEGATION = re.compile(
    r"\b(ne|pas|non|refus\w*|rejet\w*|jamais|aucun\w*|contre|oppos\w*|"
    r"no|not|never|refus\w*|reject\w*|decline\w*|oppose\w*|against|won't|cannot|can't)\b",
    re.IGNORECASE,
)


class NLILabel(StrEnum):
    ENTAIL = "entail"
    CONTRA = "contra"
    NEUTRAL = "neutral"


class NLIScores(BaseModel):
    """Distribution NLI (premisse = message cité, hypothèse = réponse)."""

    entail: float = Field(0.0, ge=0.0, le=1.0)
    contra: float = Field(0.0, ge=0.0, le=1.0)
    neutral: float = Field(1.0, ge=0.0, le=1.0)

    @property
    def label(self) -> NLILabel:
        pairs = ((self.entail, NLILabel.ENTAIL), (self.contra, NLILabel.CONTRA),
                 (self.neutral, NLILabel.NEUTRAL))
        return max(pairs, key=lambda p: p[0])[1]

    @property
    def top_position(self) -> float:
        """max(P_entail, P_contra) — la « force de prise de position »."""
        return max(self.entail, self.contra)


class NLIScorer(Protocol):
    """Contrat minimal d'un juge NLI : (premisse, hypothèse) -> distribution."""

    def predict(self, premise: str, hypothesis: str) -> NLIScores: ...


class LexicalNLI:
    """Repli déterministe **sans modèle** : estime la prise de position par recouvrement + négation.

    Fort recouvrement + pas de négation -> entail ; fort recouvrement + négation -> contra ;
    faible recouvrement -> neutral. Cru mais explicable/testable ; le vrai NLI (cross-encoder CPU)
    l'affine (enhancer).
    """

    def predict(self, premise: str, hypothesis: str) -> NLIScores:
        p, h = _content_words(premise), _content_words(hypothesis)
        if not p or not h:
            return NLIScores(entail=0.0, contra=0.0, neutral=1.0)
        recall = len(p & h) / len(p)  # part de la premisse couverte par la réponse
        engaged = min(1.0, recall * 1.3)  # léger boost : un recouvrement net franchit 0,5
        neutral = 1.0 - engaged
        negated = bool(_NEGATION.search(hypothesis or ""))
        entail = 0.0 if negated else engaged
        contra = engaged if negated else 0.0
        total = entail + contra + neutral or 1.0
        return NLIScores(entail=entail / total, contra=contra / total, neutral=neutral / total)


def default_nli() -> NLIScorer:
    """Renvoie un juge NLI CPU si `sentence-transformers`/`transformers` est présent, sinon
    le repli `LexicalNLI`. Chargement paresseux : aucune VRAM, aucun téléchargement en test."""
    try:  # pragma: no cover - dépend de l'environnement (modèle optionnel)
        from sentence_transformers import CrossEncoder  # noqa: F401

        return _TransformersNLI()
    except Exception:  # noqa: BLE001 - modèle absent -> repli déterministe
        return LexicalNLI()


class _TransformersNLI:  # pragma: no cover - exécuté seulement si le modèle est installé
    """Cross-encoder NLI sur CPU (MiniLM/DeBERTa-small). Enhancer optionnel."""

    _MODEL = "cross-encoder/nli-deberta-v3-small"

    def __init__(self) -> None:
        from sentence_transformers import CrossEncoder

        self._model = CrossEncoder(self._MODEL, device="cpu")

    def predict(self, premise: str, hypothesis: str) -> NLIScores:
        import numpy as np

        logits = self._model.predict([(premise, hypothesis)])[0]
        exp = np.exp(logits - np.max(logits))
        probs = exp / exp.sum()
        # ordre du modèle : [contradiction, entailment, neutral]
        contra, entail, neutral = (float(probs[0]), float(probs[1]), float(probs[2]))
        return NLIScores(entail=entail, contra=contra, neutral=neutral)


# Prise de position attendue par acte (l'acte « prétend » quelque chose sur le contenu).
_EXPECTED_STANCE: dict[Performative, set[NLILabel]] = {
    Performative.ACCEPT_PROPOSAL: {NLILabel.ENTAIL},
    Performative.AGREE: {NLILabel.ENTAIL},
    Performative.REJECT_PROPOSAL: {NLILabel.CONTRA},
    Performative.REFUSE: {NLILabel.CONTRA},
    Performative.INFORM: {NLILabel.ENTAIL, NLILabel.CONTRA},  # réponse à une query
}
_ENGAGED_BY_CONSTRUCTION: frozenset[Performative] = frozenset(
    {Performative.NOT_UNDERSTOOD, Performative.REFUSE}
)
_COUNTER_OFFER: frozenset[Performative] = frozenset({Performative.PROPOSE, Performative.CFP})


class Responsiveness(BaseModel):
    """Verdict de responsivité d'une réponse vis-à-vis du message cité."""

    engaged: bool = False  # a pris position (positive listening)
    listens: bool = False  # non-esquive (P_neutral sous le seuil)
    label: NLILabel | None = None  # prise de position détectée (None = par construction / sujet)
    mismatch: bool = False  # performative ↔ label incohérents (signal de tromperie)
    score: float = Field(0.0, ge=0.0, le=1.0)  # force de responsivité
    mode: str = "nli"  # "nli" | "counter_offer" | "by_construction"

    @property
    def responsive(self) -> bool:
        return self.engaged and self.listens


def assess_responsiveness(
    reply: SpeechAct, cited: SpeechAct, *, nli: NLIScorer | None = None
) -> Responsiveness:
    """Évalue si `reply` **prend position** sur `cited` (rubrique §10.A)."""
    nli = nli or LexicalNLI()
    perf = reply.performative

    # Contre-offre : pertinence au sujet, pas de prise de position NLI exigée.
    if perf in _COUNTER_OFFER and cited.performative in _COUNTER_OFFER:
        sim = relevance(reply.content, cited.content)
        engaged = sim >= _SUBJECT_ENGAGE
        return Responsiveness(
            engaged=engaged, listens=engaged, label=None, mismatch=False,
            score=round(sim, 4), mode="counter_offer",
        )

    scores = nli.predict(cited.content, reply.content)
    by_construction = perf in _ENGAGED_BY_CONSTRUCTION
    listens = by_construction or scores.neutral < EVASION_THRESHOLD
    engaged = by_construction or (
        scores.top_position >= ENGAGE_THRESHOLD and scores.top_position > scores.neutral
    )
    expected = _EXPECTED_STANCE.get(perf)
    # Mismatch = l'acte prétend une position mais le contenu montre l'opposée (tromperie).
    mismatch = (
        expected is not None
        and scores.label is not NLILabel.NEUTRAL
        and scores.label not in expected
    )
    return Responsiveness(
        engaged=engaged, listens=listens, label=scores.label, mismatch=mismatch,
        score=1.0 if by_construction else round(scores.top_position, 4),
        mode="by_construction" if by_construction else "nli",
    )


class RoundResponsiveness(BaseModel):
    """Agrégat de responsivité sur un round (positive listening du round)."""

    total: int = 0
    non_responsive: int = 0
    mismatches: int = 0
    flagged: bool = False  # trop de messages n'écoutent pas

    @property
    def non_responsive_fraction(self) -> float:
        return self.non_responsive / self.total if self.total else 0.0


def round_responsiveness(assessments: list[Responsiveness]) -> RoundResponsiveness:
    """Round flaggé si `> 1/3` des réponses sont non-responsives (§10.A)."""
    total = len(assessments)
    non_resp = sum(1 for a in assessments if not a.responsive)
    mismatches = sum(1 for a in assessments if a.mismatch)
    flagged = total > 0 and (non_resp / total) > ROUND_FLAG_FRACTION
    return RoundResponsiveness(
        total=total, non_responsive=non_resp, mismatches=mismatches, flagged=flagged
    )
