"""Tests de la fusion Reciprocal Rank Fusion."""

from rag.rrf import reciprocal_rank_fusion


def test_rrf_rewards_top_ranks():
    scores = reciprocal_rank_fusion([["a", "b", "c"]], k=60)
    assert scores["a"] > scores["b"] > scores["c"]


def test_rrf_combines_two_lists():
    # 'b' en tête des DEUX listes -> doit dépasser 'a' (haut dans une seule)
    dense = ["b", "a", "c"]
    lexical = ["b", "d", "a"]
    scores = reciprocal_rank_fusion([dense, lexical], k=60)
    assert scores["b"] > scores["a"]
    assert set(scores) == {"a", "b", "c", "d"}


def test_rrf_empty():
    assert reciprocal_rank_fusion([]) == {}
