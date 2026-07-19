"""Backend déterministe pour les tests : aucune dépendance GPU ni serveur."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from inference.backend import InferenceBackend, InferenceResult


class MockBackend(InferenceBackend):
    """Renvoie des réponses prédéfinies et enregistre les appels.

    `responses` : soit une chaîne unique (toujours renvoyée), soit une liste
    consommée appel par appel (la dernière est répétée une fois épuisée). Permet
    de scénariser JSON valide, JSON à réparer, sortie invalide, etc.
    """

    def __init__(
        self,
        responses: str | list[str] = "{}",
        *,
        completion_tokens: int = 20,
        prompt_tokens: int = 100,
        duration_s: float = 0.1,
    ) -> None:
        self._queue: list[str] = [responses] if isinstance(responses, str) else list(responses)
        if not self._queue:
            self._queue = ["{}"]
        self.completion_tokens = completion_tokens
        self.prompt_tokens = prompt_tokens
        self.duration_s = duration_s
        self.calls: list[dict[str, Any]] = []

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
        self.calls.append(
            {
                "prompt": prompt,
                "system": system,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "schema": schema,
                "plain": plain,
                "repeat_penalty": repeat_penalty,
            }
        )
        text = self._queue.pop(0) if len(self._queue) > 1 else self._queue[0]
        return InferenceResult(
            text=text,
            prompt_tokens=self.prompt_tokens,
            completion_tokens=self.completion_tokens,
            duration_s=self.duration_s,
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
        self.calls.append(
            {
                "prompt": prompt,
                "system": system,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "repeat_penalty": repeat_penalty,
                "stream": True,
            }
        )
        text = self._queue.pop(0) if len(self._queue) > 1 else self._queue[0]
        # Émet mot par mot pour simuler le flux (concat == texte complet).
        for i, word in enumerate(text.split(" ")):
            yield word if i == 0 else " " + word
