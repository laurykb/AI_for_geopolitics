"""Tests de l'embedder de hash et de l'index vectoriel in-memory."""

import numpy as np
import pytest

from rag.embedder import HashingEmbedder
from rag.vector_index import InMemoryVectorIndex


def test_hashing_embedder_is_normalized_and_deterministic():
    emb = HashingEmbedder(dim=64)
    a = emb.embed(["freedom of navigation in the Red Sea"])
    b = emb.embed(["freedom of navigation in the Red Sea"])
    assert a.shape == (1, 64)
    assert np.allclose(np.linalg.norm(a, axis=1), 1.0)
    assert np.array_equal(a, b)  # déterministe


def test_hashing_embedder_similar_texts_closer_than_unrelated():
    emb = HashingEmbedder(dim=512)
    v = emb.embed(
        [
            "oil flows through the strait of hormuz",  # référence
            "the strait of hormuz and oil exports",  # proche
            "egypt suez canal trade revenue",  # éloigné
        ]
    )
    sim_close = float(v[0] @ v[1])
    sim_far = float(v[0] @ v[2])
    assert sim_close > sim_far


def test_vector_index_returns_top_k_sorted():
    ids = ["a", "b", "c"]
    mat = np.array([[1.0, 0.0], [0.0, 1.0], [0.9, 0.1]], dtype=np.float32)
    mat /= np.linalg.norm(mat, axis=1, keepdims=True)
    index = InMemoryVectorIndex(ids, mat)

    results = index.search(np.array([1.0, 0.0], dtype=np.float32), k=2)

    assert [r[0] for r in results] == ["a", "c"]  # a (exact) puis c (proche)
    assert results[0][1] >= results[1][1]


def test_vector_index_length_mismatch_raises():
    with pytest.raises(ValueError):
        InMemoryVectorIndex(["a"], np.zeros((2, 3), dtype=np.float32))
