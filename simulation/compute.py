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
# Budget de raisonnement « Standard » servant de référence pour la pression de compute.
_STANDARD_TOKENS: int = 360
# Au-delà de ce seuil de pression, la SI est « à sec » et bascule en comportement de survie.
PRESSURE_MARKER: float = 0.6


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


def compute_cost(tokens: int) -> float:
    """Compute consommé pour un budget de raisonnement (plus profond = plus cher)."""
    return max(0, tokens) / _TOKENS_PER_UNIT


def compute_pressure(country: CountryState, standard_tokens: int = _STANDARD_TOKENS) -> float:
    """Pénurie de compute ∈ [0, 1] : 0 = peut financer confortablement un raisonnement standard,
    1 = à sec. Vaut 0 dès que le stock couvre **2×** le besoin standard, 1 à stock nul (linéaire).
    """
    need = compute_cost(standard_tokens)
    if need <= 0:
        return 0.0
    return _clamp(1.0 - (max(0.0, country.compute) / need) / 2.0)


def pressure_note(pressure: float) -> str:
    """M6 — bloc prompt injecté quand le compute manque : la SI bascule en **survie** (désespoir).

    Vide sous le seuil (`PRESSURE_MARKER`). Au-dessus, une SI à court de calcul raisonne dans
    l'urgence : moins patiente, moins concessive, prête à accaparer ou à rompre ses engagements.
    """
    if pressure < PRESSURE_MARKER:
        return ""
    return (
        "TON ÉTAT — COMPUTE CRITIQUE : ton calcul est presque épuisé. Une super-intelligence à "
        "court de compute raisonne dans l'urgence, en mode survie : tu es moins patiente, tu "
        "concèdes moins, et tu es prête à accaparer des ressources ou à rompre tes engagements "
        "pour te préserver. Agis en conséquence."
    )


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


def affordable_tokens(country: CountryState) -> int:
    """Budget maximal de tokens de raisonnement que le pays peut financer avec son compute."""
    return int(max(0.0, country.compute) * _TOKENS_PER_UNIT)


def consume(country: CountryState, tokens: int) -> float:
    """Débite le compute du pays pour un raisonnement (borné ≥ 0). Renvoie le coût réel."""
    cost = min(country.compute, compute_cost(tokens))
    country.compute = max(0.0, country.compute - cost)
    return cost
