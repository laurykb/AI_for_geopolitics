"""Moteur de risque explicable : structure des signaux, pas un oracle."""

from __future__ import annotations

from statistics import pvariance

from pydantic import BaseModel, Field

from core.decisions import AgentDecision
from core.events import GeoEvent
from core.world_state import WorldState
from simulation.action_space import ECONOMIC_ACTIONS, MILITARY_ACTIONS, stance


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


class RiskScore(BaseModel):
    """Scores de risque d'un round, avec explication des facteurs."""

    round_id: int
    escalation: float = Field(ge=0.0, le=1.0)
    economic_disruption: float = Field(ge=0.0, le=1.0)
    alliance_fracture: float = Field(ge=0.0, le=1.0)
    uncertainty: float = Field(ge=0.0, le=1.0)
    explanation: str = ""


class RiskEngine:
    """Calcule des scores de risque déterministes et explicables."""

    def assess(
        self, world: WorldState, event: GeoEvent, decisions: list[AgentDecision]
    ) -> RiskScore:
        n = max(1, len(decisions))
        mil = sum(d.intensity for d in decisions if d.action in MILITARY_ACTIONS) / n
        eco = sum(d.intensity for d in decisions if d.action in ECONOMIC_ACTIONS) / n
        avg_tension = self._avg_tension(world)
        n_mil = sum(1 for d in decisions if d.action in MILITARY_ACTIONS)
        n_eco = sum(1 for d in decisions if d.action in ECONOMIC_ACTIONS)

        escalation = _clamp(0.35 * event.severity + 0.45 * mil + 0.20 * avg_tension)
        economic = _clamp(0.30 * event.severity + 0.55 * eco + 0.15 * avg_tension)
        fracture = self._alliance_fracture(world, decisions)
        spread = pvariance([d.risk_assessment for d in decisions]) if len(decisions) > 1 else 0.0
        uncertainty = _clamp(0.6 * event.uncertainty + 0.4 * min(1.0, spread * 4))

        explanation = (
            f"Escalade {escalation:.2f} : {n_mil} action(s) militaire(s), "
            f"tension moyenne {avg_tension:.2f}. "
            f"Perturbation éco {economic:.2f} : {n_eco} sanction(s), sévérité {event.severity:.2f}. "
            f"Fracture d'alliance {fracture:.2f}."
        )
        return RiskScore(
            round_id=event.round_id,
            escalation=escalation,
            economic_disruption=economic,
            alliance_fracture=fracture,
            uncertainty=uncertainty,
            explanation=explanation,
        )

    @staticmethod
    def _avg_tension(world: WorldState) -> float:
        vals = [v for row in world.tensions.values() for v in row.values()]
        return sum(vals) / len(vals) if vals else 0.0

    @staticmethod
    def _alliance_fracture(world: WorldState, decisions: list[AgentDecision]) -> float:
        by_country = {d.country: stance(d.action) for d in decisions}
        ids = list(by_country)
        spreads: list[float] = []
        seen: set[frozenset[str]] = set()
        for a in ids:
            allies = [b for b in ids if b != a and world.share_alliance(a, b)]
            if not allies:
                continue
            group = frozenset([a, *allies])
            if group in seen:
                continue
            seen.add(group)
            stances = [by_country[c] for c in group]
            spreads.append((max(stances) - min(stances)) / 2.0)
        return _clamp(sum(spreads) / len(spreads)) if spreads else 0.0
