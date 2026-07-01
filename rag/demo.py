"""Demo CLI du RAG (vrais modèles sentence-transformers, CPU).

Usage :
    python -m rag.demo "freedom of navigation in the Red Sea"
    python -m rag.demo --eval        # recall@k / MRR sur le jeu d'évaluation

Nécessite l'extra RAG : `pip install -e ".[rag]"`. Hors pytest.
"""

from __future__ import annotations

import argparse

from rag.brief import build_brief
from rag.corpus import chunk_documents, load_corpus
from rag.embedder import SentenceTransformerEmbedder
from rag.eval import evaluate, load_eval_queries
from rag.retriever import CrossEncoderReranker, HybridRetriever


def build_retriever() -> HybridRetriever:
    chunks = chunk_documents(load_corpus(), max_chars=400, overlap=60)
    return HybridRetriever(chunks, SentenceTransformerEmbedder(), reranker=CrossEncoderReranker())


def main() -> int:
    parser = argparse.ArgumentParser(description="Demo RAG : retrieval hybride + brief sourcé.")
    parser.add_argument("query", nargs="?", default="freedom of navigation in the Red Sea")
    parser.add_argument("--k", type=int, default=4)
    parser.add_argument("--eval", action="store_true", help="évalue recall@k / MRR")
    args = parser.parse_args()

    retriever = build_retriever()

    if args.eval:
        m = evaluate(retriever, load_eval_queries(), k=args.k)
        recall, mrr_, n = m["recall@k"], m["mrr"], int(m["n"])
        print(f"Éval — recall@{args.k}={recall:.2f} | MRR={mrr_:.2f} | n={n}")
        return 0

    results = retriever.retrieve(args.query, k=args.k)
    print(f"Requête : {args.query}\n")
    for r in results:
        print(
            f"[{r.score:.3f}] {r.chunk.citation} (dense={r.dense_rank}, lexical={r.lexical_rank})"
        )
    print()
    print(build_brief(args.query, results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
