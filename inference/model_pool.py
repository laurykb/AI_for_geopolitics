"""Routeur de backends par modèle, sérialisé pour une machine mono-GPU."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from typing import Any

from inference.backend import InferenceBackend, InferenceResult
from inference.ollama_backend import OllamaBackend


class TaggedBackend(InferenceBackend):
    """Délègue à un backend injecté tout en exposant le tag attendu au transcript.

    C'est notamment utile aux tests offline : un seul MockBackend peut représenter plusieurs
    modèles sans lancer Ollama, tandis que le casting et le replay conservent leurs tags.
    """

    def __init__(self, inner: InferenceBackend, model: str, *, think: bool = False) -> None:
        self._inner = inner
        self.model = model
        # Marqueur du rôle reasoning du casting (l'activation réelle vit dans le backend
        # Ollama sous-jacent) : les tests offline vérifient le routage sans GPU.
        self.think = think

    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        max_tokens: int = 512,
        temperature: float = 0.7,
        schema: dict[str, Any] | None = None,
        plain: bool = False,
        repeat_penalty: float | None = None,
    ) -> InferenceResult:
        return self._inner.generate(
            prompt,
            system=system,
            max_tokens=max_tokens,
            temperature=temperature,
            schema=schema,
            plain=plain,
            repeat_penalty=repeat_penalty,
        )

    def stream_generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        max_tokens: int = 512,
        temperature: float = 0.7,
        repeat_penalty: float | None = None,
    ) -> Iterator[str]:
        yield from self._inner.stream_generate(
            prompt,
            system=system,
            max_tokens=max_tokens,
            temperature=temperature,
            repeat_penalty=repeat_penalty,
        )


class _SequentialOllamaBackend(TaggedBackend):
    def __init__(
        self,
        pool: SequentialOllamaPool,
        inner: OllamaBackend,
        model: str,
        *,
        think: bool = False,
    ) -> None:
        super().__init__(inner, model, think=think)
        self._pool = pool

    def generate(self, prompt: str, **kwargs: Any) -> InferenceResult:
        with self._pool.activate(self.model):
            return self._inner.generate(prompt, **kwargs)

    def stream_generate(self, prompt: str, **kwargs: Any) -> Iterator[str]:
        # Le verrou couvre tout le stream : aucun autre round ne peut décharger les poids
        # pendant que le générateur Ollama émet encore des tokens.
        with self._pool.activate(self.model):
            yield from self._inner.stream_generate(prompt, **kwargs)


class _Activation:
    def __init__(self, pool: SequentialOllamaPool, model: str) -> None:
        self.pool = pool
        self.model = model

    def __enter__(self) -> None:
        self.pool._lock.acquire()
        try:
            if self.pool._current and self.pool._current != self.model:
                self.pool._template.unload_model(self.pool._current)
            self.pool._current = self.model
        except Exception:
            self.pool._lock.release()
            raise

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.pool._lock.release()


class SequentialOllamaPool:
    """Un seul modèle résident, avec changement explicite et verrou par partie."""

    def __init__(self, template: OllamaBackend) -> None:
        self._template = template
        self._lock = threading.RLock()
        self._current = ""
        self._backends: dict[str, _SequentialOllamaBackend] = {}

    def activate(self, model: str) -> _Activation:
        return _Activation(self, model)

    def backend(self, model: str, *, think: bool = False) -> InferenceBackend:
        if model not in self._backends:
            inner = self._template.for_model(model, keep_alive="15m", think=think)
            self._backends[model] = _SequentialOllamaBackend(self, inner, model, think=think)
        return self._backends[model]


def routed_backends(
    default: InferenceBackend,
    model_tags: set[str],
    *,
    reasoning_tags: set[str] | None = None,
) -> dict[str, InferenceBackend]:
    """Construit les backends du casting sans changer le chemin mono-modèle historique.

    `reasoning_tags` (point 5) : les tags castés sur un modèle de raisonnement activent
    l'option think de leur backend. Absent (défaut), rien ne change — rétro-compatible.
    """

    reasoning = reasoning_tags or set()
    if isinstance(default, OllamaBackend):
        pool = SequentialOllamaPool(default)
        return {tag: pool.backend(tag, think=tag in reasoning) for tag in model_tags}
    return {tag: TaggedBackend(default, tag, think=tag in reasoning) for tag in model_tags}
