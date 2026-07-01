"""Tests de l'index lexical BM25."""

from rag.corpus import chunk_documents
from rag.documents import SourceDoc
from rag.lexical import BM25Index


def _chunks():
    docs = [
        SourceDoc(id="hormuz", title="Hormuz", text="The strait of hormuz oil chokepoint."),
        SourceDoc(id="suez", title="Suez", text="The suez canal trade revenue for egypt."),
        SourceDoc(id="nav", title="Nav", text="Freedom of navigation in the red sea."),
    ]
    return chunk_documents(docs, max_chars=500)


def test_bm25_ranks_keyword_match_first():
    index = BM25Index(_chunks())
    results = index.search("hormuz oil chokepoint", k=3)
    assert results
    assert results[0][0].startswith("hormuz")


def test_bm25_empty_index_returns_empty():
    assert BM25Index([]).search("anything") == []
