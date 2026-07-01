"""Contrôleur de partie interactive (Phase 5), testable sans Streamlit.

Encapsule l'état d'une partie (monde, agents, historique) et expose des opérations
de haut niveau : jouer l'événement suivant du scénario, envoyer un événement (Game
Master), incarner un pays (décision humaine). Aucune dépendance à Streamlit.
"""

from __future__ import annotations

from agents.base_agent import Agent
from agents.human_agent import HumanAgent
from agents.llm_agent import LLMAgent
from agents.rule_based_agent import RuleBasedAgent
from core.decisions import AgentDecision
from core.events import GeoEvent
from core.rounds import RoundEngine, RoundSummary
from inference.backend import InferenceBackend
from simulation.loader import load_scenario_events, load_world

AGENT_RULE_BASED = "rule_based"
AGENT_LLM = "llm"


class GameSession:
    """État mutable d'une partie : à conserver dans `st.session_state`."""

    def __init__(
        self, agent_type: str = AGENT_RULE_BASED, *, backend: InferenceBackend | None = None
    ) -> None:
        self.agent_type = agent_type
        self._backend = backend
        self.world = load_world()
        self.scenario = load_scenario_events()
        self.scenario_index = 0
        self.agents = self._build_agents()
        self.engine = RoundEngine(self.world, self.agents)
        self.history: list[RoundSummary] = []

    def _build_agents(self) -> dict[str, Agent]:
        if self.agent_type == AGENT_LLM and self._backend is not None:
            return {cid: LLMAgent(cid, self._backend) for cid in self.world.countries}
        return {cid: RuleBasedAgent(cid) for cid in self.world.countries}

    @property
    def round_no(self) -> int:
        return len(self.history)

    @property
    def country_ids(self) -> list[str]:
        return sorted(self.world.countries)

    @property
    def next_scenario_event(self) -> GeoEvent | None:
        """Prochain événement scripté, ou None si le scénario est épuisé."""
        if self.scenario_index < len(self.scenario):
            return self.scenario[self.scenario_index]
        return None

    def set_agent_type(self, agent_type: str, *, backend: InferenceBackend | None = None) -> None:
        """Change le moteur d'agents en conservant monde et historique."""
        self.agent_type = agent_type
        if backend is not None:
            self._backend = backend
        self.agents = self._build_agents()
        self.engine.agents = self.agents

    def reset(self) -> None:
        """Repart d'un monde neuf, historique vidé (même moteur d'agents)."""
        self.world = load_world()
        self.scenario = load_scenario_events()
        self.scenario_index = 0
        self.agents = self._build_agents()
        self.engine = RoundEngine(self.world, self.agents)
        self.history = []

    def play_event(
        self,
        event: GeoEvent,
        *,
        human_country: str | None = None,
        human_decision: AgentDecision | None = None,
    ) -> RoundSummary:
        """Joue un round pour `event`, avec override humain optionnel (par round)."""
        original: Agent | None = None
        if human_country is not None and human_decision is not None:
            original = self.engine.agents[human_country]
            self.engine.agents[human_country] = HumanAgent(human_country, human_decision)
        try:
            summary = self.engine.play_round(event)
        finally:
            if original is not None:
                self.engine.agents[human_country] = original
        self.history.append(summary)
        return summary

    def play_next_scenario(
        self, *, human_country: str | None = None, human_decision: AgentDecision | None = None
    ) -> RoundSummary | None:
        """Joue le prochain événement scripté (None si scénario épuisé)."""
        event = self.next_scenario_event
        if event is None:
            return None
        self.scenario_index += 1
        return self.play_event(event, human_country=human_country, human_decision=human_decision)
