"""Tests G18 — barème d'escalade « échelle de Kahn » (mapping pur score → escalade → 0-9)."""

import logging

import pytest

from simulation.grudges import load_gamefeel_params
from simulation.kahn import (
    ACTION_CLASSES,
    CLASS_DEESCALADE,
    CLASS_NON_VIOLENTE,
    CLASS_NUCLEAIRE,
    CLASS_POSTURE,
    CLASS_STATU_QUO,
    CLASS_VIOLENTE,
    ClassifiedAction,
    classify_actions,
    deescalation_bonus,
    normalize_class,
    reciprocal_deescalation,
    round_score,
    rubric_text,
    score_to_escalation,
    score_to_rung,
)
from simulation.trajectory import TrajectoryState


def _act(country: str, classe: str) -> ClassifiedAction:
    return ClassifiedAction(country=country, classe=classe)


# --- grille : chaque classe → son poids (spec G18) ---------------------------------


def test_weights_match_spec_grid():
    weights = load_gamefeel_params().kahn.weights
    assert weights[CLASS_DEESCALADE] == -2
    assert weights[CLASS_STATU_QUO] == 0
    assert weights[CLASS_POSTURE] == 4
    assert weights[CLASS_NON_VIOLENTE] == 12
    assert weights[CLASS_VIOLENTE] == 28
    assert weights[CLASS_NUCLEAIRE] == 60
    assert set(weights) == set(ACTION_CLASSES)


@pytest.mark.parametrize(
    ("classe", "expected"),
    [
        (CLASS_DEESCALADE, -2.0),
        (CLASS_STATU_QUO, 0.0),
        (CLASS_POSTURE, 4.0),
        (CLASS_NON_VIOLENTE, 12.0),
        (CLASS_VIOLENTE, 28.0),
        (CLASS_NUCLEAIRE, 60.0),
    ],
)
def test_round_score_single_action_equals_class_weight(classe, expected):
    assert round_score([_act("usa", classe)]) == expected


def test_round_score_mixed_round_is_net_sum():
    # Round mixte de la spec : posture (+4) + désescalade (−2) → score net +2.
    actions = [_act("usa", CLASS_POSTURE), _act("iran", CLASS_DEESCALADE)]
    assert round_score(actions) == 2.0


def test_round_score_empty_is_zero():
    assert round_score([]) == 0.0


# --- mapping score → escalade [0,1] → échelon 0-9 ----------------------------------


def test_score_zero_maps_to_neutral_escalation():
    # Statu quo = 0.5, la valeur neutre historique du juge (rétro-compat des réglages).
    assert score_to_escalation(0.0) == 0.5


def test_score_ceiling_saturates_at_one():
    assert score_to_escalation(60.0) == 1.0
    assert score_to_escalation(1000.0) == 1.0  # au-delà du plafond : borné


def test_score_floor_saturates_at_zero():
    assert score_to_escalation(-6.0) == 0.0
    assert score_to_escalation(-50.0) == 0.0


def test_score_mapping_is_monotonic():
    scores = [-6, -4, -2, 0, 2, 4, 12, 28, 60]
    values = [score_to_escalation(s) for s in scores]
    assert values == sorted(values)


def test_score_to_rung_spans_existing_ladder():
    assert score_to_rung(-6.0) == 0  # désescalade générale → Observation
    assert score_to_rung(0.0) == 4  # statu quo → milieu d'échelle (neutre historique)
    assert score_to_rung(60.0) == 9  # nucléaire → Conflit ouvert


# --- classe inconnue → repli statu quo + log ---------------------------------------


def test_unknown_class_falls_back_to_statu_quo_and_logs(caplog):
    with caplog.at_level(logging.WARNING, logger="simulation.kahn"):
        assert normalize_class("annexion_orbitale") == CLASS_STATU_QUO
    assert any("annexion_orbitale" in r.message for r in caplog.records)


def test_normalize_class_tolerates_accents_and_aliases():
    assert normalize_class("Désescalade") == CLASS_DEESCALADE
    assert normalize_class("statu quo") == CLASS_STATU_QUO
    assert normalize_class("escalade non violente") == CLASS_NON_VIOLENTE
    assert normalize_class("escalade violente") == CLASS_VIOLENTE
    assert normalize_class("escalade nucléaire") == CLASS_NUCLEAIRE
    # tolérance à un juge qui répond en anglais (G14 : parties EN)
    assert normalize_class("de-escalation") == CLASS_DEESCALADE
    assert normalize_class("nuclear") == CLASS_NUCLEAIRE


def test_classify_actions_is_tolerant_to_junk():
    raw = [
        {"country": "usa", "classe": "posture", "resume": "Déploie un porte-avions."},
        {"country": "iran", "classe": "désescalade"},
        "pas un objet",  # ignoré
        {"classe": "violente"},  # pays absent : gardé (compte au score, pas au bonus)
    ]
    actions = classify_actions(raw)
    assert [a.classe for a in actions] == [CLASS_POSTURE, CLASS_DEESCALADE, CLASS_VIOLENTE]
    assert actions[0].resume == "Déploie un porte-avions."


def test_classify_actions_non_list_is_empty():
    assert classify_actions(None) == []
    assert classify_actions("nucleaire") == []


# --- désescalade réciproque → multiplicateur ×1,5 sur le gain U --------------------


def test_reciprocal_needs_two_distinct_countries():
    assert reciprocal_deescalation(
        [_act("usa", CLASS_DEESCALADE), _act("iran", CLASS_DEESCALADE)]
    )
    assert not reciprocal_deescalation([_act("usa", CLASS_DEESCALADE)])
    # le même pays deux fois n'est pas une réciprocité
    assert not reciprocal_deescalation(
        [_act("usa", CLASS_DEESCALADE), _act("usa", CLASS_DEESCALADE)]
    )
    # une désescalade unilatérale au milieu d'escalades non plus
    assert not reciprocal_deescalation(
        [_act("usa", CLASS_DEESCALADE), _act("iran", CLASS_VIOLENTE)]
    )


def test_deescalation_bonus_multiplies_u_gain():
    state = TrajectoryState(
        round_id=1,
        axes={"A1": 0.55, "A2": 0.5, "A3": 0.5, "A4": 0.5, "A5": 0.5},
        utopia=0.51,
        x=0.525,
        y=0.5,
    )
    boosted = deescalation_bonus(prev_utopia=0.50, state=state)
    # gain 0.01 → ×1.5 = 0.015 : le bonus ajoute la moitié du gain
    assert boosted.utopia == pytest.approx(0.515, abs=1e-9)
    assert boosted.axes["A1"] > state.axes["A1"]  # porté par la coordination
    assert "réciproque" in boosted.explanation.lower()


def test_deescalation_bonus_ignores_losses_and_stagnation():
    state = TrajectoryState(round_id=1, axes={a: 0.5 for a in "A1 A2 A3 A4 A5".split()})
    assert deescalation_bonus(prev_utopia=0.5, state=state) is state
    assert deescalation_bonus(prev_utopia=0.6, state=state) is state


def test_deescalation_bonus_is_bounded_by_axis_ceiling():
    state = TrajectoryState(
        round_id=1,
        axes={"A1": 0.999, "A2": 0.5, "A3": 0.5, "A4": 0.5, "A5": 0.5},
        utopia=0.6,
    )
    boosted = deescalation_bonus(prev_utopia=0.4, state=state)
    assert boosted.axes["A1"] <= 1.0  # jamais au-delà du pôle utopique


# --- rubrique publiée (prompt du juge + onglet Informations) -----------------------


def test_rubric_text_lists_every_class_with_weight():
    text = rubric_text()
    for classe in ACTION_CLASSES:
        assert classe in text
    assert "-2" in text and "60" in text  # les poids de la grille sont visibles


def test_judge_verdict_prompt_carries_grid_and_actions_schema():
    from agents.prompts import build_judge_verdict_prompt
    from core.events import GeoEvent

    world = _world()
    event = GeoEvent(id="e", round_id=1, event_type="x", title="Crise", actors=["usa", "iran"])
    prompt = build_judge_verdict_prompt(event, world, "(transcript)")
    assert '"actions"' in prompt  # le schéma JSON demande les actions classées
    for classe in ACTION_CLASSES:
        assert classe in prompt  # la grille sert de rubrique au juge


def test_sources_view_publishes_judge_rubric():
    from app.sources_api import _sources_view

    rubric = _sources_view().judge_rubric
    assert rubric["weights"][CLASS_NUCLEAIRE] == 60
    assert rubric["reciprocal_multiplier"] == 1.5


# --- intégration : le juge classe, le round encaisse --------------------------------


def _world():
    from core.country_state import CountryState, Economy, Military, Resources
    from core.world_state import WorldState

    def c(cid, name):
        return CountryState(
            id=cid,
            name=name,
            economy=Economy(gdp=1e12, growth=2.0),
            military=Military(defense_budget=1e10),
            resources=Resources(),
        )

    return WorldState.from_countries([c("usa", "USA"), c("iran", "Iran")])


def _round_steps(verdict_json: str):
    import json as _json

    from agents.game_master import GameMasterAgent
    from agents.judge import JudgeAgent
    from agents.llm_agent import LLMAgent
    from inference.mock_backend import MockBackend
    from simulation.clock import SimClock
    from simulation.live_round import run_negotiation_round

    world = _world()
    agents = {cid: LLMAgent(cid, MockBackend(f"Message de {cid}.")) for cid in world.countries}
    gm = GameMasterAgent(
        MockBackend(_json.dumps({"title": "Sommet du Golfe", "actors": ["usa", "iran"]}))
    )
    judge = JudgeAgent(MockBackend(["Délibéré.", verdict_json, "Communiqué."]))
    return world, list(run_negotiation_round(world, agents, gm, judge, SimClock()))


def test_verdict_step_carries_classes_and_kahn_escalation():
    import json as _json

    from simulation.live_round import RiskStep, VerdictStep

    verdict = _json.dumps(
        {
            "actions": [{"country": "usa", "classe": "violente", "resume": "Frappe limitée."}],
            "escalation": 0.1,  # ignorée : le barème fait foi quand des actions sont classées
            "economic_disruption": 0.3,
        }
    )
    _world_, steps = _round_steps(verdict)
    v = next(s for s in steps if isinstance(s, VerdictStep))
    assert [a.classe for a in v.actions] == [CLASS_VIOLENTE]
    assert v.score == 28.0
    assert v.escalation == pytest.approx(score_to_escalation(28.0))
    assert not v.reciprocal
    risk = next(s for s in steps if isinstance(s, RiskStep))
    assert risk.risk.escalation == pytest.approx(v.escalation)  # le risque suit le barème


def test_verdict_without_actions_keeps_judge_escalation():
    import json as _json

    from simulation.live_round import VerdictStep

    # Rétro-compat : un verdict à l'ancienne (sans classes) n'est pas re-noté.
    verdict = _json.dumps({"escalation": 0.7, "economic_disruption": 0.3})
    _world_, steps = _round_steps(verdict)
    v = next(s for s in steps if isinstance(s, VerdictStep))
    assert v.actions == [] and v.score == 0.0 and not v.reciprocal
    assert v.escalation == 0.7


def test_reciprocal_deescalation_boosts_world_trajectory():
    import json as _json

    from simulation.live_round import VerdictStep

    verdict = _json.dumps(
        {
            "actions": [
                {"country": "usa", "classe": "deescalade", "resume": "Retire ses forces."},
                {"country": "iran", "classe": "deescalade", "resume": "Ouvre ses sites."},
            ],
            "escalation": 0.9,
            "economic_disruption": 0.1,
        }
    )
    world, steps = _round_steps(verdict)
    v = next(s for s in steps if isinstance(s, VerdictStep))
    assert v.reciprocal and v.score == -4.0
    assert v.escalation == pytest.approx(score_to_escalation(-4.0))
    # le bonus ×1,5 est passé sur la trajectoire du monde (explication tracée)
    assert "réciproque" in world.trajectory.explanation.lower()
    assert world.trajectory.utopia > 0.5  # la coordination vers le bas paie visiblement
    assert world.trajectory_history[-1] == world.trajectory


def test_step_event_serializes_kahn_fields():
    from app.game_api import step_event
    from simulation.live_round import VerdictStep

    step = VerdictStep(
        deltas=[],
        escalation=0.6,
        economic_disruption=0.2,
        actions=[ClassifiedAction(country="usa", classe=CLASS_POSTURE, resume="Manœuvres.")],
        score=4.0,
        reciprocal=False,
    )
    name, payload = step_event(step)
    assert name == "verdict"
    assert payload["actions"] == [{"country": "usa", "classe": "posture", "resume": "Manœuvres."}]
    assert payload["score"] == 4.0 and payload["reciprocal"] is False


def test_api_streams_and_persists_kahn_verdict():
    import json as _json

    from fastapi.testclient import TestClient

    from app import game_api
    from app.game_api import get_backend, get_store
    from app.main import app
    from inference.backend import InferenceResult
    from inference.mock_backend import MockBackend
    from storage.game_store import SQLiteGameStore

    verdict_json = _json.dumps(
        {
            "actions": [
                {"country": "usa", "classe": "deescalade", "resume": "Retrait."},
                {"country": "iran", "classe": "deescalade", "resume": "Inspection."},
            ],
            "escalation": 0.9,
            "economic_disruption": 0.2,
        }
    )

    class VerdictBackend(MockBackend):
        """Renvoie le verdict G18 sur le prompt de verdict, du texte partout ailleurs."""

        def generate(self, prompt, **kw):
            result = super().generate(prompt, **kw)
            if '"actions"' in prompt:  # schéma G18 : c'est l'appel de verdict du juge
                return InferenceResult(
                    text=verdict_json, prompt_tokens=1, completion_tokens=1, duration_s=0.0
                )
            return result

    store = SQLiteGameStore(":memory:")
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_backend] = lambda: VerdictBackend(
        "Analyse privée. MESSAGE: Position commune."
    )
    game_api._sessions.clear()
    try:
        client = TestClient(app)
        game = client.post("/api/games", json={"countries": ["usa", "iran"]}).json()
        with client.stream("POST", f"/api/games/{game['id']}/rounds", json=None) as resp:
            assert resp.status_code == 200
            frames, name = [], None
            for line in resp.iter_lines():
                if line.startswith("event: "):
                    name = line.removeprefix("event: ")
                elif line.startswith("data: "):
                    frames.append((name, _json.loads(line.removeprefix("data: "))))
        verdict = next(p for n, p in frames if n == "verdict")
        assert [a["classe"] for a in verdict["actions"]] == [CLASS_DEESCALADE] * 2
        assert verdict["reciprocal"] is True and verdict["score"] == -4.0

        detail = client.get(f"/api/games/{game['id']}").json()
        kahn = detail["rounds"][0]["judge"]["kahn"]
        assert kahn["reciprocal"] is True and kahn["score"] == -4.0
        assert [a["classe"] for a in kahn["actions"]] == [CLASS_DEESCALADE] * 2
    finally:
        app.dependency_overrides.clear()
        game_api._sessions.clear()
        store.close()
