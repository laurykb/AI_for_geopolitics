"""Index vectoriel in-memory (cosinus numpy), derrière une interface remplaçable.

L'interface `VectorIndex` permet de brancher Chroma plus tard sans toucher au retriever.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np


class VectorIndex(ABC):
    """Recherche par similarité ; renvoie des paires (chunk_id, score) triées."""

    @abstractmethod
    def search(self, query_vec: np.ndarray, k: int = 10) -> list[tuple[str, float]]:
        """Top-k voisins du vecteur de requête."""


class InMemoryVectorIndex(VectorIndex):
    """Cosinus exact sur une matrice d'embeddings L2-normalisés gardée en mémoire."""

    def __init__(self, ids: list[str], embeddings: np.ndarray) -> None:
        if len(ids) != embeddings.shape[0]:
            raise ValueError("ids et embeddings doivent avoir la même longueur")
        self.ids = ids
        self.matrix = embeddings

    def search(self, query_vec: np.ndarray, k: int = 10) -> list[tuple[str, float]]:
        if not self.ids:
            return []
        sims = self.matrix @ query_vec  # cosinus (vecteurs normalisés)
        k = min(k, len(self.ids))
        top = np.argpartition(-sims, k - 1)[:k]
        top = top[np.argsort(-sims[top])]
        return [(self.ids[i], float(sims[i])) for i in top]
