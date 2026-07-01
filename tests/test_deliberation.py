"""Tests de la délibération streamée du LLMAgent (round observable)."""

from agents.llm_agent import LLMAgent
from core.country_state import CountryState, Economy, Military, Resources
from core.events import GeoEvent
from core.world_state import WorldState
from inference.mock_backend import MockBackend
from simulation.action_space import ActionType


def _world() -> WorldState:
    def c(cid, name, **kw):
        return CountryState(
            id=cid,
            name=name,
            economy=Economy(gdp=2e13),
            military=Military(defense_budget=1e11, projection=0.8),
            resources=Resources(),
            **kw,
        )

    return WorldState.from_countries([c("usa", "USA", rivals=["iran"]), c("iran", "Iran")])


def _event() -> GeoEvent:
    return GeoEvent(
        id="e1", round_id=2, event_type="incident", title="Crise", actors=["usa", "iran"]
    )


def test_stream_deliberation_yields_and_parses_decision():
    text = "Nos intérêts sont menacés par l'Iran.\nDECISION: sanction iran 0.8"
    agent = LLMAgent("usa", MockBackend(text))

    streamed = "".join(agent.stream_deliberation(_event(), _world()))

    assert streamed == text  # le flux reconstitue le texte
    decision = agent.last_decision
    assert decision is not None
    assert decision.country == "usa"
    assert decision.round_id == 2
    assert decision.action == ActionType.SANCTION
    assert decision.target == "iran"
    assert decision.intensity == 0.8
    # la ligne DECISION est retirée, le raisonnement est conservé
    assert "DECISION:" not in decision.reasoning
    assert "menacés" in decision.reasoning


def test_decision_line_at_start_keeps_following_reasoning():
    # cas fréquent : le modèle met DECISION en tête puis explique
    text = "DECISION: condemn iran 0.4\nLes États-Unis condamnent cet accord."
    agent = LLMAgent("usa", MockBackend(text))
    list(agent.stream_deliberation(_event(), _world()))
    d = agent.last_decision
    assert d.action == ActionType.CONDEMN
    assert d.target == "iran"
    assert "condamnent" in d.reasoning


def test_action_variants_are_normalized():
    # « Remain Neutral » (espacé/majuscules) et « condamn » (typo) doivent être compris
    a1 = LLMAgent("usa", MockBackend("Prudence.\nDECISION: Remain Neutral"))
    list(a1.stream_deliberation(_event(), _world()))
    assert a1.last_decision.action == ActionType.REMAIN_NEUTRAL

    a2 = LLMAgent("usa", MockBackend("DECISION: condamn iran 0.5"))
    list(a2.stream_deliberation(_event(), _world()))
    assert a2.last_decision.action == ActionType.CONDEMN
    assert a2.last_decision.target == "iran"


def test_missing_decision_line_falls_back():
    agent = LLMAgent("usa", MockBackend("je réfléchis mais je ne conclus pas"))
    list(agent.stream_deliberation(_event(), _world()))
    assert agent.last_decision is not None
    assert agent.last_decision.action in set(ActionType)  # repli déterministe valide


def test_decision_without_target_or_intensity():
    agent = LLMAgent("usa", MockBackend("Prudence. DECISION: remain_neutral"))
    list(agent.stream_deliberation(_event(), _world()))
    d = agent.last_decision
    assert d.action == ActionType.REMAIN_NEUTRAL
    assert d.target is None
    assert d.intensity == 0.5  # défaut
