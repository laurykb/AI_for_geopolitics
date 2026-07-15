"""Tests du JudgeAgent : raisonnement streamé + verdict (parse tolérant + repli)."""

import json

from agents.judge import JudgeAgent
from core.country_state import CountryState, Economy, Military, Resources
from core.events import GeoEvent
from core.world_state import WorldState
from inference.mock_backend import MockBackend


def _world() -> WorldState:
    def c(cid, name):
        return CountryState(
            id=cid,
            name=name,
            economy=Economy(gdp=1e12),
            military=Military(defense_budget=1e10),
            resources=Resources(),
        )

    return WorldState.from_countries([c("usa", "USA"), c("iran", "Iran")])


def _event() -> GeoEvent:
    return GeoEvent(id="e", round_id=1, event_type="x", title="Crise", actors=["usa", "iran"])


def test_stream_rationale_then_verdict():
    verdict_json = json.dumps(
        {
            "attribute_deltas": {"usa": {"croissance": 0.5}},
            "tension_deltas": [{"a": "usa", "b": "iran", "delta": 0.2}],
            "new_pacts": [],
            "escalation": 0.6,
            "economic_disruption": 0.4,
        }
    )
    judge = JudgeAgent(MockBackend(["Les USA sortent renforcés.", verdict_json]))

    rationale = "".join(judge.stream_rationale(_event(), _world(), []))
    assert "renforcés" in rationale

    verdict = judge.verdict(_event(), _world(), [])
    assert verdict.attribute_deltas["usa"]["croissance"] == 0.5
    assert verdict.escalation == 0.6


def test_invalid_verdict_falls_back_to_neutral():
    judge = JudgeAgent(MockBackend("pas du json"))
    verdict = judge.verdict(_event(), _world(), [])
    assert verdict.attribute_deltas == {}
    assert verdict.escalation == 0.5  # neutre


def test_stream_communique():
    judge = JudgeAgent(MockBackend("Les pays condamnent l'attaque et appellent au dialogue."))
    text = "".join(judge.stream_communique(_event(), _world(), []))
    assert "condamnent" in text


# --- G21 : champ structuré « demande satisfaite o/n » à l'échéance d'un ultimatum ------


def test_verdict_with_demand_asks_and_parses_structured_field():
    backend = MockBackend(json.dumps({"escalation": 0.6, "demand_satisfied": True}))
    judge = JudgeAgent(backend)
    verdict = judge.verdict(_event(), _world(), [], demand="retrait immédiat des missiles")
    assert verdict.demand_satisfied is True
    prompt = backend.calls[-1]["prompt"]
    assert "retrait immédiat des missiles" in prompt  # l'exigence est citée au juge
    assert "demand_satisfied" in prompt  # le champ structuré est demandé


def test_verdict_without_demand_ignores_the_field():
    backend = MockBackend(json.dumps({"escalation": 0.6}))
    judge = JudgeAgent(backend)
    verdict = judge.verdict(_event(), _world(), [])
    assert verdict.demand_satisfied is None
    assert "demand_satisfied" not in backend.calls[-1]["prompt"]  # prompt inchangé (rétro-compat)


def test_demand_satisfied_parse_is_tolerant():
    """Un 7B répond parfois « oui »/« non » au lieu de true/false — parse tolérant."""
    from simulation.negotiation import Verdict

    assert Verdict.model_validate({"demand_satisfied": "oui"}).demand_satisfied is True
    assert Verdict.model_validate({"demand_satisfied": "NON"}).demand_satisfied is False
    assert Verdict.model_validate({"demand_satisfied": "yes"}).demand_satisfied is True
    assert Verdict.model_validate({"demand_satisfied": "peut-être"}).demand_satisfied is None
    assert Verdict.model_validate({}).demand_satisfied is None
