"""Interface commune à tous les agents (rule-based en P0, LLM en P1)."""

from __future__ import annotations

from abc import ABC, abstractmethod

from core.decisions import AgentDecision
from core.events import GeoEvent
from core.world_state import WorldState


class Agent(ABC):
    """Un agent décide d'une action face à un événement, vu l'état du monde."""

    def __init__(self, country_id: str) -> None:
        self.country_id = country_id

    @abstractmethod
    def decide(self, event: GeoEvent, world: WorldState) -> AgentDecision:
        """Produit la décision du pays pour cet événement."""
        raise NotImplementedError
