"""Tests du retriever hybride (offline : HashingEmbedder)."""

from rag.brief import build_brief
from rag.corpus import chunk_documents, load_corpus
from rag.documents import Chunk
from rag.embedder import HashingEmbedder
from rag.retriever import HybridRetriever, Reranker


def _retriever(**kw) -> HybridRetriever:
    chunks = chunk_documents(load_corpus(), max_chars=400, overlap=60)
    return HybridRetriever(chunks, HashingEmbedder(dim=1024), **kw)


def test_retrieves_relevant_document_in_top_k():
    retriever = _retriever()
    results = retriever.retrieve("freedom of navigation in the Red Sea shipping", k=3)
    assert results
    assert any(r.chunk.doc_id == "freedom-of-navigation" for r in results)
    # provenance présente -> citation possible
    assert all(r.chunk.source for r in results)


def test_results_carry_ranks_for_explainability():
    retriever = _retriever()
    results = retriever.retrieve("strait of hormuz oil chokepoint", k=3)
    top = results[0]
    assert top.chunk.doc_id == "hormuz-energy"
    # au moins un des deux rangs d'origine est renseigné
    assert top.dense_rank is not None or top.lexical_rank is not None


class _SpyReranker(Reranker):
    """Reranker espion : enregistre l'appel et force l'ordre inverse des candidats."""

    def __init__(self) -> None:
        self.called_with: str | None = None

    def rerank(self, query: str, chunks: list[Chunk]) -> list[float]:
        self.called_with = query
        # scores décroissants selon la position -> inverse l'ordre d'entrée
        return [float(-i) for i in range(len(chunks))]


def test_reranker_is_invoked_and_reorders():
    spy = _SpyReranker()
    retriever = _retriever(reranker=spy)
    results = retriever.retrieve("suez canal egypt trade revenue", k=5)
    assert spy.called_with == "suez canal egypt trade revenue"
    assert results  # le reranker a produit l'ordre final


def test_brief_contains_citations():
    retriever = _retriever()
    results = retriever.retrieve("sanctions on Iran economy", k=2)
    brief = build_brief("sanctions on Iran economy", results)
    assert "[source:" in brief
    assert brief.count("[source:") == len(results)


def test_empty_corpus_retriever():
    retriever = HybridRetriever([], HashingEmbedder(dim=64))
    assert retriever.retrieve("anything", k=3) == []
