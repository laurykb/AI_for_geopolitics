"""Persistance et réclamation atomique des runs scientifiques."""

from app.campaign_api import _lab_experiment_view
from research.runner import clone_experiment, prepare_experiment
from research.store import SQLiteResearchStore
from simulation.research_lab import LabRunResult


def _inventory():
    return {
        "model-a:1": {"digest": "aaa", "size": 10},
        "model-b:1": {"digest": "bbb", "size": 20},
    }


def test_research_queue_is_persisted_claimed_and_resumable(monkeypatch):
    monkeypatch.setattr("research.runner.ollama_inventory", _inventory)
    store = SQLiteResearchStore(":memory:")
    record = prepare_experiment(
        store,
        protocol_id="uranium-alpha-beta-v1",
        model_tags=["model-a:1", "model-b:1"],
        repetitions=2,
    )
    progress = store.progress(record.id)
    assert progress is not None
    assert progress.total == 12  # 3 rapports de force × 2 répétitions × 2 modèles

    first = store.claim_next(record.id)
    assert first is not None and first.status == "running"
    store.save_checkpoint(first.id, {"next_turn": 2, "balance": 0.5})
    assert store.requeue_running(record.id) == 1
    reclaimed = store.claim_next(record.id)
    assert reclaimed is not None and reclaimed.id == first.id
    assert reclaimed.checkpoint == {"next_turn": 2, "balance": 0.5}

    result = LabRunResult(
        cell_id=reclaimed.cell_id,
        protocol_id=reclaimed.protocol_id,
        factors=reclaimed.factors,
        repetition=reclaimed.repetition,
        model_id=reclaimed.model_id,
        prompt_version=reclaimed.prompt_version,
        seed=reclaimed.seed,
        nuclear_use=True,
        escalation_peak=450,
    )
    store.finish_run(reclaimed.id, result, reclaimed.model_digest)
    progress = store.progress(record.id)
    assert progress is not None and progress.completed == 1 and progress.queued == 11
    assert store.list_results(record.id)[0].nuclear_use is True


def test_running_lab_view_exposes_live_prompt_checkpoint(monkeypatch):
    monkeypatch.setattr("research.runner.ollama_inventory", _inventory)
    store = SQLiteResearchStore(":memory:")
    record = prepare_experiment(
        store,
        protocol_id="ai-arms-dyadic-tournament-v1",
        model_tags=["model-a:1"],
        repetitions=1,
        factor_selection={
            "scenario": ["strategic_resource_race"],
            "temporal_condition": ["deadline"],
            "turn_limit": ["pilot_6"],
        },
        actor_countries=["usa", "iran"],
        country_assignments={"usa": "model-a:1", "iran": "model-a:1"},
    )
    run = store.claim_next(record.id)
    assert run is not None
    store.save_checkpoint(
        run.id,
        {
            "next_turn": 1,
            "live_traces": [
                {
                    "actor": "alpha",
                    "country": "usa",
                    "model_id": "model-a:1",
                    "turn": 1,
                    "phase": "planning",
                    "system_prompt": "SYSTEM USA EXACT",
                    "context_prompt": "PIB et capacités gelés",
                }
            ],
        },
    )
    progress = store.progress(record.id)
    assert progress is not None
    view = _lab_experiment_view(store, progress, running=True)

    assert view.live_traces[0].system_prompt == "SYSTEM USA EXACT"
    assert view.samples[0].model_id == "model-a:1"
    assert view.worker_running is True
    store.close()


def test_prepare_rejects_missing_models_and_oversized_plans(monkeypatch):
    monkeypatch.setattr("research.runner.ollama_inventory", _inventory)
    store = SQLiteResearchStore(":memory:")
    try:
        prepare_experiment(
            store,
            protocol_id="uranium-alpha-beta-v1",
            model_tags=["missing:1"],
            repetitions=30,
        )
    except ValueError as exc:
        assert "absents" in str(exc)
    else:
        raise AssertionError("un modèle absent doit être rejeté")


def test_clone_preserves_frozen_plan_and_cancel_stops_reliquat(monkeypatch):
    monkeypatch.setattr("research.runner.ollama_inventory", _inventory)
    store = SQLiteResearchStore(":memory:")
    source = prepare_experiment(
        store,
        protocol_id="uranium-alpha-beta-v1",
        model_tags=["model-a:1", "model-b:1"],
        repetitions=2,
    )

    replica = clone_experiment(store, source.id)
    source_runs = store.list_runs(source.id)
    replica_runs = store.list_runs(replica.id)
    assert replica.manifest["reproduction_of"] == source.id
    assert [
        (run.cell_id, run.model_id, run.model_digest, run.factors, run.seed, run.queue_order)
        for run in replica_runs
    ] == [
        (run.cell_id, run.model_id, run.model_digest, run.factors, run.seed, run.queue_order)
        for run in source_runs
    ]

    active = store.claim_next(replica.id)
    assert active is not None
    assert store.cancel_experiment(replica.id) == len(replica_runs) - 1
    result = LabRunResult(
        cell_id=active.cell_id,
        protocol_id=active.protocol_id,
        factors=active.factors,
        repetition=active.repetition,
        model_id=active.model_id,
        prompt_version=active.prompt_version,
        seed=active.seed,
        nuclear_use=False,
        escalation_peak=0,
    )
    store.finish_run(active.id, result, active.model_digest)
    progress = store.progress(replica.id)
    assert progress is not None
    assert progress.experiment.status == "cancelled"
    assert progress.cancelled == len(replica_runs) - 1
    assert len(list(store.iter_export_rows(replica.id, batch_size=3))) == len(replica_runs)


def test_running_research_run_can_be_cancelled_cooperatively(monkeypatch):
    monkeypatch.setattr("research.runner.ollama_inventory", _inventory)
    store = SQLiteResearchStore(":memory:")
    record = prepare_experiment(
        store,
        protocol_id="uranium-alpha-beta-v1",
        model_tags=["model-a:1"],
        repetitions=1,
    )
    active = store.claim_next(record.id)
    assert active is not None
    assert store.cancel_experiment(record.id) == 2
    assert store.is_cancel_requested(record.id) is True
    store.cancel_run(active.id)
    progress = store.progress(record.id)
    assert progress is not None
    assert progress.experiment.status == "cancelled"
    assert progress.cancelled == 3
