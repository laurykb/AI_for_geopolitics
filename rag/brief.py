"""Génère un brief sourcé (avec citations) à partir des résultats de retrieval."""

from __future__ import annotations

from rag.retriever import RetrievalResult

_SNIPPET_MAX = 240


def build_brief(query: str, results: list[RetrievalResult], *, max_points: int = 5) -> str:
    """Brief compact : une puce citée par source. Chaque puce finit par `[source: ...]`."""
    if not results:
        return f"Brief — {query}\n\nAucune source pertinente trouvée."

    lines = [f"Brief — {query}", ""]
    for result in results[:max_points]:
        snippet = " ".join(result.chunk.text.split())
        if len(snippet) > _SNIPPET_MAX:
            snippet = snippet[:_SNIPPET_MAX].rstrip() + "…"
        lines.append(f"- {snippet} [source: {result.chunk.citation}]")
    return "\n".join(lines)
