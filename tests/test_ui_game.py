"""Tests du contrôleur de partie GameSession (sans Streamlit)."""

import json

from core.decisions import AgentDecision
from core.events import GeoEvent
from inference.mock_backend import MockBackend
from simulation.action_space import ActionType
from ui.game import AGENT_LLM, GameSession


def test_spectator_plays_scenario_then_exhausts():
    game = GameSession()
    n_events = len(game.scenario)
    assert n_events >= 3

    played = 0
    while game.play_next_scenario() is not None:
        played += 1
    assert played == n_events
    assert game.round_no == n_events
    assert game.play_next_scenario() is None  # scénario épuisé


def test_game_master_custom_event_is_played():
    game = GameSession()
    event = GeoEvent(
        id="gm-1", round_id=1, event_type="custom", title="Blocus", actors=["usa"], severity=0.9
    )
    summary = game.play_event(event)
    assert game.round_no == 1
    assert summary.event.title == "Blocus"
    assert len(summary.decisions) == len(game.country_ids)


def test_human_override_reflected_in_round():
    game = GameSession()
    event = game.next_scenario_event
    human = AgentDecision(
        country="usa", round_id=event.round_id, action=ActionType.MOBILIZE, intensity=1.0
    )
    summary = game.play_next_scenario(human_country="usa", human_decision=human)

    usa = next(d for d in summary.decisions if d.country == "usa")
    assert usa.action == ActionType.MOBILIZE
    assert usa.intensity == 1.0
    # après le round, l'agent de base (rule-based) est restauré
    from agents.rule_based_agent import RuleBasedAgent

    assert isinstance(game.engine.agents["usa"], RuleBasedAgent)


def test_switch_to_llm_agents_keeps_world():
    game = GameSession()
    canned = json.dumps({"action": "call_for_mediation", "intensity": 0.3})
    game.set_agent_type(AGENT_LLM, backend=MockBackend(canned))
    from agents.llm_agent import LLMAgent

    assert all(isinstance(a, LLMAgent) for a in game.engine.agents.values())
    summary = game.play_next_scenario()
    assert summary is not None


def test_reset_clears_history():
    game = GameSession()
    game.play_next_scenario()
    assert game.round_no == 1
    game.reset()
    assert game.round_no == 0
    assert game.scenario_index == 0
