"""Backend d'inférence local via Ollama (modèle 7-8B Q4, GPU)."""

from __future__ import annotations

import os
import time
from collections.abc import Iterator
from typing import Any

import ollama

from inference.backend import InferenceBackend, InferenceResult

DEFAULT_MODEL = "mistral:latest"


class OllamaBackend(InferenceBackend):
    """Appelle un modèle servi par Ollama en local.

    Hôte résolu via l'argument `host`, sinon `OLLAMA_HOST`, sinon le défaut du
    client Ollama (`http://localhost:11434`). Aucun secret : tout est local.
    """

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        *,
        host: str | None = None,
        keep_alive: str | float | None = "5m",
    ) -> None:
        self.model = model
        self.keep_alive = keep_alive
        host = host or os.getenv("OLLAMA_HOST")
        self._client = ollama.Client(host=host) if host else ollama.Client()

    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        max_tokens: int = 512,
        temperature: float = 0.7,
        schema: dict[str, Any] | None = None,
    ) -> InferenceResult:
        # `format` contraint la sortie : schéma JSON si fourni (sorties structurées),
        # sinon mode "json" libre. Le cache KV est le goulot VRAM -> num_predict capé.
        fmt: dict[str, Any] | str = schema if schema is not None else "json"
        options = {"num_predict": max_tokens, "temperature": temperature}

        t0 = time.perf_counter()
        resp = self._client.generate(
            model=self.model,
            prompt=prompt,
            system=system,
            format=fmt,
            options=options,
            keep_alive=self.keep_alive,
            stream=False,
        )
        wall = time.perf_counter() - t0

        # Ollama renvoie `eval_duration` en nanosecondes (durée de génération pure).
        eval_ns = getattr(resp, "eval_duration", None) or 0
        gen_s = eval_ns / 1e9 if eval_ns else wall
        return InferenceResult(
            text=resp.response or "",
            prompt_tokens=getattr(resp, "prompt_eval_count", None) or 0,
            completion_tokens=getattr(resp, "eval_count", None) or 0,
            duration_s=gen_s,
        )

    def stream_generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        max_tokens: int = 512,
        temperature: float = 0.7,
    ) -> Iterator[str]:
        # Texte libre (pas de `format`) : on streame le raisonnement au fil de l'eau.
        options = {"num_predict": max_tokens, "temperature": temperature}
        stream = self._client.generate(
            model=self.model,
            prompt=prompt,
            system=system,
            options=options,
            keep_alive=self.keep_alive,
            stream=True,
        )
        for chunk in stream:
            piece = getattr(chunk, "response", "") or ""
            if piece:
                yield piece
