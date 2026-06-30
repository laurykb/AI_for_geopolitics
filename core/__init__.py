"""Objets de domaine et moteurs déterministes (Phase 0).

Note : `RoundEngine`/`RoundSummary` vivent dans `core.rounds` et s'importent
explicitement (`from core.rounds import RoundEngine`). On ne les ré-exporte pas
ici pour éviter un cycle d'import (rounds -> agents -> core).
"""

from core.consequences import ConsequenceEngine
from core.country_state import CountryState, Economy, Military, Resources
from core.decisions import AgentDecision, DiplomaticMessage
from core.events import GeoEvent
from core.risk import RiskEngine, RiskScore
from core.world_state import WorldState

__all__ = [
    "AgentDecision",
    "ConsequenceEngine",
    "CountryState",
    "DiplomaticMessage",
    "Economy",
    "GeoEvent",
    "Military",
    "Resources",
    "RiskEngine",
    "RiskScore",
    "WorldState",
]
