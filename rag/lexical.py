"""Index lexical BM25 (rank_bm25) sur les chunks."""

from __future__ import annotations

from rank_bm25 import BM25Okapi

from rag.documents import Chunk, tokenize


class BM25Index:
    """Recherche lexicale BM25 ; renvoie des paires (chunk_id, score) triées."""

    def __init__(self, chunks: list[Chunk]) -> None:
        self.chunks = chunks
        self._bm25 = BM25Okapi([tokenize(c.text) for c in chunks]) if chunks else None

    def search(self, query: str, k: int = 10) -> list[tuple[str, float]]:
        if self._bm25 is None:
            return []
        scores = self._bm25.get_scores(tokenize(query))
        ranked = sorted(
            zip((c.id for c in self.chunks), scores, strict=True),
            key=lambda pair: pair[1],
            reverse=True,
        )
        return ranked[:k]
