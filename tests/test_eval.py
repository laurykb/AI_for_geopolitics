"""Tests des métriques d'évaluation (math exacte + run offline sur le corpus seed)."""

from rag.corpus import chunk_documents, load_corpus
from rag.embedder import HashingEmbedder
from rag.eval import evaluate, load_eval_queries, mrr, recall_at_k
from rag.retriever import HybridRetriever


def test_recall_at_k_math():
    assert recall_at_k(["a", "b", "c"], ["a"], k=2) == 1.0
    assert recall_at_k(["x", "b", "a"], ["a"], k=2) == 0.0
    assert recall_at_k(["a", "x", "b"], ["a", "b"], k=3) == 1.0
    assert recall_at_k(["a", "x", "y"], ["a", "b"], k=3) == 0.5


def test_mrr_math():
    assert mrr(["a", "b"], ["a"]) == 1.0
    assert mrr(["x", "a"], ["a"]) == 0.5
    assert mrr(["x", "y"], ["a"]) == 0.0


def test_evaluate_offline_returns_sane_metrics():
    chunks = chunk_documents(load_corpus(), max_chars=400, overlap=60)
    retriever = HybridRetriever(chunks, HashingEmbedder(dim=1024))
    metrics = evaluate(retriever, load_eval_queries(), k=3)

    assert set(metrics) == {"recall@k", "mrr", "k", "n"}
    assert metrics["n"] >= 6
    # même sans modèle réel, le retrieval lexical+hash retrouve la plupart des docs
    assert metrics["recall@k"] > 0.5
