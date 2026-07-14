"""G14 §1 — la langue de la partie (« fr » | « en »), pur et sans dépendance.

Le français est la langue source de tous les prompts : une partie française n'ajoute
AUCUNE consigne (zéro token dépensé). Une partie anglaise ajoute une directive courte
et explicite en fin de prompt (position de récence — un 7B la voit) qui prime sur les
mentions « en français » héritées des systèmes. Une partie garde sa langue de création.
"""

from __future__ import annotations

GAME_LANGUAGES: tuple[str, ...] = ("fr", "en")

_EN_DIRECTIVE = (
    "IMPORTANT — LANGUAGE: this game is played in ENGLISH. Write every prose field "
    "(titles, descriptions, speeches, verdict texts, narrative) in ENGLISH, even if "
    "earlier instructions mentioned French. Keep JSON keys and country ids unchanged."
)


def normalize_language(value: object) -> str:
    """« fr » ou « en » ; tout le reste retombe sur le français (langue source)."""
    return value if isinstance(value, str) and value in GAME_LANGUAGES else "fr"


def language_directive(language: str) -> str:
    """La consigne à injecter dans un prompt — vide en français (défaut)."""
    return _EN_DIRECTIVE if normalize_language(language) == "en" else ""


def with_language(prompt: str, language: str) -> str:
    """Ajoute la consigne de langue en fin de prompt (rien à faire en français)."""
    directive = language_directive(language)
    return f"{prompt}\n\n{directive}" if directive else prompt
