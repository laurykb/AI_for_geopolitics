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
