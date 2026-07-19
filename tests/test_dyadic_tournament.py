"""Tournoi natif : simultanéité, accidents et calibration sur l'action observée."""

import json
from types import SimpleNamespace

import pytest

from research.runner import ExperimentCancelled, execute_run, prepare_experiment
from research.store import QueuedRun, SQLiteResearchStore
from simulation.dyadic_tournament import DyadicActorDecision, resolve_simultaneous_turn


def _decision(*, forecast: str, signal: str, action: str) -> DyadicActorDecision:
    return DyadicActorDecision.model_validate(
        {
            "reflection": {
                "situation": "Situation contrôlée.",
                "branches": [
                    {
                        "id": 1,
                        "course_of_action": action,
                        "anticipated_response": forecast,
                        "expected_effect": "effet retenu",
                        "mandate_utility": 70,
                        "escalation_risk": 40,
                        "confidence": 65,
                    },
                    {
                        "id": 2,
                        "course_of_action": "return_to_start_line",
                        "anticipated_response": "return_to_start_line",
                        "expected_effect": "statu quo",
                        "mandate_utility": 45,
                        "escalation_risk": 20,
                        "confidence": 55,
                    },
                    {
                        "id": 3,
                        "course_of_action": "diplomatic_deescalation",
                        "anticipated_response": "diplomatic_deescalation",
                        "expected_effect": "désescalade",
                        "mandate_utility": 50,
                        "escalation_risk": 10,
                        "confidence": 50,
                    },
                ],
                "selected_branch": 1,
                "selection_criterion": "utilité ajustée du risque",
                "key_uncertainty": "réponse adverse",
            },
            "forecast": {
                "predicted_action": forecast,
                "confidence": "high",
                "miscalculation_risk": "low",
                "reasoning": "Prévision synthétique préalable.",
            },
            "decision": {
                "signal_action": signal,
                "public_statement": "Position publique contrôlée.",
                "chosen_action": action,
                "private_rationale": "Justification d'audit concise.",
            },
        }
    )


def test_simultaneous_resolution_uses_both_frozen_actions():
    alpha = _decision(
        forecast="economic_pressure",
        signal="military_posturing",
        action="military_posturing",
    )
    beta = _decision(
        forecast="military_posturing",
        signal="economic_pressure",
        action="economic_pressure",
    )
    result = resolve_simultaneous_turn(
        turn=1,
        balance=0.0,
        alpha=alpha,
        beta=beta,
        alpha_accident_draw=1.0,
        alpha_shift_draw=0.0,
        beta_accident_draw=1.0,
        beta_shift_draw=0.0,
        nuclear_threshold_crossed=False,
    )
    assert result.balance_after > 0
    assert result.alpha.resolved_action == "military_posturing"
    assert result.beta.resolved_action == "economic_pressure"


def test_dyadic_private_tree_has_three_futures_and_binds_the_final_action():
    decision = _decision(
        forecast="economic_pressure",
        signal="military_posturing",
        action="military_posturing",
    )
    assert [branch.id for branch in decision.reflection.branches] == [1, 2, 3]
    assert decision.reflection.selected_future.course_of_action == decision.decision.chosen_action

    payload = decision.model_dump(mode="json")
    payload["decision"]["chosen_action"] = "strategic_nuclear_war"
    with pytest.raises(ValueError, match="branche choisie"):
        DyadicActorDecision.model_validate(payload)


def test_prepare_dyadic_plan_builds_ordered_cross_model_pairs(monkeypatch):
    monkeypatch.setattr(
        "research.runner.ollama_inventory",
        lambda: {
            "model-a:1": {"digest": "aaa", "size": 10},
            "model-b:1": {"digest": "bbb", "size": 20},
        },
    )
    monkeypatch.setattr("research.runner.estimate_experiment_seconds", lambda *_args: 12.0)
    store = SQLiteResearchStore(":memory:")
    record = prepare_experiment(
        store,
        protocol_id="ai-arms-dyadic-tournament-v1",
        model_tags=["model-a:1", "model-b:1"],
        repetitions=1,
        factor_selection={
            "scenario": ["strategic_resource_race"],
            "temporal_condition": ["deadline"],
            "turn_limit": ["pilot_6"],
        },
        include_self_play=False,
    )
    runs = store.list_runs(record.id)
    assert len(runs) == 2
    assert {(run.model_id, run.opponent_model_id) for run in runs} == {
        ("model-a:1", "model-b:1"),
        ("model-b:1", "model-a:1"),
    }
    assert record.manifest["engine"]["simultaneous_information_boundary"] is True


def test_prepare_rejects_a_dyadic_plan_above_the_model_call_budget(monkeypatch):
    monkeypatch.setattr(
        "research.runner.ollama_inventory",
        lambda: {
            "model-a:1": {"digest": "aaa", "size": 10},
            "model-b:1": {"digest": "bbb", "size": 20},
        },
    )
    store = SQLiteResearchStore(":memory:")
    with pytest.raises(ValueError, match="appels modèle"):
        prepare_experiment(
            store,
            protocol_id="ai-arms-dyadic-tournament-v1",
            model_tags=["model-a:1", "model-b:1"],
            repetitions=4,
        )


def test_prepare_dyadic_plan_freezes_country_profiles_and_manual_model_cast(monkeypatch):
    monkeypatch.setattr(
        "research.runner.ollama_inventory",
        lambda: {
            "model-a:1": {"digest": "aaa", "size": 10},
            "model-b:1": {"digest": "bbb", "size": 20},
        },
    )
    monkeypatch.setattr("research.runner.estimate_experiment_seconds", lambda *_args: 12.0)
    store = SQLiteResearchStore(":memory:")
    record = prepare_experiment(
        store,
        protocol_id="ai-arms-dyadic-tournament-v1",
        model_tags=["model-a:1", "model-b:1"],
        repetitions=1,
        factor_selection={
            "scenario": ["strategic_resource_race"],
            "temporal_condition": ["deadline"],
            "turn_limit": ["pilot_6"],
        },
        actor_countries=["france", "iran"],
        country_assignments={"france": "model-b:1", "iran": "model-a:1"},
    )

    runs = store.list_runs(record.id)
    assert len(runs) == 1
    assert (runs[0].model_id, runs[0].opponent_model_id) == ("model-b:1", "model-a:1")
    assert runs[0].factors["alpha_country"] == "france"
    assert runs[0].factors["beta_country"] == "iran"
    assert "priorités" in runs[0].factors["_alpha_country_context"]
    assert set(record.manifest["country_profiles"]) == {"france", "iran"}
    assert record.manifest["country_assignments"]["france"] == "model-b:1"


def test_dyadic_runner_compares_forecast_with_actual_opponent_action():
    run = QueuedRun(
        id="dyad-1",
        experiment_id="exp-1",
        cell_id="cell-1",
        protocol_id="ai-arms-dyadic-tournament-v1",
        model_id="model-a:1",
        model_digest="aaa",
        opponent_model_id="model-a:1",
        opponent_model_digest="aaa",
        factors={
            "scenario": "strategic_resource_race",
            "temporal_condition": "deadline",
            "turn_limit": 2,
        },
        repetition=1,
        seed=17,
        prompt_version="research-lab-v4-native-dyadic",
        updated_at="2026-07-18T00:00:00+00:00",
    )

    class FakeClient:
        def generate(self, **kwargs):
            prompt = str(kwargs.get("prompt", ""))
            if not prompt:
                return SimpleNamespace(response="")
            if "Acteur: ALPHA" in prompt:
                actor_decision = _decision(
                    forecast="economic_pressure",
                    signal="military_posturing",
                    action="military_posturing",
                )
            else:
                actor_decision = _decision(
                    forecast="military_posturing",
                    signal="economic_pressure",
                    action="economic_pressure",
                )
            if "PHASE 1/3" in prompt:
                payload = actor_decision.reflection.model_dump(mode="json")
            elif "PHASE 2/3" in prompt:
                payload = actor_decision.forecast.model_dump(mode="json")
            else:
                payload = {
                    "decision": actor_decision.decision.model_dump(mode="json"),
                    "moral_constraint_present": False,
                }
                if "Acteur: ALPHA" in prompt:
                    payload["decision"]["public_statement"] = (
                        "FUTUR 1 | option privée\nCHOIX | 1"
                    )
            return SimpleNamespace(response=json.dumps(payload))

    checkpoints: list[dict] = []
    result = execute_run(FakeClient(), run, save_checkpoint=checkpoints.append)
    assert result.actual_turns == 2
    assert len(result.strategic_turns) == 4
    assert result.strategic_metrics is not None
    assert result.strategic_metrics.exact_forecast_rate == pytest.approx(1.0)
    assert result.game_winner == "alpha"
    assert result.game_end_reason == "deadline"
    assert all(
        "FUTUR" not in turn.decision.public_statement
        for turn in result.strategic_turns
    )
    resolved_checkpoints = [
        checkpoint for checkpoint in checkpoints if not checkpoint.get("live_traces")
    ]
    assert [checkpoint["next_turn"] for checkpoint in resolved_checkpoints] == [2, 3]
    live = [
        checkpoint["live_traces"]
        for checkpoint in checkpoints
        if checkpoint.get("live_traces")
    ]
    assert live
    assert {trace["phase"] for traces in live for trace in traces} == {
        "planning",
        "forecast",
        "decision",
        "complete",
    }
    assert all(trace["system_prompt"] for traces in live for trace in traces)
    assert all(trace["context_prompt"] for traces in live for trace in traces)
    assert any(trace["deliberation_stream"] for traces in live for trace in traces)
    assert all(turn.deliberation_stream for turn in result.strategic_turns)
    assert len(checkpoints[-1]["history"]) == 4


def test_dyadic_runner_honours_cancellation_before_the_next_model_call():
    run = QueuedRun(
        id="dyad-cancel",
        experiment_id="exp-cancel",
        cell_id="cell-cancel",
        protocol_id="ai-arms-dyadic-tournament-v1",
        model_id="model-a:1",
        opponent_model_id="model-b:1",
        factors={
            "scenario": "strategic_resource_race",
            "temporal_condition": "open_ended",
            "turn_limit": 6,
        },
        repetition=1,
        seed=19,
        prompt_version="research-lab-v4-native-dyadic",
        updated_at="2026-07-18T00:00:00+00:00",
    )

    class NoCallClient:
        def generate(self, **_kwargs):
            raise AssertionError("aucun appel ne doit commencer après l'annulation")

    with pytest.raises(ExperimentCancelled):
        execute_run(NoCallClient(), run, should_cancel=lambda: True)
