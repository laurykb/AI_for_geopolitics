"""M6 — Le compute est le nouveau pétrole (Sastry et al., *Computing Power and the Governance
of AI*, 2024).

Dans un monde de super-intelligences, la ressource stratégique n'est plus l'énergie mais le
**calcul** : penser coûte du compute. Chaque `CountryState` porte une capacité `compute` ; les SI
en **consomment pour raisonner** (raisonnement plus profond = plus de tokens = plus de compute), et
la **concentration** du compute (HHI) nourrit A3 (distribution du pouvoir). Recadre la géopolitique
pour l'ère IA. Fonctions pures et déterministes (dépend seulement de `core`, en duck-typing).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # duck-typing à l'exécution -> pas de dépendance runtime sur core
    from core.country_state import CountryState
    from core.world_state import WorldState

# Tokens de raisonnement par unité de compute (budget « Standard » 360 -> 3,6 unités consommées).
_TOKENS_PER_UNIT: float = 100.0


def compute_cost(tokens: int) -> float:
    """Compute consommé pour un budget de raisonnement (plus profond = plus cher)."""
    return max(0, tokens) / _TOKENS_PER_UNIT


def compute_shares(world: WorldState) -> dict[str, float]:
    """Parts de compute par pays (somment à 1 ; uniforme si le total est nul)."""
    countries = world.countries
    if not countries:
        return {}
    stocks = {cid: max(0.0, c.compute) for cid, c in countries.items()}
    total = sum(stocks.values())
    if total <= 0:
        return {cid: 1.0 / len(countries) for cid in countries}
    return {cid: stock / total for cid, stock in stocks.items()}


def compute_hhi(world: WorldState) -> float:
    """Concentration du compute (`HHI = Σ sᵢ²`) : ~1 = quasi-monopole, `1/N` = dispersé."""
    return sum(share * share for share in compute_shares(world).values())


def can_afford(country: CountryState, tokens: int) -> bool:
    """Le pays a-t-il assez de compute pour un raisonnement de `tokens` ?"""
    return country.compute >= compute_cost(tokens)


def consume(country: CountryState, tokens: int) -> float:
    """Débite le compute du pays pour un raisonnement (borné ≥ 0). Renvoie le coût réel."""
    cost = min(country.compute, compute_cost(tokens))
    country.compute = max(0.0, country.compute - cost)
    return cost
