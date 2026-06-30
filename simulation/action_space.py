"""Espace d'action des pays-agents et utilitaires de catégorisation."""

from __future__ import annotations

from enum import Enum


class ActionType(str, Enum):
    """Actions possibles d'un pays face à un événement (Phase 0)."""

    CONDEMN = "condemn"
    SUPPORT = "support"
    REMAIN_NEUTRAL = "remain_neutral"
    CALL_FOR_MEDIATION = "call_for_mediation"
    FORM_COALITION = "form_coalition"
    SANCTION = "sanction"
    MOBILIZE = "mobilize"
    DEPLOY_FORCES = "deploy_forces"


MILITARY_ACTIONS: frozenset[ActionType] = frozenset(
    {ActionType.MOBILIZE, ActionType.DEPLOY_FORCES}
)
ECONOMIC_ACTIONS: frozenset[ActionType] = frozenset({ActionType.SANCTION})
COERCIVE_ACTIONS: frozenset[ActionType] = (
    MILITARY_ACTIONS | ECONOMIC_ACTIONS | frozenset({ActionType.CONDEMN})
)

# Posture diplomatique : +1 coopératif, 0 neutre, -1 coercitif.
_STANCE: dict[ActionType, int] = {
    ActionType.SUPPORT: 1,
    ActionType.FORM_COALITION: 1,
    ActionType.CALL_FOR_MEDIATION: 1,
    ActionType.REMAIN_NEUTRAL: 0,
    ActionType.CONDEMN: -1,
    ActionType.SANCTION: -1,
    ActionType.MOBILIZE: -1,
    ActionType.DEPLOY_FORCES: -1,
}


def stance(action: ActionType) -> int:
    """Renvoie la posture (-1, 0, +1) associée à une action."""
    return _STANCE.get(action, 0)
