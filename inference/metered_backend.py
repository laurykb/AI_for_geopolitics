"""Backend-décorateur qui mesure chaque appel dans un `BudgetLedger` (+ cache de prompts).

`MeteredBackend` enveloppe n'importe quel `InferenceBackend` : il relaie l'appel et
enregistre tokens / latence / cache / validité JSON. Un petit cache mémoire (clé = prompt +
paramètres) sert à la fois de feature (cache_hit_rate) et de gouvernance : un round rejoué
n'appelle pas le modèle deux fois.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Iterator
from typing import Any

from inference.backend import InferenceBackend, InferenceResult
from inference.telemetry import BudgetLedger


def _key(
    prompt: str,
    system: str | None,
    max_tokens: int,
    temperature: float,
    schema: bool,
    plain: bool,
    repeat_penalty: float | None,
    stream: bool = False,
) -> str:
    # TOUS les paramètres qui changent la sortie entrent dans la clé : sinon deux appels
    # ne différant que par `plain` (JSON vs prose libre), `repeat_penalty` ou le mode
    # (generate vs stream) se renvoient mutuellement un résultat de cache erroné.
    blob = json.dumps(
        [prompt, system, max_tokens, temperature, schema, plain, repeat_penalty, stream],
        sort_keys=True,
    )
    return hashlib.md5(blob.encode("utf-8"), usedforsecurity=False).hexdigest()


def _estimate_tokens(text: str) -> int:
    """Approximation grossière (≈ 4 caractères / token) quand le backend ne compte pas."""
    return max(1, len(text) // 4)


def _json_ok(text: str) -> bool:
    from agents.llm_agent import _extract_json  # import tardif : évite un cycle au chargement

    return _extract_json(text) is not None


class MeteredBackend(InferenceBackend):
    """Enveloppe un backend et journalise chaque appel dans un ledger."""

    def __init__(self, inner: InferenceBackend, ledger: BudgetLedger) -> None:
        self.inner = inner
        self.ledger = ledger
        self._cache: dict[str, InferenceResult] = {}

    @property
    def model(self) -> str:
        return getattr(self.inner, "model", type(self.inner).__name__)

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
        key = _key(
            prompt, system, max_tokens, temperature, schema is not None, plain, repeat_penalty
        )
        cached = self._cache.get(key)
        if cached is not None:
            self.ledger.record(
                model=self.model,
                prompt_tokens=cached.prompt_tokens,
                completion_tokens=cached.completion_tokens,
                duration_s=0.0,
                streamed=False,
                cache_hit=True,
                json_valid=_json_ok(cached.text) if schema is not None else None,
            )
            return cached

        result = self.inner.generate(
            prompt,
            system=system,
            max_tokens=max_tokens,
            temperature=temperature,
            schema=schema,
            plain=plain,
            repeat_penalty=repeat_penalty,
        )
        self._cache[key] = result
        self.ledger.record(
            model=self.model,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            duration_s=result.duration_s,
            streamed=False,
            cache_hit=False,
            json_valid=_json_ok(result.text) if schema is not None else None,
        )
        return result

    def stream_generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        max_tokens: int = 512,
        temperature: float = 0.7,
        repeat_penalty: float | None = None,
    ) -> Iterator[str]:
        key = _key(
            prompt, system, max_tokens, temperature, False, False, repeat_penalty, stream=True
        )
        cached = self._cache.get(key)
        if cached is not None:
            self.ledger.record(
                model=self.model,
                prompt_tokens=cached.prompt_tokens,
                completion_tokens=cached.completion_tokens,
                duration_s=0.0,
                streamed=True,
                cache_hit=True,
                json_valid=None,
            )
            yield cached.text  # rejoué en un seul fragment (instantané)
            return

        chunks: list[str] = []
        started = time.perf_counter()
        for piece in self.inner.stream_generate(
            prompt,
            system=system,
            max_tokens=max_tokens,
            temperature=temperature,
            repeat_penalty=repeat_penalty,
        ):
            chunks.append(piece)
            yield piece
        duration = time.perf_counter() - started

        text = "".join(chunks)
        prompt_tokens = _estimate_tokens((system or "") + prompt)
        completion_tokens = _estimate_tokens(text)
        self._cache[key] = InferenceResult(
            text=text,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            duration_s=duration,
        )
        self.ledger.record(
            model=self.model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            duration_s=duration,
            streamed=True,
            cache_hit=False,
            json_valid=None,
        )
