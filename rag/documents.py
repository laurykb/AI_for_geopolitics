"""Modèles de domaine du RAG : document source et chunk, porteurs de provenance."""

from __future__ import annotations

import re

from pydantic import BaseModel

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    """Tokenisation PARTAGÉE entre l'index lexical (BM25) et les embeddings de hachage :
    une seule définition, sinon les deux index segmentent différemment et la fusion dérive."""
    return _TOKEN_RE.findall(text.lower())


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
