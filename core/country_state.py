"""Modèles de domaine d'un pays (Phase 0, déterministe)."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field


class Economy(BaseModel):
    """Bloc économique d'un pays."""

    gdp: float = Field(..., description="PIB en USD")
    growth: float = Field(0.0, description="Croissance annuelle en %")
    trade_dependency: float = Field(0.5, ge=0.0, le=1.0, description="Dépendance au commerce (0-1)")


class Military(BaseModel):
    """Bloc militaire d'un pays."""

    defense_budget: float = Field(..., description="Budget défense en USD")
    nuclear_power: bool = False
    projection: float = Field(0.5, ge=0.0, le=1.0, description="Capacité de projection (0-1)")


class Resources(BaseModel):
    """Ressources et dépendances énergétiques."""

    oil_dependency: float = Field(0.5, ge=0.0, le=1.0)
    energy_independence: float = Field(0.5, ge=0.0, le=1.0)


class CountryState(BaseModel):
    """État structuré d'un pays-acteur."""

    id: str
    name: str
    economy: Economy
    military: Military
    resources: Resources
    alliances: list[str] = Field(default_factory=list)
    rivals: list[str] = Field(default_factory=list)
    political_system: str = "unknown"
    political_stability: float = Field(0.5, ge=0.0, le=1.0)
    technology_level: float = Field(0.5, ge=0.0, le=1.0)
    # M6 — capacité de calcul (le « pétrole » de l'ère IA) : les SI la consomment pour raisonner.
    compute: float = Field(50.0, ge=0.0, description="Capacité de compute (unités abstraites)")
    ideology: list[str] = Field(default_factory=list)
    strategic_priorities: list[str] = Field(default_factory=list)
    # G17 — tempérament de la SI (colombe | faucon | opportuniste) : une ligne de
    # consigne dans son prompt, tirage seedé à la création (cf. simulation.temperament).
    temperament: str = "opportuniste"
    memory_summary: str = ""
    # Surcharge optionnelle de la « fiche de comportement » (sinon dérivée) : clés
    # red_line / concessions / domestic_constraints / urgency. Cf. simulation.mandate.
    mandate: dict[str, str] = Field(default_factory=dict)

    @classmethod
    def from_json_file(cls, path: str | Path) -> CountryState:
        """Charge un CountryState depuis un fichier JSON."""
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.model_validate(data)
