"""Ingestion du corpus sourcé et découpage en chunks (Phase 3)."""

from __future__ import annotations

import json
from pathlib import Path

from rag.documents import Chunk, SourceDoc

DEFAULT_CORPUS_DIR = "data/corpus_seed"
_EVAL_FILE = "eval_queries.json"


def load_corpus(path: str | Path = DEFAULT_CORPUS_DIR) -> list[SourceDoc]:
    """Charge les documents `*.json` du dossier (hors fichier d'évaluation)."""
    docs: list[SourceDoc] = []
    for p in sorted(Path(path).glob("*.json")):
        if p.name == _EVAL_FILE:
            continue
        data = json.loads(p.read_text(encoding="utf-8"))
        docs.append(SourceDoc.model_validate(data))
    return docs


def chunk_documents(
    docs: list[SourceDoc], *, max_chars: int = 500, overlap: int = 80
) -> list[Chunk]:
    """Découpe chaque document en chunks (fenêtre glissante par mots, avec recouvrement)."""
    chunks: list[Chunk] = []
    for doc in docs:
        for i, text in enumerate(_split(doc.text, max_chars, overlap)):
            chunks.append(
                Chunk(
                    id=f"{doc.id}#{i}",
                    doc_id=doc.id,
                    title=doc.title,
                    source=doc.source,
                    text=text,
                )
            )
    return chunks


def _split(text: str, max_chars: int, overlap: int) -> list[str]:
    """Fenêtre glissante par mots : chunks <= max_chars, recouvrement ~overlap chars."""
    words = text.split()
    if not words:
        return []
    chunks: list[str] = []
    current: list[str] = []
    length = 0
    for word in words:
        if current and length + len(word) + 1 > max_chars:
            chunks.append(" ".join(current))
            current = _tail(current, overlap)
            length = sum(len(w) + 1 for w in current)
        current.append(word)
        length += len(word) + 1
    if current:
        chunks.append(" ".join(current))
    return chunks


def _tail(words: list[str], overlap: int) -> list[str]:
    """Derniers mots tenant dans ~`overlap` caractères (recouvrement inter-chunks)."""
    kept: list[str] = []
    length = 0
    for word in reversed(words):
        if length + len(word) + 1 > overlap:
            break
        kept.insert(0, word)
        length += len(word) + 1
    return kept
