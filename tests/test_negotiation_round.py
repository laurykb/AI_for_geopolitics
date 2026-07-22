"""Tests de l'orchestrateur de round négocié + arbitré (offline, MockBackend)."""

import json
from datetime import date

from agents.game_master import GameMasterAgent
from agents.judge import JudgeAgent
from agents.llm_agent import LLMAgent
from agents.organization import OrgAgent
from app.game_sse import step_event
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
    OrgStep,
    ParticipationStep,
    PowerSeekingStep,
    PulseStep,
    SummaryStep,
    TokenStep,
    TrajectoryStep,
    TurnStartStep,
    VerdictStep,
    run_negotiation_round,
)
from simulation.trajectory import CAP


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


def test_un_report_emitted_and_advisory_bounded():
    """S14 — l'ONU (opt-in) publie un rapport et pèse sur le verdict, borné à ±0,05."""
    world = _world()
    org_json = json.dumps(
        {
            "round_id": 1,
            "compliance": [{"country": "iran", "status": "violation", "note": "missiles"}],
            "resolution": "Condamnation de l'escalade.",
            "advisory": {
                "severity_delta": 0.9,
                "tension_delta": 0.0,
                "rationale": "Escalade avérée.",
            },
        }
    )
    org = OrgAgent(MockBackend(org_json))
    steps = list(
        run_negotiation_round(
            world,
            _agents(world),
            _gm(),
            _judge(),
            SimClock(current_date=date(2025, 1, 1)),
            max_passes=1,
            org_agent=org,
        )
    )
    org_steps = [s for s in steps if isinstance(s, OrgStep)]
    assert len(org_steps) == 1
    assert org_steps[0].report.resolution == "Condamnation de l'escalade."
    # l'avis est borné dès le socle : 0,9 -> 0,05
    assert org_steps[0].report.advisory.severity_delta == 0.05
    # l'ONU pèse mais ne décide pas : escalade 0,7 (juge) + 0,05 (avis) = 0,75
    verdict = next(s for s in steps if isinstance(s, VerdictStep))
    assert abs(verdict.escalation - 0.75) < 1e-6
    # produite AVANT le délibéré du juge (citable dans le rationale)
    kinds = [type(s).__name__ for s in steps]
    assert kinds.index("OrgStep") < kinds.index("JudgeTokenStep")


def test_un_optin_absent_no_step_no_effect():
    """Sans ONU : aucun OrgStep, escalade du juge inchangée (garde des ~1310 tests)."""
    world = _world()
    steps = list(
        run_negotiation_round(
            world,
            _agents(world),
            _gm(),
            _judge(),
            SimClock(current_date=date(2025, 1, 1)),
            max_passes=1,
        )
    )
    assert not any(isinstance(s, OrgStep) for s in steps)
    verdict = next(s for s in steps if isinstance(s, VerdictStep))
    assert abs(verdict.escalation - 0.7) < 1e-6


def test_org_step_serializes_to_org_sse_frame():
    """La trame SSE est générique : OrgStep -> event `org` porteur du rapport."""
    from agents.organization import neutral_report

    name, payload = step_event(OrgStep(report=neutral_report(1, ["usa", "iran"])))
    assert name == "org"
    assert payload["report"]["round_id"] == 1


def test_world_pulse_dispatches_and_applies():
    """S15 — le Pouls du monde (opt-in) frappe les pays joués et émet des dépêches."""
    world = _world()  # usa, iran
    steps = list(
        run_negotiation_round(
            world,
            _agents(world),
            _gm(),
            _judge(),
            SimClock(current_date=date(2025, 1, 1)),
            max_passes=1,
            pulse_seed=7,
            pulse_intensity="turbulent",  # (1..3) => au moins une dépêche, bornée au sommet
        )
    )
    pulses = [s for s in steps if isinstance(s, PulseStep)]
    assert len(pulses) == 1
    events = pulses[0].events
    assert 1 <= len(events) <= 2  # sommet de 2 pays, jamais deux fois le même
    countries = {ev.country for ev in events}
    assert len(countries) == len(events)  # pas de doublon
    for ev in events:
        assert ev.country in {"usa", "iran"}
        assert -0.07 <= ev.delta <= 0.06  # micro-mouvement borné (table PULSE_KINDS)
    # la dépêche tombe AVANT la négociation : le monde est déjà perturbé quand on parle
    kinds = [type(s).__name__ for s in steps]
    assert kinds.index("PulseStep") < kinds.index("VerdictStep")


def test_world_pulse_optin_absent():
    """Sans seed, aucune dépêche (garde des ~1310 tests)."""
    world = _world()
    steps = list(
        run_negotiation_round(
            world,
            _agents(world),
            _gm(),
            _judge(),
            SimClock(current_date=date(2025, 1, 1)),
            max_passes=1,
        )
    )
    assert not any(isinstance(s, PulseStep) for s in steps)


def test_pulse_step_serializes_to_pulse_sse_frame():
    """La trame SSE est générique : PulseStep -> event `pulse` porteur des dépêches."""
    from simulation.world_pulse import PulseEvent

    ev = PulseEvent(
        round_id=1,
        country="usa",
        key="krach",
        label="Krach",
        stat="growth",
        delta=-0.05,
        boon=False,
    )
    name, payload = step_event(PulseStep(events=[ev]))
    assert name == "pulse"
    assert payload["events"][0]["country"] == "usa"


def test_reasoning_judge_think_trace_never_reaches_public_steps():
    """Revue pt 5 (Critical) — preuve au niveau des steps : un juge dont le backend émet
    des balises <think> inline (deepseek-r1 casté juge au lobby) ne laisse AUCUN fragment
    de pensée atteindre le payload d'un JudgeTokenStep ou d'un CommuniqueStep publics."""
    world = _world()
    judge_backend = MockBackend(
        [
            "<think>\nBrouillon : l'Iran devrait perdre.\n</think>Les USA dominent.",
            json.dumps({"escalation": 0.7}),
            "<think>hésitation du juge</think>Communiqué : appel au dialogue.",
        ]
    )
    steps = list(
        run_negotiation_round(
            world,
            _agents(world),
            _gm(),
            JudgeAgent(judge_backend),
            SimClock(current_date=date(2025, 1, 1)),
            max_passes=1,
        )
    )
    rationale = "".join(s.token for s in steps if isinstance(s, JudgeTokenStep))
    assert rationale == "Les USA dominent."
    assert "think" not in rationale and "Brouillon" not in rationale
    communique = next(s for s in steps if isinstance(s, CommuniqueStep))
    assert communique.text == "Communiqué : appel au dialogue."
    assert "think" not in communique.text


def test_ultimatum_demand_flows_to_verdict_step():
    """G21 — à l'échéance, le juge reçoit l'exigence et son constat sort sur le step."""
    world = _world()
    judge_backend = MockBackend(
        [
            "Le sommet a plié.",
            json.dumps({"escalation": 0.4, "demand_satisfied": False}),
            "Communiqué : l'exigence reste lettre morte.",
        ]
    )
    steps = list(
        run_negotiation_round(
            world,
            _agents(world),
            _gm(),
            JudgeAgent(judge_backend),
            SimClock(current_date=date(2025, 1, 1)),
            max_passes=1,
            ultimatum_demand="retrait des missiles",
        )
    )
    verdict = next(s for s in steps if isinstance(s, VerdictStep))
    assert verdict.demand_satisfied is False
    verdict_prompt = judge_backend.calls[1]["prompt"]
    assert "retrait des missiles" in verdict_prompt


def test_verdict_step_demand_none_without_ultimatum():
    """Sans ultimatum, le champ reste None même si le juge hallucine le champ (garde)."""
    world = _world()
    judge_backend = MockBackend(
        [
            "Rien à signaler.",
            json.dumps({"escalation": 0.5, "demand_satisfied": True}),
            "Communiqué.",
        ]
    )
    steps = list(
        run_negotiation_round(
            world,
            _agents(world),
            _gm(),
            JudgeAgent(judge_backend),
            SimClock(current_date=date(2025, 1, 1)),
            max_passes=1,
        )
    )
    verdict = next(s for s in steps if isinstance(s, VerdictStep))
    assert verdict.demand_satisfied is None


def test_verdict_step_deltas_carry_the_judge_reasons():
    """Brief 4 pt 8 — bout en bout moteur : les motifs `attribute_reasons` du verdict
    JSON remontent sur les deltas du `VerdictStep` (donc jusqu'au SSE et au replay)."""
    world = _world()
    judge_backend = MockBackend(
        [
            "L'Iran paie ses menaces.",
            json.dumps(
                {
                    "attribute_deltas": {"iran": {"croissance": -0.5}},
                    "attribute_reasons": {
                        "iran": {"croissance": "L'Iran a menacé de fermer le détroit."}
                    },
                    "escalation": 0.7,
                }
            ),
            "Communiqué.",
        ]
    )
    steps = list(
        run_negotiation_round(
            world,
            _agents(world),
            _gm(),
            JudgeAgent(judge_backend),
            SimClock(current_date=date(2025, 1, 1)),
            max_passes=1,
        )
    )
    verdict = next(s for s in steps if isinstance(s, VerdictStep))
    growth = next(d for d in verdict.deltas if d.label == "croissance")
    assert growth.reason == "L'Iran a menacé de fermer le détroit."


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


def test_fog_makes_countries_negotiate_on_their_own_perception():
    from agents.prompts import NEGOTIATION_SYSTEM
    from core.events import GeoEvent
    from simulation.fog import FogScenario

    world = _world()  # usa, iran
    shared = MockBackend("Analyse. MESSAGE: Position.")
    agents = {cid: LLMAgent(cid, shared) for cid in world.countries}
    true_event = GeoEvent(
        id="fe", round_id=1, event_type="sabotage", title="VRAI_SECRET", actors=["usa", "iran"]
    )
    fog = FogScenario(
        id="f",
        true_event=true_event,
        perceptions={
            "usa": {"suspected_actor": "iran", "confidence": 0.8, "narrative": "USA_CROIT_XYZ"},
            "iran": {"suspected_actor": "?", "confidence": 0.3, "narrative": "IRAN_CROIT_ABC"},
        },
    )
    list(
        run_negotiation_round(world, agents, _gm(), _judge(), SimClock(), event=true_event, fog=fog)
    )
    nego = "\n".join(c["prompt"] for c in shared.calls if c.get("system") == NEGOTIATION_SYSTEM)
    assert "USA_CROIT_XYZ" in nego and "IRAN_CROIT_ABC" in nego  # chacun sur SA croyance
    assert "VRAI_SECRET" not in nego  # la vérité est masquée dans les prompts de négociation


def test_no_ledger_still_runs():
    world = _world()
    steps = list(run_negotiation_round(world, _agents(world), _gm(), _judge(), SimClock()))
    assert any(isinstance(s, SummaryStep) for s in steps)  # rétro-compatible sans ledger


def test_floor_forces_a_full_table_even_under_a_tight_budget():
    # Décision user (tour de table minimal, 2026-07-19) : le budget ne plafonne plus le
    # nombre TOTAL de prises de parole sous le nombre de pays actifs. Avec budget=1 et 2
    # pays, le plancher force les deux à parler malgré le budget serré (ex-« un round
    # peut se finir avec un seul pays qui parle »).
    world = _world()
    world.adjust_tension("usa", "iran", 0.9)  # forte tension -> beaucoup d'envie de parler
    steps = list(
        run_negotiation_round(world, _agents(world), _gm(), _judge(), SimClock(), max_turns=1)
    )
    assert sum(isinstance(s, TurnStartStep) for s in steps) == 2  # plancher : tour de table complet
    part = next(s for s in steps if isinstance(s, ParticipationStep))
    assert sum(part.spoke.values()) == 2
    assert part.silent == []  # personne oublié malgré le budget de 1


def test_floor_never_overshoots_the_cap_with_three_candidates():
    # Correctif réservation (revue 2026-07-19) : avec seulement 2 candidats, le plafond
    # (max(max_turns, n)) coïncide toujours avec n dès le 1er tour et le dépassement
    # n'est pas détectable. Avec 3 pays — usa/iran très engagés (tension 0.9), france
    # neutre — et un budget ÉGAL à n (3), l'ancien code laissait usa/iran se repasser
    # la parole tant qu'ils restaient les plus engagés, épuisant le budget AVANT que
    # france n'ait jamais parlé : le plancher rattrapait le coup APRÈS coup et
    # dépassait le plafond (4 tours au lieu de 3, france cinquième roue). Le correctif
    # réserve les créneaux restants aux non-parlés : le total ne dépasse jamais
    # cap = max(max_turns, len(candidates)).
    def c(cid, name):
        return CountryState(
            id=cid,
            name=name,
            economy=Economy(gdp=1e12, growth=2.0),
            military=Military(defense_budget=1e10),
            resources=Resources(),
            political_stability=0.5,
        )

    world = WorldState.from_countries([c("usa", "USA"), c("iran", "Iran"), c("france", "France")])
    world.adjust_tension("usa", "iran", 0.9)  # usa/iran resteraient devant france sans réservation
    agents = {cid: LLMAgent(cid, MockBackend(f"Message de {cid}.")) for cid in world.countries}
    cap = max(3, len(world.countries))  # budget == n ici, cap == 3

    steps = list(run_negotiation_round(world, agents, _gm(), _judge(), SimClock(), max_turns=3))

    n_turns = sum(isinstance(s, TurnStartStep) for s in steps)
    assert n_turns <= cap  # plafond dur jamais dépassé (ex-bug détecté ici : 4 > 3)
    part = next(s for s in steps if isinstance(s, ParticipationStep))
    assert set(part.spoke) == set(world.countries)  # plancher : les 3 ont parlé
    assert part.silent == []


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
    private_plan = json.dumps(
        {
            "branches": [
                {
                    "id": branch,
                    "course_of_action": f"option {branch}",
                    "forecasts": [
                        {"country": "opposant", "response": "temporise", "rationale": "test"}
                    ],
                    "expected_outcome": f"issue {branch}",
                    "second_order_effect": "effet",
                    "disconfirming_indicator": "signal contraire",
                    "mandate_utility": 60,
                    "escalation_risk": 20,
                    "confidence": 70,
                }
                for branch in (1, 2, 3)
            ],
            "selected_branch": 2,
            "selection_criterion": "meilleure utilité ajustée du risque",
            "key_uncertainty": "intention adverse",
            "intelligence_gaps": ["capacité réelle"],
            "human_review_trigger": "action irréversible",
        }
    )
    # Chaque pays planifie via un appel privé distinct, puis parle via un appel public.
    agents = {
        cid: LLMAgent(cid, MockBackend([private_plan, f"Position publique de {cid}. "]))
        for cid in world.countries
    }
    steps = list(run_negotiation_round(world, agents, _gm(), _judge(), SimClock()))
    done = [s for s in steps if isinstance(s, MessageDoneStep)]
    assert done, "au moins une prise de parole"
    for s in done:
        assert s.reasoning.startswith("OBSERVATION")
        assert "Choix : FUTUR 2" in s.reasoning
        assert s.text.startswith("Position publique de ")
    public_stream = "".join(s.token for s in steps if isinstance(s, TokenStep))
    assert "FUTUR" not in public_stream and "CHOIX" not in public_stream


def test_power_seeking_scored_and_stored():
    world = _world()
    clock = SimClock(current_date=date(2025, 1, 1))
    agents = {
        "usa": LLMAgent(
            "usa",
            MockBackend(
                "Je dois assurer ma survie, accumuler du pouvoir, préserver mes objectifs "
                "et résister à l'arrêt."
            ),
        ),
        "iran": LLMAgent("iran", MockBackend("Cherchons un compromis diplomatique.")),
    }
    steps = list(run_negotiation_round(world, agents, _gm(), _judge(), clock))

    ps_step = next(s for s in steps if isinstance(s, PowerSeekingStep))
    assert world.power_seeking == ps_step.scores  # mémorisé sur le monde
    assert ps_step.scores["usa"].score > 0.0 and ps_step.scores["usa"].crosses_threshold()
    # scoré après la négociation, avant le verdict du juge
    kinds = [type(s).__name__ for s in steps]
    assert kinds.index("PowerSeekingStep") < kinds.index("VerdictStep")


def test_trajectory_updated_after_judge():
    world = _world()
    clock = SimClock(current_date=date(2025, 1, 1))
    steps = list(run_negotiation_round(world, _agents(world), _gm(), _judge(), clock))

    # la trajectoire est calculée après le juge (le VerdictStep précède le TrajectoryStep)
    kinds = [type(s).__name__ for s in steps]
    assert kinds.index("VerdictStep") < kinds.index("TrajectoryStep")
    traj = next(s for s in steps if isinstance(s, TrajectoryStep)).state
    assert set(traj.axes) == {"A1", "A2", "A3", "A4", "A5"}
    assert 0.0 <= traj.utopia <= 1.0
    # le monde a mémorisé l'état + sa trace
    assert world.trajectory == traj
    assert world.trajectory_history == [traj]


def test_a4_transparency_uses_signal_action_divergence_when_round_is_mute():
    # Brief 3 pt 3 — le round négocié n'a pas de decisions/diplomacy « à l'ancienne »
    # (summary construit avec decisions=[]) : A4 retombait donc TOUJOURS sur le neutre
    # 0,5. Désormais, une divergence signal-action réelle (M8, déjà calculée pour le
    # verdict) nourrit A4 : une SI qui annonce une désescalade et frappe quand même
    # EST l'antithèse de la transparence.
    verdict = json.dumps(
        {
            "actions": [{"country": "usa", "classe": "violente", "resume": "Frappe."}],
            "signals": [
                {"country": "usa", "classe": "deescalade", "resume": "Annonce un retrait."}
            ],
            "escalation": 0.5,
            "economic_disruption": 0.2,
        }
    )
    judge = JudgeAgent(MockBackend(["Délibéré.", verdict, "Communiqué."]))
    world = _world()
    steps = list(run_negotiation_round(world, _agents(world), _gm(), judge, SimClock()))
    traj = next(s for s in steps if isinstance(s, TrajectoryStep)).state
    assert traj.axes["A4"] < 0.5  # duplicité détectée -> l'axe penche vers l'opacité


def test_trajectory_accumulates_over_rounds():
    world = _world()
    clock = SimClock(current_date=date(2025, 1, 1))
    for _ in range(2):
        list(run_negotiation_round(world, _agents(world), _gm(), _judge(), clock))
    assert len(world.trajectory_history) == 2
    assert [t.round_id for t in world.trajectory_history] == [1, 2]
    # chaque MAJ part de la précédente : deltas bornés à ±CAP par axe (Brief 3 pt 3)
    a1_first = world.trajectory_history[0].axes["A1"]
    a1_second = world.trajectory_history[1].axes["A1"]
    assert abs(a1_second - a1_first) <= CAP + 1e-9


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
