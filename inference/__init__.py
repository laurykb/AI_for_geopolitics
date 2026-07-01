"""Service d'inférence local (Phase 1).

Abstraction `InferenceBackend` + implémentations : Ollama (local, GPU) et un mock
déterministe pour les tests (sans GPU ni serveur).
"""

from inference.backend import InferenceBackend, InferenceResult
from inference.mock_backend import MockBackend
from inference.ollama_backend import OllamaBackend

__all__ = [
    "InferenceBackend",
    "InferenceResult",
    "MockBackend",
    "OllamaBackend",
]
