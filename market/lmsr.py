"""LMSR (Logarithmic Market Scoring Rule) — market maker à perte bornée (fonctions pures).

Cœur mathématique du marché de prédiction. Aucune dépendance (math pur), stable numériquement
via log-sum-exp. Un marché tient un vecteur `q` (parts nettes émises par outcome) et une liquidité
`b > 0`. Voir `docs/spec_market.md` §2 et Hanson (LMSR). Argent fictif uniquement.
"""

from __future__ import annotations

import math


def _logsumexp(xs: list[float]) -> float:
    """`ln( Σ exp(x_i) )` calculé de façon stable (soustraction du max → pas d'overflow)."""
    m = max(xs)
    return m + math.log(sum(math.exp(x - m) for x in xs))


def cost(q: list[float], b: float) -> float:
    """Fonction de coût LMSR : `C(q) = b · ln( Σ_i exp(q_i / b) )`."""
    if b <= 0:
        raise ValueError("b (liquidité) doit être > 0")
    if not q:
        raise ValueError("q ne doit pas être vide")
    return b * _logsumexp([qi / b for qi in q])


def price(q: list[float], b: float) -> list[float]:
    """Prix (= probabilités implicites) par outcome ; les prix somment à 1 (softmax de q/b)."""
    if b <= 0:
        raise ValueError("b (liquidité) doit être > 0")
    if not q:
        raise ValueError("q ne doit pas être vide")
    scaled = [qi / b for qi in q]
    m = max(scaled)
    exps = [math.exp(s - m) for s in scaled]
    total = sum(exps)
    return [e / total for e in exps]


def cost_to_trade(q: list[float], b: float, outcome: int, shares: float) -> float:
    """Coût (crédits) pour acheter `shares` parts de `outcome` (Δ < 0 = vente).

    `cost_to_trade = C(q + shares·e_outcome) − C(q)`. Positif à l'achat, négatif à la vente.
    """
    if not 0 <= outcome < len(q):
        raise ValueError(f"outcome hors bornes : {outcome} (0..{len(q) - 1})")
    after = list(q)
    after[outcome] += shares
    return cost(after, b) - cost(q, b)


def max_loss(b: float, n_outcomes: int) -> float:
    """Perte maximale (subvention) du market maker : `L_max = b · ln(N)`."""
    if b <= 0:
        raise ValueError("b (liquidité) doit être > 0")
    if n_outcomes < 1:
        raise ValueError("n_outcomes doit être >= 1")
    return b * math.log(n_outcomes)
