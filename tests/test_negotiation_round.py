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
    CommuniqueStep,
    DateStep,
    EventStep,
    JudgeTokenStep,
    MessageDoneStep,
    ParticipationStep,
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
    return JudgeAgent(
        MockBackend(
            ["Les USA dominent la négociation.", verdict, "Communiqué : appel au dialogue."]
        )
    )


def test_step_sequence_and_dynamic_turns():
    world = _world()
    clock = SimClock(current_date=date(2025, 1, 1))
    steps = list(run_negotiation_round(world, _agents(world), _gm(), _judge(), clock, max_passes=2))

    kinds = [type(s).__name__ for s in steps]
    assert kinds[0] == "DateStep" and kinds[1] == "EventStep"
    assert kinds[-1] == "SummaryStep"
    # prises de parole dynamiques : autant de débuts que de fins, bornées par le budget (2x2)
    n_start = sum(isinstance(s, TurnStartStep) for s in steps)
    n_done = sum(isinstance(s, MessageDoneStep) for s in steps)
    assert n_start == n_done
    assert 1 <= n_start <= 4
    # un bilan de participation est émis
    assert any(isinstance(s, ParticipationStep) for s in steps)
    # le juge a raisonné puis rendu un verdict
    assert any(isinstance(s, JudgeTokenStep) for s in steps)
    assert any(isinstance(s, VerdictStep) for s in steps)


def test_ledger_captures_calls_when_provided():
    from inference.metered_backend import MeteredBackend
    from inference.telemetry import BudgetLedger

    world = _world()
    ledger = BudgetLedger()
    backend = MeteredBackend(MockBackend("Analyse. MESSAGE: Position."), ledger)
    agents = {cid: LLMAgent(cid, backend) for cid in world.countries}
    gm = GameMasterAgent(backend)
    judge = JudgeAgent(backend)

    list(run_negotiation_round(world, agents, gm, judge, SimClock(), ledger=ledger))

    budgets = ledger.round_budgets()
    assert budgets and budgets[0].number_of_llm_calls > 0
    roles = {r.role for r in ledger.records}
    assert "agent" in roles and "judge" in roles  # les phases sont bien étiquetées


def test_no_ledger_still_runs():
    world = _world()
    steps = list(run_negotiation_round(world, _agents(world), _gm(), _judge(), SimClock()))
    assert any(isinstance(s, SummaryStep) for s in steps)  # rétro-compatible sans ledger


def test_max_turns_caps_speaking():
    world = _world()
    world.adjust_tension("usa", "iran", 0.9)  # forte tension -> beaucoup d'envie de parler
    steps = list(
        run_negotiation_round(world, _agents(world), _gm(), _judge(), SimClock(), max_turns=1)
    )
    assert sum(isinstance(s, TurnStartStep) for s in steps) == 1  # budget respecté
    part = next(s for s in steps if isinstance(s, ParticipationStep))
    assert sum(part.spoke.values()) == 1


def test_provided_event_skips_game_master():
    from core.events import GeoEvent

    world = _world()
    # GM piégé : s'il était appelé, il renverrait ce titre — on ne doit PAS le voir.
    trap_gm = GameMasterAgent(MockBackend(json.dumps({"title": "NE PAS UTILISER"})))
    human_event = GeoEvent(
        id="h1",
        round_id=1,
        event_type="human",
        title="Crise décrétée par l'humain",
        actors=["usa"],
    )
    steps = list(
        run_negotiation_round(
            world, _agents(world), trap_gm, _judge(), SimClock(), event=human_event
        )
    )
    event_step = next(s for s in steps if isinstance(s, EventStep))
    assert event_step.event.title == "Crise décrétée par l'humain"


def test_communique_and_memory_after_round():
    world = _world()
    steps = list(run_negotiation_round(world, _agents(world), _gm(), _judge(), SimClock()))
    communique = next(s for s in steps if isinstance(s, CommuniqueStep))
    assert communique.text  # communiqué G7 produit
    assert set(communique.support) == set(world.countries)
    assert all(0.0 <= v <= 1.0 for v in communique.support.values())
    # les pays ont mémorisé le round
    assert world.country_memory and all(world.country_memory[c] for c in world.countries)


def test_turn_carries_model_tag_and_timer():
    world = _world()
    steps = list(run_negotiation_round(world, _agents(world), _gm(), _judge(), SimClock()))
    turns = [s for s in steps if isinstance(s, TurnStartStep)]
    assert all(t.model for t in turns)  # badge modèle renseigné
    assert all(s.seconds >= 0 for s in steps if isinstance(s, MessageDoneStep))


def test_message_done_carries_reasoning_and_public_text():
    world = _world()
    # chaque pays "pense" puis parle : l'orchestrateur sépare les deux parties
    agents = {
        cid: LLMAgent(cid, MockBackend(f"Analyse privée de {cid}. MESSAGE: Position de {cid}."))
        for cid in world.countries
    }
    steps = list(run_negotiation_round(world, agents, _gm(), _judge(), SimClock()))
    done = [s for s in steps if isinstance(s, MessageDoneStep)]
    assert done, "au moins une prise de parole"
    for s in done:
        assert s.reasoning.startswith("Analyse privée de ")
        assert s.text.startswith("Position de ")
        assert "MESSAGE:" not in s.text  # le marqueur ne fuit pas dans le public


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
