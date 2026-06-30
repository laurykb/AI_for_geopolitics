"""RAG sourcé (Phase 3) : ingestion, retrieval hybride, reranking, citations, éval.

`__init__` ne charge que des éléments légers (pas de torch). Les implémentations
sentence-transformers sont en import paresseux dans `rag.embedder` / `rag.retriever`.
"""

from rag.corpus import chunk_documents, load_corpus
from rag.documents import Chunk, SourceDoc

__all__ = ["Chunk", "SourceDoc", "chunk_documents", "load_corpus"]
