"""Reciprocal Rank Fusion : combine plusieurs classements en un score unique."""

from __future__ import annotations

from collections.abc import Iterable


def reciprocal_rank_fusion(ranked_lists: Iterable[list[str]], k: int = 60) -> dict[str, float]:
    """RRF : `score(id) = Σ 1 / (k + rang)` (rang 1-based) sur tous les classements.

    Robuste à l'hétérogénéité des échelles de score (dense vs lexical) : seul le rang compte.
    """
    scores: dict[str, float] = {}
    for ranked in ranked_lists:
        for rank, item_id in enumerate(ranked):
            scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (k + rank + 1)
    return scores
