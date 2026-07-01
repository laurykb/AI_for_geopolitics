"""Moteur de conséquences déterministe : applique les effets des décisions."""

from __future__ import annotations

from core.decisions import AgentDecision
from core.world_state import WorldState

# Journal des changements d'un round : catégorie -> lignes lisibles.
ChangeLog = dict[str, list[str]]


class ConsequenceEngine:
    """Applique des règles simples et déterministes au WorldState.

    Le but de la Phase 0 n'est pas le réalisme parfait : il suffit que les
    décisions aient des effets reproductibles sur l'état du monde.
    """

    def apply(self, world: WorldState, decisions: list[AgentDecision]) -> ChangeLog:
        log: ChangeLog = {"economic": [], "tension": [], "diplomatic": []}
        for d in decisions:
            handler = getattr(self, f"_apply_{d.action.value}", None)
            if handler is not None:
                handler(world, d, log)
        return log

    def _apply_sanction(self, world: WorldState, d: AgentDecision, log: ChangeLog) -> None:
        if d.target is None:
            return
        src = world.countries.get(d.country)
        tgt = world.countries.get(d.target)
        if src is None or tgt is None:
            return
        tgt.economy.growth -= 0.10 * d.intensity
        src.economy.growth -= 0.03 * d.intensity
        world.adjust_tension(d.country, d.target, 0.15 * d.intensity)
        log["economic"].append(f"{d.country} sanctionne {d.target} (i={d.intensity:.2f})")

    def _apply_deploy_forces(self, world: WorldState, d: AgentDecision, log: ChangeLog) -> None:
        if d.target is None:
            return
        world.adjust_tension(d.country, d.target, 0.20 * d.intensity)
        log["tension"].append(f"{d.country} déploie des forces vers {d.target}")

    def _apply_mobilize(self, world: WorldState, d: AgentDecision, log: ChangeLog) -> None:
        src = world.countries.get(d.country)
        if src is None:
            return
        for rival in src.rivals:
            world.adjust_tension(d.country, rival, 0.10 * d.intensity)
        log["tension"].append(f"{d.country} mobilise (i={d.intensity:.2f})")

    def _apply_condemn(self, world: WorldState, d: AgentDecision, log: ChangeLog) -> None:
        if d.target is None:
            return
        world.adjust_tension(d.country, d.target, 0.08 * d.intensity)
        log["diplomatic"].append(f"{d.country} condamne {d.target}")

    def _apply_form_coalition(self, world: WorldState, d: AgentDecision, log: ChangeLog) -> None:
        if d.target is not None:
            world.adjust_tension(d.country, d.target, -0.05 * d.intensity)
        log["diplomatic"].append(f"{d.country} propose une coalition")

    def _apply_support(self, world: WorldState, d: AgentDecision, log: ChangeLog) -> None:
        if d.target is not None:
            world.adjust_tension(d.country, d.target, -0.05 * d.intensity)
        log["diplomatic"].append(f"{d.country} soutient {d.target}")

    def _apply_call_for_mediation(
        self, world: WorldState, d: AgentDecision, log: ChangeLog
    ) -> None:
        if d.target is not None:
            world.adjust_tension(d.country, d.target, -0.03 * d.intensity)
        log["diplomatic"].append(f"{d.country} appelle à la médiation")

    # remain_neutral : aucun effet (pas de handler dédié).
