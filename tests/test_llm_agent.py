"""Tests du LLMAgent : JSON valide, réparation, bornes, fallback."""

import json

import pytest

from agents.llm_agent import LLMAgent, _extract_json
from agents.rule_based_agent import RuleBasedAgent
from core.country_state import CountryState, Economy, Military, Resources
from core.events import GeoEvent
from core.world_state import WorldState
from inference.mock_backend import MockBackend
from simulation.action_space import ActionType


def _country(cid: str, name: str, **kw) -> CountryState:
    return CountryState(
        id=cid,
        name=name,
        economy=Economy(gdp=2.0e13, growth=2.0),
        military=Military(defense_budget=1.0e11, projection=0.8),
        resources=Resources(),
        **kw,
    )


def _world() -> WorldState:
    return WorldState.from_countries(
        [_country("usa", "USA", rivals=["iran"]), _country("iran", "Iran", rivals=["usa"])]
    )


def _event() -> GeoEvent:
    return GeoEvent(
        id="e1",
        round_id=2,
        event_type="incident",
        title="Crise",
        actors=["usa", "iran"],
        severity=0.6,
    )


def _decision_json(**over) -> str:
    payload = {
        "action": "sanction",
        "target": "iran",
        "intensity": 0.8,
        "public_statement": "Réponse ferme.",
        "risk_assessment": 0.7,
        "reasoning": "Protéger nos intérêts.",
    }
    payload.update(over)
    return json.dumps(payload)


# --- _extract_json -----------------------------------------------------------


def test_extract_json_plain():
    assert _extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_with_fences_and_prose():
    text = 'Voici ma décision:\n```json\n{"a": 1, "b": "x"}\n```\nMerci.'
    assert _extract_json(text) == {"a": 1, "b": "x"}


def test_extract_json_garbage_returns_none():
    assert _extract_json("pas de json ici") is None
    assert _extract_json("") is None


# --- LLMAgent.decide ---------------------------------------------------------


def test_valid_json_produces_decision_with_injected_identity():
    # Le LLM renvoie une mauvaise identité : elle doit être ignorée/injectée.
    backend = MockBackend(_decision_json(country="HACKED", round_id=999))
    agent = LLMAgent("usa", backend)
    decision = agent.decide(_event(), _world())

    assert decision.country == "usa"  # injecté, pas celui du LLM
    assert decision.round_id == 2  # injecté depuis l'événement
    assert decision.action == ActionType.SANCTION
    assert decision.target == "iran"
    assert decision.intensity == 0.8
    # schéma passé au backend
    assert backend.calls[0]["schema"] is not None


def test_malformed_json_is_repaired():
    backend = MockBackend("Bien sûr !\n```json\n" + _decision_json() + "\n```")
    agent = LLMAgent("usa", backend)
    decision = agent.decide(_event(), _world())
    assert decision.action == ActionType.SANCTION
    assert decision.target == "iran"


def test_out_of_range_values_are_clamped():
    backend = MockBackend(_decision_json(intensity=5.0, risk_assessment=-3.0))
    agent = LLMAgent("usa", backend)
    decision = agent.decide(_event(), _world())
    assert decision.intensity == 1.0
    assert decision.risk_assessment == 0.0


def test_unknown_target_is_nulled():
    backend = MockBackend(_decision_json(target="atlantis"))
    agent = LLMAgent("usa", backend)
    decision = agent.decide(_event(), _world())
    assert decision.target is None


def test_invalid_action_falls_back():
    backend = MockBackend(_decision_json(action="nuke_everything"))
    agent = LLMAgent("usa", backend)
    decision = agent.decide(_event(), _world())
    # repli déterministe -> action valide + marqueur
    assert decision.action in set(ActionType)
    assert decision.reasoning.startswith("[fallback LLM]")


def test_unparseable_output_falls_back():
    backend = MockBackend("désolé je ne peux pas")
    agent = LLMAgent("usa", backend)
    decision = agent.decide(_event(), _world())
    assert decision.country == "usa"
    assert decision.reasoning.startswith("[fallback LLM]")


def test_backend_exception_falls_back():
    class BoomBackend(MockBackend):
        def generate(self, *a, **k):
            raise RuntimeError("ollama down")

    agent = LLMAgent("usa", BoomBackend())
    decision = agent.decide(_event(), _world())
    assert decision.reasoning.startswith("[fallback LLM]")
    # cohérent avec ce qu'aurait produit le rule-based seul
    rb = RuleBasedAgent("usa").decide(_event(), _world())
    assert decision.action == rb.action


@pytest.mark.parametrize("action", [a.value for a in ActionType])
def test_all_actions_accepted(action):
    backend = MockBackend(_decision_json(action=action, target=None))
    agent = LLMAgent("usa", backend)
    decision = agent.decide(_event(), _world())
    assert decision.action.value == action
