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
        self.host = host or os.getenv("OLLAMA_HOST")
        self._client = ollama.Client(host=self.host) if self.host else ollama.Client()

    def for_model(
        self, model: str, *, keep_alive: str | float | None = "15m"
    ) -> OllamaBackend:
        """Clone léger vers le même serveur ; utilisé par le routeur mono-GPU."""

        return OllamaBackend(model=model, host=self.host, keep_alive=keep_alive)

    def unload_model(self, model: str) -> None:
        """Demande à Ollama de libérer les poids d'un modèle entre deux familles."""

        if not model:
            return
        try:
            self._client.generate(
                model=model,
                prompt="",
                keep_alive=0,
                options={"num_predict": 1},
            )
        except Exception:  # noqa: BLE001 - l'optimisation VRAM ne doit pas tuer la partie
            return

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
        # `format` contraint la sortie : schéma JSON si fourni (sorties structurées),
        # mode "json" libre par défaut, ou AUCUNE contrainte en prose (`plain`, G6 —
        # le narrateur écrit du texte). Cache KV = goulot VRAM -> num_predict capé.
        fmt: dict[str, Any] | str | None = (
            schema if schema is not None else (None if plain else "json")
        )
        options = {"num_predict": max_tokens, "temperature": temperature}
        if repeat_penalty is not None:
            options["repeat_penalty"] = repeat_penalty

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
        repeat_penalty: float | None = None,
    ) -> Iterator[str]:
        # Texte libre (pas de `format`) : on streame le raisonnement au fil de l'eau.
        options = {"num_predict": max_tokens, "temperature": temperature}
        if repeat_penalty is not None:
            options["repeat_penalty"] = repeat_penalty
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
