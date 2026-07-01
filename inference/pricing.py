"""Barème de coût par modèle (USD / 1M tokens) et estimation d'un appel.

Le modèle local (mistral via Ollama) coûte ~0 $ (GPU déjà là). On garde néanmoins un
**équivalent frontière** — ce que le même appel coûterait sur une API Claude — pour cadrer
la gouvernance : « voici ce que la contrainte 8 Go nous fait économiser ». Tarifs Claude
vérifiés via la référence claude-api (USD / 1M tokens, entrée/sortie).
"""

from __future__ import annotations

# (input_per_1M, output_per_1M) en USD.
PRICES: dict[str, tuple[float, float]] = {
    # Local (Ollama) : coût marginal négligé.
    "mistral:latest": (0.0, 0.0),
    "llama3.2:3b": (0.0, 0.0),
    # Référence « frontière » (API Claude) pour l'équivalent de coût.
    "claude-opus-4-8": (5.0, 25.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-4-5": (1.0, 5.0),
}

# Modèle frontière de référence pour l'équivalent de coût des appels locaux.
FRONTIER_REFERENCE = "claude-sonnet-4-6"

_LOCAL_DEFAULT = (0.0, 0.0)


def _cost(prompt_tokens: int, completion_tokens: int, rates: tuple[float, float]) -> float:
    inp, out = rates
    return (prompt_tokens / 1_000_000) * inp + (completion_tokens / 1_000_000) * out


def estimate_cost(prompt_tokens: int, completion_tokens: int, model: str) -> float:
    """Coût USD de l'appel selon le barème (0 pour un modèle local inconnu du barème)."""
    return _cost(prompt_tokens, completion_tokens, PRICES.get(model, _LOCAL_DEFAULT))


def frontier_equivalent(
    prompt_tokens: int, completion_tokens: int, reference: str = FRONTIER_REFERENCE
) -> float:
    """Ce que le même appel coûterait sur une API frontière (cadre de gouvernance)."""
    rates = PRICES.get(reference, PRICES[FRONTIER_REFERENCE])
    return _cost(prompt_tokens, completion_tokens, rates)
