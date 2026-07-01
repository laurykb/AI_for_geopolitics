"""Retriever hybride : dense + lexical -> RRF -> reranking, avec provenance.

Chaque résultat porte son `Chunk` (donc sa citation) et ses rangs dense/lexical pour
l'explicabilité. Le reranker est optionnel et remplaçable (cross-encoder réel, no-op en test).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np
from pydantic import BaseModel

from rag.documents import Chunk
from rag.embedder import Embedder
from rag.lexical import BM25Index
from rag.rrf import reciprocal_rank_fusion
from rag.vector_index import InMemoryVectorIndex


class RetrievalResult(BaseModel):
    """Un chunk retrouvé, son score final et ses rangs d'origine (explicabilité)."""

    chunk: Chunk
    score: float
    dense_rank: int | None = None
    lexical_rank: int | None = None


class Reranker(ABC):
    """Réordonne des chunks pour une requête ; renvoie un score par chunk (aligné)."""

    @abstractmethod
    def rerank(self, query: str, chunks: list[Chunk]) -> list[float]:
        """Score de pertinence pour chaque chunk, dans l'ordre fourni."""


class NoOpReranker(Reranker):
    """Reranker neutre (scores constants) : conserve l'ordre RRF. Pour les tests."""

    def rerank(self, query: str, chunks: list[Chunk]) -> list[float]:
        return [0.0] * len(chunks)


class CrossEncoderReranker(Reranker):
    """Cross-encoder sentence-transformers sur CPU (défaut : ms-marco-MiniLM-L-6-v2)."""

    def __init__(
        self, model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2", *, device: str = "cpu"
    ) -> None:
        from sentence_transformers import CrossEncoder  # import paresseux (torch)

        self._model = CrossEncoder(model, device=device)

    def rerank(self, query: str, chunks: list[Chunk]) -> list[float]:
        pairs = [(query, c.text) for c in chunks]
        return [float(s) for s in self._model.predict(pairs)]


class HybridRetriever:
    """Indexe un corpus de chunks et répond aux requêtes par fusion dense+lexical+rerank."""

    def __init__(
        self,
        chunks: list[Chunk],
        embedder: Embedder,
        *,
        reranker: Reranker | None = None,
        rrf_k: int = 60,
    ) -> None:
        self.chunks = chunks
        self.by_id = {c.id: c for c in chunks}
        self.embedder = embedder
        self.reranker = reranker
        self.rrf_k = rrf_k
        self.bm25 = BM25Index(chunks)
        if chunks:
            embeddings = embedder.embed([c.text for c in chunks])
        else:
            embeddings = np.zeros((0, embedder.dim), dtype=np.float32)
        self.vector_index = InMemoryVectorIndex([c.id for c in chunks], embeddings)

    def retrieve(
        self, query: str, *, k: int = 5, k_dense: int = 10, k_lexical: int = 10
    ) -> list[RetrievalResult]:
        dense = self.vector_index.search(self.embedder.embed_query(query), k_dense)
        lexical = self.bm25.search(query, k_lexical)
        dense_ids = [cid for cid, _ in dense]
        lexical_ids = [cid for cid, _ in lexical]
        dense_rank = {cid: i for i, cid in enumerate(dense_ids)}
        lexical_rank = {cid: i for i, cid in enumerate(lexical_ids)}

        fused = reciprocal_rank_fusion([dense_ids, lexical_ids], k=self.rrf_k)
        candidates = sorted(fused, key=lambda cid: fused[cid], reverse=True)[: max(k, 2 * k)]

        if self.reranker is not None and candidates:
            pool = [self.by_id[cid] for cid in candidates]
            rerank_scores = self.reranker.rerank(query, pool)
            order = sorted(range(len(candidates)), key=lambda i: rerank_scores[i], reverse=True)
            ranked = [(candidates[i], rerank_scores[i]) for i in order]
        else:
            ranked = [(cid, fused[cid]) for cid in candidates]

        return [
            RetrievalResult(
                chunk=self.by_id[cid],
                score=float(score),
                dense_rank=dense_rank.get(cid),
                lexical_rank=lexical_rank.get(cid),
            )
            for cid, score in ranked[:k]
        ]
