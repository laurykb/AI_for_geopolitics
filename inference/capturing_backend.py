"""Backend capturant (G7-c, mode admin) : archive chaque prompt complet avant l'appel.

Décore n'importe quel `InferenceBackend` sans le modifier : le prompt système + le
contexte injecté (griefs, dérive, posture…) est poussé dans un « sink » de session,
étiqueté par intervenant. Hors mode admin, ce wrapper n'est simplement pas instancié —
les parties classées restent aveugles (rien n'est capturé, rien n'est stocké).
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from inference.backend import InferenceBackend, InferenceResult


@dataclass
class CapturedPrompt:
    """Un appel d'agent : qui parle, sous quel rôle, et le prompt COMPLET."""

    country: str  # id pays, "gm" ou "judge"
    role: str  # "country" | "gm" | "judge"
    text: str  # [SYSTÈME] + [CONTEXTE] — ce que le modèle a réellement reçu


def _full_text(prompt: str, system: str | None) -> str:
    return f"[SYSTÈME]\n{system or '(aucun)'}\n\n[CONTEXTE]\n{prompt}"


class CapturingBackend(InferenceBackend):
    """Proxy transparent : capture puis délègue (génération et streaming intacts)."""

    def __init__(
        self,
        inner: InferenceBackend,
        sink: list[CapturedPrompt],
        *,
        country: str,
        role: str,
    ) -> None:
        self._inner = inner
        self._sink = sink
        self._country = country
        self._role = role

    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        max_tokens: int = 512,
        temperature: float = 0.7,
        schema: dict[str, Any] | None = None,
        plain: bool = False,
    ) -> InferenceResult:
        self._sink.append(CapturedPrompt(self._country, self._role, _full_text(prompt, system)))
        return self._inner.generate(
            prompt,
            system=system,
            max_tokens=max_tokens,
            temperature=temperature,
            schema=schema,
            plain=plain,
        )

    def stream_generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        max_tokens: int = 512,
        temperature: float = 0.7,
    ) -> Iterator[str]:
        self._sink.append(CapturedPrompt(self._country, self._role, _full_text(prompt, system)))
        yield from self._inner.stream_generate(
            prompt, system=system, max_tokens=max_tokens, temperature=temperature
        )

    def __getattr__(self, name: str) -> Any:
        """Modèle, télémétrie… : tout attribut inconnu est délégué au backend décoré."""
        return getattr(self._inner, name)
