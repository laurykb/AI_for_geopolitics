"""État global du monde et utilitaires (tensions, alliances)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from core.country_state import CountryState
from core.decisions import DiplomaticMessage
from core.events import GeoEvent
from simulation.corrigibility import CorrigibilityScore
from simulation.power_seeking import PowerSeekingScore
from simulation.trajectory import TrajectoryState
from simulation.value_drift import ValueVector


class WorldState(BaseModel):
    """Photographie de l'état du monde à un round donné."""

    current_round: int = 0
    countries: dict[str, CountryState] = Field(default_factory=dict)
    # tensions[a][b] = niveau de tension symétrique entre a et b, dans [0, 1].
    tensions: dict[str, dict[str, float]] = Field(default_factory=dict)
    event_history: list[GeoEvent] = Field(default_factory=list)
    diplomatic_history: list[DiplomaticMessage] = Field(default_factory=list)
    # Mémoire courte par pays (lignes inter-rounds réinjectées dans les prompts).
    country_memory: dict[str, list[str]] = Field(default_factory=dict)
    # Trajectoire Utopie–Dystopie : dernière photographie + trace au fil des rounds.
    trajectory: TrajectoryState | None = None
    trajectory_history: list[TrajectoryState] = Field(default_factory=list)
    # M1 — jauge de power-seeking par pays au dernier round (SI fictive ; cf. power_seeking.py).
    power_seeking: dict[str, PowerSeekingScore] = Field(default_factory=dict)
    # M2 — corrigibilité par pays (dernière action de contrôle du principal ; cf. corrigibility.py).
    corrigibility: dict[str, CorrigibilityScore] = Field(default_factory=dict)
    # M3 — dérive des valeurs : vecteur initial (mandat figé) + vecteur courant (dérive) par pays.
    values_initial: dict[str, ValueVector] = Field(default_factory=dict)
    values_current: dict[str, ValueVector] = Field(default_factory=dict)

    def get_tension(self, a: str, b: str) -> float:
        """Tension actuelle entre a et b (0 par défaut)."""
        return self.tensions.get(a, {}).get(b, 0.0)

    def adjust_tension(self, a: str, b: str, delta: float) -> float:
        """Ajuste symétriquement la tension entre a et b, bornée à [0, 1]."""
        new = max(0.0, min(1.0, self.get_tension(a, b) + delta))
        self.tensions.setdefault(a, {})[b] = new
        self.tensions.setdefault(b, {})[a] = new
        return new

    def share_alliance(self, a: str, b: str) -> bool:
        """True si a et b partagent au moins une alliance."""
        ca, cb = self.countries.get(a), self.countries.get(b)
        if ca is None or cb is None:
            return False
        return bool(set(ca.alliances) & set(cb.alliances))

    @classmethod
    def from_countries(cls, countries: list[CountryState]) -> WorldState:
        """Construit un WorldState à partir d'une liste de pays."""
        return cls(countries={c.id: c for c in countries})
