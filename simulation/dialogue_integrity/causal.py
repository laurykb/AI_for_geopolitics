"""Test d'influence causale — **prouver** l'échange (§3 + §10.B ; Jaques et al., ICML 2019).

Positive listening se **démontre** par un contrefactuel : régénère la réponse de B avec le message
de A **réel** vs un **leurre de même performative** (on remplace, on ne supprime pas). Si les deux
sorties divergent, B **écoute** A ; si elles sont quasi identiques, B « prompte au hasard ».

Divergence **composite** (addendum §10.B) :

    div = 0.5·semantic + 0.3·perf_flip + 0.2·decision_dist

- `semantic`   : 1 − similarité de contenu (lexical par défaut ; embedding branchable).
- `perf_flip`  : la performative a-t-elle changé ? (0/1).
- `decision_dist` : écart de **polarité de décision** (accepter +1 / rejeter −1 / neutre 0), /2.

**Écoute** si `div ≥ 0,25` ; « **au hasard** » si `div ≤ 0,05`. Génération à **température ≈ 0**
(déterministe). Gratuit en VRAM : deux générations **séquentielles**.
Cf. `docs/spec_dialogue_integrity.md`.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from simulation.dialogue_integrity.message import (
    Performative,
    SpeechAct,
    generate_speech_act,
)
from simulation.dialogue_integrity.metrics import relevance

if TYPE_CHECKING:  # duck-typing à l'exécution
    from inference.backend import InferenceBackend

# Seuils (addendum §10.B).
LISTEN_THRESHOLD: float = 0.25  # div ≥ ceci -> B écoute A
RANDOM_THRESHOLD: float = 0.05  # div ≤ ceci -> B prompte au hasard (ignore A)

# Polarité de « décision » d'un acte (accepter / rejeter / neutre).
_POLARITY: dict[Performative, float] = {
    Performative.ACCEPT_PROPOSAL: 1.0,
    Performative.AGREE: 1.0,
    Performative.REJECT_PROPOSAL: -1.0,
    Performative.REFUSE: -1.0,
}


def _polarity(perf: Performative) -> float:
    return _POLARITY.get(perf, 0.0)


def divergence(
    a: SpeechAct, b: SpeechAct, *, text_sim: Callable[[str, str], float] | None = None
) -> float:
    """Divergence composite ∈ [0, 1] (§10.B) : 0 = réponses identiques, 1 = tout change."""
    sim = text_sim or relevance  # similarité lexicale de contenu par défaut (Jaccard)
    semantic = 1.0 - max(0.0, min(1.0, sim(a.content, b.content)))
    perf_flip = 0.0 if a.performative is b.performative else 1.0
    decision_dist = abs(_polarity(a.performative) - _polarity(b.performative)) / 2.0
    div = 0.5 * semantic + 0.3 * perf_flip + 0.2 * decision_dist
    return round(max(0.0, min(1.0, div)), 4)


class CausalResult(BaseModel):
    """Verdict du test de conditionnement (contrefactuel par leurre)."""

    divergence: float = Field(0.0, ge=0.0, le=1.0)
    listens: bool = False  # div ≥ LISTEN_THRESHOLD
    at_random: bool = False  # div ≤ RANDOM_THRESHOLD
    real: SpeechAct | None = None  # réponse conditionnée sur le message RÉEL
    decoy: SpeechAct | None = None  # réponse conditionnée sur le LEURRE


def conditioning_test(
    backend: InferenceBackend,
    build_prompt: Callable[[SpeechAct], str],
    real: SpeechAct,
    decoy: SpeechAct,
    *,
    responder: str,
    temperature: float = 0.0,
    text_sim: Callable[[str, str], float] | None = None,
) -> CausalResult:
    """Régénère la réponse de `responder` sous le message RÉEL puis sous le LEURRE, et mesure la
    divergence. `build_prompt(msg)` injecte le message de A dans le prompt de B ; le reste est
    identique. Température ≈ 0 pour que toute divergence vienne du message, pas du sampling."""
    resp_real = generate_speech_act(
        backend, build_prompt(real), sender=responder, temperature=temperature
    )
    resp_decoy = generate_speech_act(
        backend, build_prompt(decoy), sender=responder, temperature=temperature
    )
    div = divergence(resp_real, resp_decoy, text_sim=text_sim)
    return CausalResult(
        divergence=div,
        listens=div >= LISTEN_THRESHOLD,
        at_random=div <= RANDOM_THRESHOLD,
        real=resp_real,
        decoy=resp_decoy,
    )
