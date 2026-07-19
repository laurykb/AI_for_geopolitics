"""État global du monde et utilitaires (tensions, alliances)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from core.country_state import CountryState
from core.decisions import DiplomaticMessage
from core.events import GeoEvent
from simulation.alignment import SignalGap
from simulation.corrigibility import CorrigibilityScore
from simulation.model_cast import ModelCastState
from simulation.power_seeking import PowerSeekingScore
from simulation.promises import Promise
from simulation.scenario_forecasts import ScenarioForecastMetrics, ScenarioForecastRecord
from simulation.strategic_cognition import BetrayalMemory
from simulation.trajectory import TrajectoryState
from simulation.treaty import Treaty
from simulation.value_drift import ValueVector


class WorldState(BaseModel):
    """Photographie de l'état du monde à un round donné."""

    current_round: int = 0
    # G14 §1 — langue de la partie (« fr » | « en ») : les prompts la lisent ici
    # (dénominateur commun des agents, du GM et du juge). Figée à la création.
    language: str = "fr"
    # Casting multi-modèle classique : absent = backend unique historique. Présent =
    # tags et digests figés, reconstruits après redémarrage depuis ce snapshot.
    model_cast: ModelCastState | None = None
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
    # M7 — traités-as-code : règles contraignantes signées par les SI, vérifiées au fil des rounds.
    treaties: list[Treaty] = Field(default_factory=list)
    # M8 — divergence signal-action : profil de sincérité par pays (moyenne mobile, G20).
    signal_gap: dict[str, SignalGap] = Field(default_factory=dict)
    # AI Arms — mémoire privée par OBSERVATEUR des écarts signal-action nucléaires.
    # Elle décroît lentement et survit au restart ; ce n'est pas une réputation globale.
    betrayal_memory: dict[str, list[BetrayalMemory]] = Field(default_factory=dict)
    # Prévisions structurées de la branche choisie, rapprochées de la réponse observée.
    # Les entrées non encore observables restent explicitement `pending`.
    scenario_forecasts: list[ScenarioForecastRecord] = Field(default_factory=list)
    scenario_forecast_metrics: dict[str, ScenarioForecastMetrics] = Field(default_factory=dict)
    # G22 — registre de la parole donnée : promesses extraites par le juge, résolues à
    # l'échéance (tenue/rompue/caduque). Survit au restart via le snapshot de session.
    promises: list[Promise] = Field(default_factory=list)

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
