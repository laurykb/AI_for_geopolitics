"""Négociation multi-tours et arbitrage : messages, verdict du juge, garde-fou.

Les super-intelligences échangent des messages en langage naturel (transcript). Un juge
LLM produit un `Verdict` (deltas d'attributs, tensions, pactes). `apply_verdict` applique
ce verdict **borné** (garde-fou déterministe) — le LLM interprète, mais ne dérape pas.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, Field

from core.world_state import WorldState
from simulation.diplomacy import pact_id


class NegotiationMessage(BaseModel):
    """Une prise de parole d'un pays dans la négociation d'un round."""

    country: str
    text: str
    pass_no: int = 0
    seconds: float = 0.0
    model: str = ""


@dataclass
class AttributeDelta:
    """Variation d'un attribut d'un pays sur un round (pour l'affichage)."""

    country: str
    label: str
    before: float
    after: float

    @property
    def change(self) -> float:
        return self.after - self.before


class Verdict(BaseModel):
    """Verdict d'arbitrage du juge (permissif : le garde-fou nettoie derrière)."""

    attribute_deltas: dict = Field(default_factory=dict)  # {id: {croissance, stabilité, ...}}
    tension_deltas: list = Field(default_factory=list)  # [{a, b, delta}]
    new_pacts: list = Field(default_factory=list)  # [[a, b], ...]
    escalation: float = 0.5
    economic_disruption: float = 0.5


def format_transcript(transcript: list[NegotiationMessage], *, limit: int = 14) -> str:
    """Formate le transcript pour un prompt (les `limit` derniers messages)."""
    lines = [f"[P{m.pass_no}] {m.country}: {m.text}" for m in transcript[-limit:]]
    return "\n".join(lines) if lines else "(début de la négociation)"


# Attribut -> (chemin, bornes de la valeur | None) et plafond du delta par round.
_ATTRS: dict[str, tuple[str, tuple[float, float] | None]] = {
    "croissance": ("economy.growth", None),
    "stabilité": ("political_stability", (0.0, 1.0)),
    "techno": ("technology_level", (0.0, 1.0)),
    "projection": ("military.projection", (0.0, 1.0)),
}
_CAPS = {"croissance": 1.5, "stabilité": 0.15, "techno": 0.15, "projection": 0.15}


def _get(obj, path: str) -> float:
    for part in path.split("."):
        obj = getattr(obj, part)
    return float(obj)


def _set(obj, path: str, value: float) -> None:
    parts = path.split(".")
    for part in parts[:-1]:
        obj = getattr(obj, part)
    setattr(obj, parts[-1], value)


def apply_verdict(world: WorldState, verdict: Verdict) -> list[AttributeDelta]:
    """Applique le verdict du juge **borné** ; renvoie les deltas effectivement appliqués."""
    deltas: list[AttributeDelta] = []

    for cid, attrs in verdict.attribute_deltas.items():
        country = world.countries.get(cid)
        if country is None or not isinstance(attrs, dict):
            continue
        for label, raw in attrs.items():
            if label not in _ATTRS:
                continue
            try:
                delta = float(raw)
            except (TypeError, ValueError):
                continue
            path, bounds = _ATTRS[label]
            cap = _CAPS[label]
            delta = max(-cap, min(cap, delta))
            before = _get(country, path)
            after = before + delta
            if bounds is not None:
                after = max(bounds[0], min(bounds[1], after))
            if abs(after - before) > 1e-9:
                _set(country, path, after)
                deltas.append(AttributeDelta(cid, label, before, after))

    for entry in verdict.tension_deltas:
        if not isinstance(entry, dict):
            continue
        a, b, value = entry.get("a"), entry.get("b"), entry.get("delta")
        if a in world.countries and b in world.countries and a != b:
            try:
                world.adjust_tension(a, b, float(value))
            except (TypeError, ValueError):
                continue

    for pact in verdict.new_pacts:
        if (
            isinstance(pact, list | tuple)
            and len(pact) == 2
            and pact[0] in world.countries
            and pact[1] in world.countries
            and pact[0] != pact[1]
        ):
            pid = pact_id(pact[0], pact[1])
            for member in pact:
                alliances = world.countries[member].alliances
                if pid not in alliances:
                    alliances.append(pid)

    return deltas
