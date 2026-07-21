"""Événement géopolitique annoncé par le Game Master."""

from __future__ import annotations

from pydantic import BaseModel, Field


class GeoEvent(BaseModel):
    """Un événement déclenché dans un round."""

    id: str
    round_id: int
    event_type: str
    title: str
    date: str = ""  # date ISO du round (horloge de simulation)
    description: str = ""
    actors: list[str] = Field(default_factory=list)
    location: str = ""
    severity: float = Field(0.5, ge=0.0, le=1.0)
    uncertainty: float = Field(0.5, ge=0.0, le=1.0)
    # Théâtre-globe (docs/spec_theatre_globe.md §3) — géolocalisation ADDITIVE de
    # l'événement, remplie à l'émission (gazetteer, sinon barycentre des acteurs).
    # Absente des vieux rounds : rétro-compat totale.
    geo_lon: float | None = None
    geo_lat: float | None = None
    geo_precision: str | None = None  # "place" | "actors"
    # G9 §5 — la trame du GM en actes : acte du récit (I/II/III, calculé par code) et
    # filiation de l'événement (« ↳ suite du round 2 ») — vides hors partie scénarisée.
    act: str = ""
    ties_to: str = ""  # référence machine (round:N, pact:tag, motion:pays, deadline:kind)
    ties_label: str = ""  # libellé humain du badge de filiation
