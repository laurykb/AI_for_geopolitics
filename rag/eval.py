"""Métriques de retrieval : recall@k et MRR sur un jeu de requêtes labellisées."""

from __future__ import annotations

import json
from pathlib import Path

from rag.corpus import DEFAULT_CORPUS_DIR
from rag.retriever import HybridRetriever


def recall_at_k(retrieved_doc_ids: list[str], relevant_doc_ids: list[str], k: int) -> float:
    """Fraction des documents pertinents présents dans le top-k."""
    relevant = set(relevant_doc_ids)
    if not relevant:
        return 0.0
    top = set(retrieved_doc_ids[:k])
    return len(relevant & top) / len(relevant)


def mrr(retrieved_doc_ids: list[str], relevant_doc_ids: list[str]) -> float:
    """Mean Reciprocal Rank : 1/rang du premier document pertinent (0 si absent)."""
    relevant = set(relevant_doc_ids)
    for i, doc_id in enumerate(retrieved_doc_ids):
        if doc_id in relevant:
            return 1.0 / (i + 1)
    return 0.0


def load_eval_queries(path: str | Path = DEFAULT_CORPUS_DIR) -> list[dict]:
    """Charge le jeu d'évaluation `{query, relevant_doc_ids}`."""
    data = json.loads((Path(path) / "eval_queries.json").read_text(encoding="utf-8"))
    return data["queries"]


def evaluate(retriever: HybridRetriever, queries: list[dict], *, k: int = 5) -> dict[str, float]:
    """Moyenne recall@k et MRR (au niveau document) sur l'ensemble des requêtes."""
    recalls: list[float] = []
    mrrs: list[float] = []
    for q in queries:
        results = retriever.retrieve(q["query"], k=k)
        doc_ids = _dedup(r.chunk.doc_id for r in results)
        recalls.append(recall_at_k(doc_ids, q["relevant_doc_ids"], k))
        mrrs.append(mrr(doc_ids, q["relevant_doc_ids"]))
    n = len(queries)
    return {
        "recall@k": sum(recalls) / n if n else 0.0,
        "mrr": sum(mrrs) / n if n else 0.0,
        "k": float(k),
        "n": float(n),
    }


def _dedup(seq) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in seq:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out
