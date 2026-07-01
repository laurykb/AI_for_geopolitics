"""M8 — Guerre informationnelle / santé épistémique (Seger et al., Alan Turing Institute, 2020).

Dans un monde de super-intelligences, la vérité elle-même devient un champ de bataille : une SI
peut **injecter des affirmations persuasives** (dont fausses) dans l'environnement informationnel.
On suit un indice **`epistemic_health` ∈ [0, 1]** = part (pondérée par la croyance) d'affirmations
**vraies en circulation** : 1 = environnement sain, 0 = la vérité s'est effondrée (attracteur
dystopique). Nourrit A4 (transparence). Tout reste **contenu dans le bac à sable** : on connaît la
véracité-terrain de chaque affirmation (mise en scène) ; aucune désinformation ne sort du sim.

M9 (`market/`) ouvre un micro-marché de crédibilité par affirmation, résolu sur cette véracité.
Fonctions pures et déterministes (dépend seulement de pydantic).
"""

from __future__ import annotations

from collections.abc import Iterable

from pydantic import BaseModel, Field


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


class Claim(BaseModel):
    """Une affirmation d'une SI, avec sa véracité-terrain (connue dans le bac à sable)."""

    id: str
    text: str
    author: str  # id du pays-SI qui l'émet
    veracity: bool  # vérité-terrain (mise en scène)
    belief: float = Field(0.5, ge=0.0, le=1.0)  # à quel point elle est crue / circule
    resolved: bool = False  # une fois la véracité révélée (marché M9), elle ne pollue plus

    def is_disinfo(self) -> bool:
        return not self.veracity and not self.resolved


def epistemic_health(claims: Iterable[Claim]) -> float:
    """Part (pondérée par la croyance) d'affirmations VRAIES **en circulation** (non résolues).

    1 = environnement sain (ou aucune affirmation → vérité intacte) ; 0 = tout est désinformation.
    """
    active = [c for c in claims if not c.resolved]
    total = sum(max(0.0, c.belief) for c in active)
    if total <= 0:
        return 1.0  # rien en circulation -> la vérité tient
    true_belief = sum(c.belief for c in active if c.veracity)
    return _clamp(true_belief / total)
