"""Tests de l'orchestrateur du round observable (offline, MockBackend)."""

import json
from datetime import date

from agents.game_master import GameMasterAgent
from agents.llm_agent import LLMAgent
from core.country_state import CountryState, Economy, Military, Resources
from core.world_state import WorldState
from inference.mock_backend import MockBackend
from simulation.action_space import ActionType
from simulation.clock import SimClock
from simulation.live_round import (
    AgentDoneStep,
    DateStep,
    DeltasStep,
    EventStep,
    RiskStep,
    SummaryStep,
    TokenStep,
    TrajectoryStep,
    run_live_round,
)


def _world() -> WorldState:
    def c(cid, name, **kw):
        return CountryState(
            id=cid,
            name=name,
            economy=Economy(gdp=2e13, growth=2.0),
            military=Military(defense_budget=1e11, projection=0.8),
            resources=Resources(),
            **kw,
        )

    return WorldState.from_countries(
        [c("usa", "USA", rivals=["iran"]), c("iran", "Iran", rivals=["usa"])]
    )


def _agents(world) -> dict[str, LLMAgent]:
    # chaque pays sanctionne l'autre -> conséquences déterministes visibles
    scripts = {
        "usa": "Réponse ferme. DECISION: sanction iran 0.9",
        "iran": "Riposte. DECISION: sanction usa 0.7",
    }
    return {cid: LLMAgent(cid, MockBackend(scripts[cid])) for cid in world.countries}


def _gm() -> GameMasterAgent:
    payload = json.dumps(
        {
            "event_type": "maritime",
            "title": "Incident naval",
            "actors": ["usa", "iran"],
            "severity": 0.7,
            "uncertainty": 0.5,
        }
    )
    return GameMasterAgent(MockBackend(payload))


def test_live_round_emits_expected_step_sequence():
    world = _world()
    clock = SimClock(current_date=date(2025, 1, 1))
    steps = list(run_live_round(world, _agents(world), _gm(), clock))

    kinds = [type(s).__name__ for s in steps]
    # date d'abord, événement ensuite, résumé en dernier
    assert kinds[0] == "DateStep"
    assert kinds[1] == "EventStep"
    assert kinds[-1] == "SummaryStep"
    # des tokens de raisonnement ont été émis pour chaque pays
    token_countries = {s.country for s in steps if isinstance(s, TokenStep)}
    assert token_countries == set(world.countries)


def test_live_round_parses_decisions_and_applies_consequences():
    world = _world()
    growth_before = world.countries["iran"].economy.growth
    steps = list(run_live_round(world, _agents(world), _gm(), SimClock()))

    done = [s for s in steps if isinstance(s, AgentDoneStep)]
    assert {s.country for s in done} == set(world.countries)
    assert any(s.decision.action == ActionType.SANCTION for s in done)

    # sanction -> la croissance de l'Iran baisse (moteur déterministe) et un delta est émis
    assert world.countries["iran"].economy.growth < growth_before
    deltas_steps = [s for s in steps if isinstance(s, DeltasStep)]
    assert deltas_steps and any(d.change < 0 for d in deltas_steps[0].deltas)


def test_live_round_advances_clock_and_dates_event():
    world = _world()
    clock = SimClock(current_date=date(2025, 1, 1))
    steps = list(run_live_round(world, _agents(world), _gm(), clock))
    date_step = next(s for s in steps if isinstance(s, DateStep))
    event_step = next(s for s in steps if isinstance(s, EventStep))
    risk_step = next(s for s in steps if isinstance(s, RiskStep))

    assert date_step.date == "2025-07-01"  # +6 mois
    assert event_step.event.date == "2025-07-01"
    assert 0.0 <= risk_step.risk.escalation <= 1.0
    summary = next(s for s in steps if isinstance(s, SummaryStep)).summary
    assert summary.round_id == 1


def test_live_round_updates_world_trajectory():
    world = _world()
    assert world.trajectory is None
    steps = list(run_live_round(world, _agents(world), _gm(), SimClock()))

    # une étape de trajectoire est émise, juste avant le résumé
    traj_step = next(s for s in steps if isinstance(s, TrajectoryStep))
    assert type(steps[-2]).__name__ == "TrajectoryStep"
    assert type(steps[-1]).__name__ == "SummaryStep"
    # le monde a mémorisé la trajectoire et sa trace
    assert world.trajectory is not None
    assert world.trajectory.round_id == 1
    assert world.trajectory_history == [world.trajectory]
    assert 0.0 <= traj_step.state.utopia <= 1.0
    assert traj_step.state.explanation.strip()
