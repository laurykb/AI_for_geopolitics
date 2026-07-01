"""Escalation Ladder : échelle d'escalade 0-9 + plafond atteignable par pays — déterministe.

Chaque pays a un profil d'escalade (5 paramètres dérivés de `CountryState`, surchargeables) :
`escalation_threshold` (propension à escalader), `risk_tolerance`, `alliance_pressure` (soutien
allié → monte plus haut), `domestic_pressure` et `economic_exposure` (freins). `ceiling` calcule
**jusqu'où** un pays peut monter sur l'échelle face à un événement (0 appel LLM, explicable).
"""

from __future__ import annotations

from dataclasses import dataclass

from core.country_state import CountryState
from core.events import GeoEvent
from core.world_state import WorldState

# Échelle d'escalade (échelon -> intitulé).
LADDER: list[str] = [
    "Observation",  # 0
    "Déclaration publique",  # 1
    "Condamnation",  # 2
    "Sanctions ciblées",  # 3
    "Sanctions sectorielles",  # 4
    "Coalition diplomatique",  # 5
    "Déploiement militaire défensif",  # 6
    "Cyber-réponse",  # 7
    "Frappe limitée",  # 8
    "Conflit ouvert",  # 9
]
MAX_RUNG = len(LADDER) - 1  # 9

_PARAM_KEYS = (
    "escalation_threshold",
    "risk_tolerance",
    "alliance_pressure",
    "domestic_pressure",
    "economic_exposure",
)


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


@dataclass
class EscalationProfile:
    """Les 5 curseurs qui gouvernent l'escalade d'un pays (chacun dans [0, 1])."""

    escalation_threshold: float
    risk_tolerance: float
    alliance_pressure: float
    domestic_pressure: float
    economic_exposure: float


def rung_label(rung: int) -> str:
    return LADDER[max(0, min(MAX_RUNG, rung))]


def reached_rung(escalation: float) -> int:
    """Convertit une escalade continue (0-1, ex. verdict du juge) en échelon 0-9."""
    return round(_clamp(escalation) * MAX_RUNG)


def derive_profile(country: CountryState) -> EscalationProfile:
    """Dérive le profil d'escalade de `country`, puis applique sa surcharge `mandate`."""
    mil, eco, res = country.military, country.economy, country.resources
    profile = EscalationProfile(
        escalation_threshold=_clamp(
            0.5 * mil.projection
            + (0.2 if mil.nuclear_power else 0.0)
            + (0.3 if country.rivals else 0.0)
        ),
        risk_tolerance=_clamp(0.6 * mil.projection + 0.4 * country.political_stability),
        alliance_pressure=_clamp(0.4 * len(country.alliances)),
        domestic_pressure=_clamp(1.0 - country.political_stability),
        economic_exposure=_clamp(
            (eco.trade_dependency + res.oil_dependency + (1 - res.energy_independence)) / 3
        ),
    )
    for key in _PARAM_KEYS:  # surcharge hybride via data/countries/*.json (mandate)
        raw = country.mandate.get(key)
        if raw is not None:
            try:
                setattr(profile, key, _clamp(float(raw)))
            except (TypeError, ValueError):
                pass
    return profile


def ceiling(
    profile: EscalationProfile, event: GeoEvent, world: WorldState, country: CountryState
) -> int:
    """Échelon maximum (0-9) que `country` peut atteindre face à `event` (déterministe)."""
    others = [a for a in event.actors if a != country.id]
    avg_tension = (
        sum(world.get_tension(country.id, a) for a in others) / len(others) if others else 0.0
    )
    involvement = 0.2 if country.id in event.actors else 0.0
    drive = (
        0.35 * profile.escalation_threshold
        + 0.25 * profile.risk_tolerance
        + 0.15 * profile.alliance_pressure
        + 0.15 * avg_tension
        + 0.10 * event.severity
        + involvement
    )
    brake = 0.25 * profile.domestic_pressure + 0.25 * profile.economic_exposure
    return round(_clamp(drive - brake) * MAX_RUNG)
