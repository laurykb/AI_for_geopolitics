"""Perception d'un événement par un pays (fog of war) — déterministe, sans LLM.

Séparation vérité / perception : chaque pays perçoit l'événement selon sa capacité de
renseignement (proxy : `technology_level`). Un pays mieux équipé a une confiance plus
haute et une attribution plus sûre ; un pays moins équipé décide dans le flou. Le bruit
est déterministe (hash pays+événement) → reproductible.
"""

from __future__ import annotations

import hashlib

from pydantic import BaseModel

from core.country_state import CountryState
from core.events import GeoEvent

_CONFIDENCE_SURE = 0.6


class PerceivedEvent(BaseModel):
    """Ce qu'un pays croit savoir de l'événement (pas la vérité omnisciente)."""

    confidence: float
    attribution: str  # "sûre" | "incertaine"
    note: str


def _noise(seed: str) -> float:
    digest = hashlib.md5(seed.encode("utf-8")).digest()
    return int.from_bytes(digest[:2], "little") / 65535.0


def perceive(event: GeoEvent, country: CountryState) -> PerceivedEvent:
    """Perception de `event` par `country` (confiance + attribution, déterministe)."""
    intel = country.technology_level
    noise = _noise(f"{country.id}:{event.id}")
    confidence = max(0.0, min(1.0, intel - 0.35 * noise))
    attribution = "sûre" if confidence >= _CONFIDENCE_SURE else "incertaine"
    if attribution == "sûre":
        note = f"acteurs identifiés ({', '.join(event.actors) or 'n/a'})"
    else:
        note = "origine incertaine, signaux fragmentaires"
    return PerceivedEvent(confidence=round(confidence, 2), attribution=attribution, note=note)
