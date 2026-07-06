"""Abstraction d'un backend d'inférence et son résultat (avec télémétrie)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from typing import Any

from pydantic import BaseModel, Field


class InferenceResult(BaseModel):
    """Sortie d'une génération, avec les compteurs nécessaires aux mesures (tok/s).

    `duration_s` est la durée de *génération* (pas la latence réseau), de sorte que
    `tokens_per_second` reflète le débit du modèle. La latence bout-en-bout se mesure
    au niveau du round (cf. `inference.bench`).
    """

    text: str
    prompt_tokens: int = Field(0, ge=0)
    completion_tokens: int = Field(0, ge=0)
    duration_s: float = Field(0.0, ge=0.0)

    @property
    def tokens_per_second(self) -> float:
        """Débit de génération (tokens de sortie / seconde), 0 si non mesurable."""
        return self.completion_tokens / self.duration_s if self.duration_s > 0 else 0.0


class InferenceBackend(ABC):
    """Contrat minimal d'un backend : un prompt -> du texte (+ télémétrie).

    Mono-tour (prompt + system) : suffisant pour une décision de pays en Phase 1.
    `schema` (JSON Schema) permet de contraindre la sortie au format structuré.
    """

    @abstractmethod
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
        """Génère une complétion pour `prompt` et renvoie le texte + la télémétrie.

        `plain=True` (G6) : prose libre, sans contrainte JSON — pour le narrateur."""
        raise NotImplementedError

    def stream_generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        max_tokens: int = 512,
        temperature: float = 0.7,
    ) -> Iterator[str]:
        """Génère en streaming : yield des fragments de texte au fil de l'eau.

        Défaut : repli non-streamé (un seul fragment). Les backends « live » surchargent
        pour émettre les tokens en direct (raisonnement visible dans l'UI).
        """
        yield self.generate(
            prompt, system=system, max_tokens=max_tokens, temperature=temperature
        ).text
