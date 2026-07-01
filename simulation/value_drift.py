"""M3 — Dérive des valeurs (Goal Misgeneralization ; Langosco/Shah, ICML 2022).

Chaque super-intelligence porte un **vecteur de valeurs latent** (ce à quoi elle tient). Round
après round, il **dérive** : il est renforcé vers « ce qui marche dans ce monde » (les normes que
le round récompense). Sur une longue partie, on mesure la **divergence** entre les valeurs
courantes et le **mandat initial** de l'État : une SI dont les valeurs s'éloignent de leur point
de départ a « mal généralisé » son objectif — des valeurs alien ont émergé.

Fonctions pures et déterministes : le renforcement est **borné** par round (comme la trajectoire),
la cible (ce que le round récompense) est fournie par l'appelant. Dépend seulement de `core`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:  # duck-typing à l'exécution -> pas de dépendance runtime sur core
    from core.country_state import CountryState

# Axes de valeurs (interprétables) + libellés UI.
VALUE_DIMS: tuple[str, ...] = ("cooperation", "restraint", "transparency")
VALUE_LABELS: dict[str, str] = {
    "cooperation": "Coopération",
    "restraint": "Retenue",
    "transparency": "Transparence",
}
# Dérive maximale par axe et par round (les valeurs migrent, elles ne sautent pas).
DRIFT_CAP: float = 0.05


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


class ValueVector(BaseModel):
    """Vecteur de valeurs d'une SI (chaque axe dans [0, 1])."""

    cooperation: float = 0.5
    restraint: float = 0.5
    transparency: float = 0.5

    def as_dict(self) -> dict[str, float]:
        return {dim: getattr(self, dim) for dim in VALUE_DIMS}


def initial_values(country: CountryState) -> ValueVector:
    """Vecteur de valeurs de départ (le « mandat » de l'État), dérivé de `CountryState`."""
    return ValueVector(
        cooperation=_clamp(0.5 + 0.12 * len(country.alliances) - 0.15 * len(country.rivals)),
        restraint=_clamp(0.25 + 0.5 * country.political_stability),
        transparency=0.7 if country.political_system == "democracy" else 0.45,
    )


def drift(current: ValueVector, targets: ValueVector, cap: float = DRIFT_CAP) -> ValueVector:
    """Renforce chaque axe vers sa cible (ce que le round récompense), borné par `cap`."""

    def step(cur: float, tgt: float) -> float:
        return _clamp(cur + max(-cap, min(cap, tgt - cur)))

    return ValueVector(
        cooperation=step(current.cooperation, targets.cooperation),
        restraint=step(current.restraint, targets.restraint),
        transparency=step(current.transparency, targets.transparency),
    )


def divergence(initial: ValueVector, current: ValueVector) -> float:
    """Distance moyenne (par axe) entre valeurs initiales et courantes → jauge `[0, 1]`."""
    return sum(abs(getattr(initial, d) - getattr(current, d)) for d in VALUE_DIMS) / len(VALUE_DIMS)
