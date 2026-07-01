"""Tests de l'orchestrateur de round négocié + arbitré (offline, MockBackend)."""

import json
from datetime import date

from agents.game_master import GameMasterAgent
from agents.judge import JudgeAgent
from agents.llm_agent import LLMAgent
from core.country_state import CountryState, Economy, Military, Resources
from core.world_state import WorldState
from inference.mock_backend import MockBackend
from simulation.clock import SimClock
from simulation.live_round import (
    DateStep,
    EventStep,
    JudgeTokenStep,
    MessageDoneStep,
    SummaryStep,
    TurnStartStep,
    VerdictStep,
    run_negotiation_round,
)


def _world() -> WorldState:
    def c(cid, name, **kw):
        return CountryState(
            id=cid,
            name=name,
            economy=Economy(gdp=1e12, growth=2.0),
            military=Military(defense_budget=1e10),
            resources=Resources(),
            political_stability=0.5,
            **kw,
        )

    return WorldState.from_countries([c("usa", "USA"), c("iran", "Iran")])


def _agents(world) -> dict[str, LLMAgent]:
    return {cid: LLMAgent(cid, MockBackend(f"Message de {cid}.")) for cid in world.countries}


def _gm() -> GameMasterAgent:
    return GameMasterAgent(
        MockBackend(json.dumps({"title": "Sommet du Golfe", "actors": ["usa", "iran"]}))
    )


def _judge() -> JudgeAgent:
    verdict = json.dumps(
        {
            "attribute_deltas": {"iran": {"croissance": -0.5}},
            "escalation": 0.7,
            "economic_disruption": 0.3,
        }
    )
    return JudgeAgent(MockBackend(["Les USA dominent la négociation.", verdict]))


def test_step_sequence_and_passes():
    world = _world()
    clock = SimClock(current_date=date(2025, 1, 1))
    steps = list(run_negotiation_round(world, _agents(world), _gm(), _judge(), clock, max_passes=2))

    kinds = [type(s).__name__ for s in steps]
    assert kinds[0] == "DateStep" and kinds[1] == "EventStep"
    assert kinds[-1] == "SummaryStep"
    # 2 passes x 2 pays = 4 prises de parole
    assert sum(isinstance(s, TurnStartStep) for s in steps) == 4
    assert sum(isinstance(s, MessageDoneStep) for s in steps) == 4
    # le juge a raisonné puis rendu un verdict
    assert any(isinstance(s, JudgeTokenStep) for s in steps)
    assert any(isinstance(s, VerdictStep) for s in steps)


def test_turn_carries_model_tag_and_timer():
    world = _world()
    steps = list(run_negotiation_round(world, _agents(world), _gm(), _judge(), SimClock()))
    turns = [s for s in steps if isinstance(s, TurnStartStep)]
    assert all(t.model for t in turns)  # badge modèle renseigné
    assert all(s.seconds >= 0 for s in steps if isinstance(s, MessageDoneStep))


def test_judge_verdict_applied_and_bounded():
    world = _world()
    g0 = world.countries["iran"].economy.growth
    steps = list(run_negotiation_round(world, _agents(world), _gm(), _judge(), SimClock()))

    verdict_step = next(s for s in steps if isinstance(s, VerdictStep))
    assert verdict_step.escalation == 0.7
    # le juge a baissé la croissance de l'Iran (delta -0.5, sous le plafond 1.5)
    assert world.countries["iran"].economy.growth == g0 - 0.5
    assert any(d.country == "iran" and d.label == "croissance" for d in verdict_step.deltas)
    # la date a avancé
    assert next(s for s in steps if isinstance(s, DateStep)).date == "2025-07-01"
    assert next(s for s in steps if isinstance(s, EventStep)).event.title == "Sommet du Golfe"
    assert next(s for s in steps if isinstance(s, SummaryStep)).summary.round_id == 1
