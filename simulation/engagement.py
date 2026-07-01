"""Engagement d'un pays dans la négociation — déterministe, sans LLM.

Remplace le round-robin fixe : à chaque tour, on estime l'« envie de parler » de chaque
super-intelligence à partir de la situation (est-elle actrice ? tension ? vient-on de
l'interpeller ? son tempérament ?) et de sa fatigue (a-t-elle déjà beaucoup parlé ?). Un
pays peu concerné reste sous le seuil et **se tait** (0 appel LLM) ; un pays interpellé voit
son score bondir et peut **couper la file** (interruption émergente). Tout est reproductible
(jitter dérivé d'un hash), donc testable offline.
"""

from __future__ import annotations

import hashlib

from core.events import GeoEvent
from core.world_state import WorldState

# En dessous de ce score, le pays ne prend pas la parole (il n'est pas assez concerné).
SPEAK_THRESHOLD = 0.25


def _jitter(*parts: str) -> float:
    """Bruit déterministe dans [0, 1] pour départager des scores proches (reproductible)."""
    digest = hashlib.md5(":".join(parts).encode("utf-8")).digest()
    return int.from_bytes(digest[:2], "little") / 65535.0


def _mentions(text: str, country_id: str, country_name: str) -> bool:
    """Le message interpelle-t-il ce pays (id ou nom cité) ?"""
    low = text.lower()
    return country_id.lower() in low or (len(country_name) > 2 and country_name.lower() in low)


def engagement_score(
    country_id: str,
    event: GeoEvent,
    world: WorldState,
    transcript: list,
    spoke_count: dict[str, int] | None = None,
) -> float:
    """Estime l'envie de parler de `country_id` maintenant (plus c'est haut, plus il veut parler).

    Combine implication dans l'événement, tension vs les acteurs, interpellation dans le
    dernier message, tempérament du profil, fatigue (répétitions) et un micro-jitter.
    """
    spoke_count = spoke_count or {}
    country = world.countries[country_id]
    score = 0.0

    # 1. Implication : acteur de l'événement (fortement) ou simple spectateur (un peu).
    if country_id in event.actors:
        score += 0.40 + 0.30 * event.severity
    else:
        score += 0.10 * event.severity

    # 2. Tension moyenne vis-à-vis des acteurs (plus c'est tendu, plus on intervient).
    rivals_here = [a for a in event.actors if a != country_id]
    if rivals_here:
        avg_tension = sum(world.get_tension(country_id, a) for a in rivals_here) / len(rivals_here)
        score += 0.40 * avg_tension

    # 3. Interpellation : si le dernier message d'un AUTRE pays nous cite -> forte envie de réagir.
    last = next((m for m in reversed(transcript) if m.country != country_id), None)
    if last is not None and _mentions(last.text, country_id, country.name):
        score += 0.60

    # 4. Tempérament dérivé du profil réel.
    dependency = (
        country.economy.trade_dependency
        + country.resources.oil_dependency
        + (1 - country.resources.energy_independence)
    ) / 3
    if country.military.projection >= 0.7 and country.rivals:
        score += 0.15  # assertif : prend plus souvent la parole
    if dependency >= 0.55 or country.military.projection < 0.5:
        score -= 0.05  # prudent/dépendant : un peu moins pressé

    # 5. Fatigue : chaque prise de parole déjà consommée réduit l'envie (anti-monopole).
    score -= 0.35 * spoke_count.get(country_id, 0)

    # 6. Micro-jitter déterministe (dépend du tour) pour départager sans figer l'ordre.
    score += 0.05 * _jitter(country_id, event.id, str(len(transcript)))

    return score
