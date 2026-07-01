"""Embeddings sur CPU : abstraction + impl sentence-transformers (lazy) + hashing (tests).

Le hashing-trick (`HashingEmbedder`) est déterministe et sans dépendance lourde : il
permet de tester tout le pipeline RAG offline, sans télécharger de modèle ni charger torch.
"""

from __future__ import annotations

import hashlib
import re
from abc import ABC, abstractmethod

import numpy as np

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def _l2_normalize(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return matrix / norms


class Embedder(ABC):
    """Transforme des textes en vecteurs L2-normalisés `[n, dim]`."""

    @property
    @abstractmethod
    def dim(self) -> int:
        """Dimension des vecteurs produits."""

    @abstractmethod
    def embed(self, texts: list[str]) -> np.ndarray:
        """Encode une liste de textes (passages) -> matrice normalisée `[len(texts), dim]`."""

    def embed_query(self, query: str) -> np.ndarray:
        """Encode une requête -> vecteur `[dim]` (par défaut comme un passage)."""
        return self.embed([query])[0]


class HashingEmbedder(Embedder):
    """Embeddings déterministes par hashing-trick (sac de mots projeté), pour les tests."""

    def __init__(self, dim: int = 256) -> None:
        self._dim = dim

    @property
    def dim(self) -> int:
        return self._dim

    def embed(self, texts: list[str]) -> np.ndarray:
        vecs = np.zeros((len(texts), self._dim), dtype=np.float32)
        for i, text in enumerate(texts):
            for token in _tokenize(text):
                digest = hashlib.md5(token.encode("utf-8")).digest()
                bucket = int.from_bytes(digest[:4], "little") % self._dim
                vecs[i, bucket] += 1.0
        return _l2_normalize(vecs)


class SentenceTransformerEmbedder(Embedder):
    """Bi-encoder sentence-transformers sur CPU (défaut : bge-small-en-v1.5)."""

    # Instruction de requête recommandée pour les modèles bge.
    _QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "

    def __init__(self, model: str = "BAAI/bge-small-en-v1.5", *, device: str = "cpu") -> None:
        from sentence_transformers import SentenceTransformer  # import paresseux (torch)

        self._model = SentenceTransformer(model, device=device)
        # `get_embedding_dimension` (récent) avec repli sur l'ancien nom.
        get_dim = (
            getattr(self._model, "get_embedding_dimension", None)
            or self._model.get_sentence_embedding_dimension
        )
        self._dim = int(get_dim())

    @property
    def dim(self) -> int:
        return self._dim

    def embed(self, texts: list[str]) -> np.ndarray:
        emb = self._model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
        return emb.astype(np.float32)

    def embed_query(self, query: str) -> np.ndarray:
        emb = self._model.encode(
            [self._QUERY_INSTRUCTION + query], normalize_embeddings=True, convert_to_numpy=True
        )
        return emb.astype(np.float32)[0]
