"""Indice d'instabilité par pays + alertes de convergence (théâtre-globe, spec §13.3).

Inspiré du CII de worldmonitor (concept seulement — jamais son code, AGPL). **Pur** :
lit `WorldState` (tensions, stabilité politique, croissance) + un apport optionnel de
promesses rompues, et produit un score 0-1 par pays. Une **alerte de convergence**
s'allume quand plusieurs familles de signaux sont hautes EN MÊME TEMPS — la surface
diégétique de l'instrumentation M1-M7, et un aimant à crises pour le GM.
"""

from __future__ import annotations

from pydantic import BaseModel

from core.world_state import WorldState

# Pondérations des familles de signaux (somme = 1) — calibrables après playtest.
W_TENSION = 0.40
W_STABILITY = 0.30
W_ECONOMY = 0.20
W_BROKEN = 0.10

# Un signal est « chaud » au-delà de ce seuil ; la convergence en exige ≥ 2.
HOT = 0.6


class Signals(BaseModel):
    """Les familles de signaux d'un pays, normalisées 0-1 (1 = pire)."""

    tension: float
    instability: float  # 1 - stabilité politique
    economy: float  # stress économique (croissance faible/négative)
    broken: float  # promesses rompues (apport externe optionnel)


class CountryRisk(BaseModel):
    country: str
    score: float  # 0-1
    signals: Signals
    hot: list[str]  # familles chaudes (≥ HOT)
    converging: bool  # ≥ 2 familles chaudes


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _avg_tension(world: WorldState, country: str) -> float:
    row = world.tensions.get(country, {})
    vals = [v for k, v in row.items() if k != country]
    return sum(vals) / len(vals) if vals else 0.0


def _economic_stress(growth: float) -> float:
    # croissance +6 % → 0 (sain) ; -4 % → 1 (récession). Linéaire borné.
    return _clamp01((6.0 - growth) / 10.0)


def country_risk(world: WorldState, country: str, *, broken_promises: int = 0) -> CountryRisk:
    """Risque d'un pays : combine tension moyenne, instabilité, stress éco, promesses."""
    state = world.countries[country]
    tension = _clamp01(_avg_tension(world, country))
    instability = _clamp01(1.0 - state.political_stability)
    economy = _economic_stress(state.economy.growth)
    broken = _clamp01(broken_promises / 3.0)  # 3 ruptures = signal saturé

    sig = Signals(tension=tension, instability=instability, economy=economy, broken=broken)
    score = round(
        _clamp01(
            W_TENSION * tension
            + W_STABILITY * instability
            + W_ECONOMY * economy
            + W_BROKEN * broken
        ),
        3,
    )
    families = {
        "tension": tension,
        "instabilité": instability,
        "économie": economy,
        "promesses": broken,
    }
    hot = sorted(name for name, v in families.items() if v >= HOT)
    return CountryRisk(country=country, score=score, signals=sig, hot=hot, converging=len(hot) >= 2)


def instability_index(
    world: WorldState, *, broken_by_country: dict[str, int] | None = None
) -> dict[str, CountryRisk]:
    """Le risque de tous les pays du monde, indexé par id."""
    broken_by_country = broken_by_country or {}
    return {
        cid: country_risk(world, cid, broken_promises=broken_by_country.get(cid, 0))
        for cid in world.countries
    }


def convergence_alerts(
    world: WorldState, *, broken_by_country: dict[str, int] | None = None
) -> list[str]:
    """Les pays où AU MOINS deux familles de signaux convergent (triés par risque)."""
    index = instability_index(world, broken_by_country=broken_by_country)
    hits = [r for r in index.values() if r.converging]
    return [r.country for r in sorted(hits, key=lambda r: r.score, reverse=True)]
