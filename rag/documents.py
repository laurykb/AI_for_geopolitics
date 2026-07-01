"""Modèles de domaine du RAG : document source et chunk, porteurs de provenance."""

from __future__ import annotations

from pydantic import BaseModel


class SourceDoc(BaseModel):
    """Document source du corpus, avec sa citation (URL ou référence)."""

    id: str
    title: str
    source: str = ""
    date: str = ""
    text: str


class Chunk(BaseModel):
    """Fragment indexable d'un document, conservant la provenance pour citer."""

    id: str
    doc_id: str
    title: str
    source: str = ""
    text: str

    @property
    def citation(self) -> str:
        """Citation lisible du fragment (titre + source)."""
        return f"{self.title} ({self.source})" if self.source else self.title
