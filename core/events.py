"""Événement géopolitique annoncé par le Game Master."""

from __future__ import annotations

from pydantic import BaseModel, Field


class GeoEvent(BaseModel):
    """Un événement déclenché dans un round."""

    id: str
    round_id: int
    event_type: str
    title: str
    description: str = ""
    actors: list[str] = Field(default_factory=list)
    location: str = ""
    severity: float = Field(0.5, ge=0.0, le=1.0)
    uncertainty: float = Field(0.5, ge=0.0, le=1.0)
