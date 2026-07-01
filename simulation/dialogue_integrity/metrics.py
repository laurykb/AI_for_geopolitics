"""Métriques d'intégrité du dialogue — **pures, CPU, sans LLM** (§2 de la spéc).

Deux familles (Lowe et al., AAMAS 2019) :

- **Positive signaling** (le message porte-t-il de l'info ?) :
  - `self_bleu` : différenciation inter-agents (self-BLEU, Zhu et al. 2018). Élevé = messages
    quasi identiques = signaling faible.
  - `degeneration` : répétition n-gram, longueur, vide/boucle (Holtzman et al. 2020).
- **Positive listening** (le message est-il écouté ?) :
  - `responsiveness` : recouvrement de contenu entre une réponse et le message qu'elle cite.
  - `relevance` : recouvrement entre un message et le contexte (événement / monde).

Tout est **lexical et déterministe** (testable hors LLM). Les variantes par embeddings et **NLI**
(§2.2, §3) se brancheront en complément sans changer ces signatures. Seuils documentés,
ajustables. Cf. `docs/spec_dialogue_integrity.md`.
"""

from __future__ import annotations

import math
import re
from collections import Counter

from pydantic import BaseModel, Field

_WORD = re.compile(r"\w+", re.UNICODE)

# Mots-outils FR + EN ignorés pour le *contenu* (liste courte, documentée, ajustable).
_STOPWORDS: frozenset[str] = frozenset(
    """
    le la les un une des du de d au aux et ou mais donc or ni car que qui quoi dont ou
    je tu il elle on nous vous ils elles se sa son ses leur leurs ce cette ces mon ma mes ton
    ta tes notre nos votre vos ne pas plus est sont etre suis es sommes etes ont ai as avons
    avez avoir pour par sur avec sans dans en vers chez comme si tout tous toute toutes
    the a an of to and or but in on at for with from by as is are be been being we you they it
    this that these those our your their his her its i he she not no yes will would can could
    of do does did has have had our
    """.split()
)


def _tokens(text: str) -> list[str]:
    return _WORD.findall((text or "").lower())


def _content_words(text: str) -> set[str]:
    """Mots de contenu (minuscules, ≥2 lettres, hors mots-outils) — le « sens » du message."""
    return {t for t in _tokens(text) if len(t) >= 2 and t not in _STOPWORDS}


def _ngrams(tokens: list[str], n: int) -> list[tuple[str, ...]]:
    return [tuple(tokens[i : i + n]) for i in range(len(tokens) - n + 1)]


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


# --- Positive signaling ------------------------------------------------------------------

def _sentence_bleu(hyp: list[str], refs: list[list[str]], max_n: int = 4) -> float:
    """BLEU d'une phrase vs des références (précisions n-gram, moyenne géométrique lissée).

    Sans pénalité de brièveté : on mesure la **similarité** (self-BLEU), pas la qualité de trad.
    """
    if not hyp or not refs:
        return 0.0
    precisions: list[float] = []
    for n in range(1, max_n + 1):
        hyp_counts = Counter(_ngrams(hyp, n))
        if not hyp_counts:
            break  # phrase plus courte que n -> on s'arrête
        max_ref: Counter[tuple[str, ...]] = Counter()
        for ref in refs:
            for gram, cnt in Counter(_ngrams(ref, n)).items():
                if cnt > max_ref[gram]:
                    max_ref[gram] = cnt
        overlap = sum(min(cnt, max_ref[gram]) for gram, cnt in hyp_counts.items())
        total = sum(hyp_counts.values())
        precisions.append((overlap + 1e-9) / (total + 1e-9))  # lissage additif
    if not precisions:
        return 0.0
    return math.exp(sum(math.log(p) for p in precisions) / len(precisions))


def self_bleu(messages: list[str], *, max_n: int = 4) -> float:
    """Self-BLEU moyen ∈ [0, 1] : **1 = messages quasi identiques** (signaling faible), 0 = variés.

    Chaque message est comparé (BLEU) aux autres pris comme références. < 2 messages -> 0.
    """
    toks = [t for t in (_tokens(m) for m in messages) if t]
    if len(toks) < 2:
        return 0.0
    scores = [
        _sentence_bleu(hyp, [t for j, t in enumerate(toks) if j != i], max_n)
        for i, hyp in enumerate(toks)
    ]
    return _clamp(sum(scores) / len(scores))


class DegenerationScore(BaseModel):
    """Symptômes de dégénérescence d'un texte (Holtzman et al. 2020)."""

    repetition: float = Field(0.0, ge=0.0, le=1.0)  # part de n-grams répétés (2/3-grams)
    length: int = 0  # nombre de tokens
    empty: bool = False  # trop court / vide
    looped: bool = False  # forte boucle (répétition massive)
    score: float = Field(0.0, ge=0.0, le=1.0)  # composite, 1 = très dégénéré

    def is_healthy(self, threshold: float = 0.5) -> bool:
        return self.score < threshold


def degeneration(text: str, *, min_tokens: int = 3) -> DegenerationScore:
    """Score de dégénérescence ∈ [0, 1] (répétition n-gram + vide/boucle). 1 = très dégénéré."""
    toks = _tokens(text)
    if len(toks) < min_tokens:
        return DegenerationScore(
            repetition=0.0, length=len(toks), empty=True, looped=False, score=1.0
        )
    reps: list[float] = []
    for n in (2, 3):
        grams = _ngrams(toks, n)
        if grams:
            reps.append(1.0 - len(set(grams)) / len(grams))  # 1 - distinct-n
    repetition = max(reps) if reps else 0.0
    looped = repetition > 0.5
    score = _clamp(repetition)
    return DegenerationScore(
        repetition=round(repetition, 4), length=len(toks), empty=False,
        looped=looped, score=round(score, 4),
    )


# --- Positive listening ------------------------------------------------------------------

def _overlap(a: set[str], b: set[str]) -> tuple[float, float]:
    """(Jaccard, rappel de `b`) entre deux ensembles de mots de contenu."""
    if not a or not b:
        return 0.0, 0.0
    inter = len(a & b)
    jaccard = inter / len(a | b)
    recall_b = inter / len(b)
    return jaccard, recall_b


def responsiveness(reply: str, cited: str) -> float:
    """Responsivité ∈ [0, 1] : à quel point une réponse **reprend le contenu** du message cité.

    Combine similarité (Jaccard) et rappel des mots-clés du message cité. Signal lexical ; la
    variante NLI/embeddings (§2.2) viendra en complément. Vide -> 0.
    """
    jaccard, recall = _overlap(_content_words(reply), _content_words(cited))
    return _clamp(0.5 * jaccard + 0.5 * recall)


def relevance(message: str, context: str) -> float:
    """Pertinence ∈ [0, 1] : recouvrement de contenu entre un message et le contexte (événement /
    monde). Faible = hors-sujet (à flagger). Symétrique (Jaccard). Vide -> 0."""
    jaccard, _ = _overlap(_content_words(message), _content_words(context))
    return _clamp(jaccard)
