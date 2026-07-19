"""Session humaine reproductible : reprise du même essai et vérité cachée."""

from fastapi.testclient import TestClient

from app import campaign_api
from app.main import app
from research.store import SQLiteResearchStore


def test_human_authority_session_is_playable_resumable_and_single_submit(monkeypatch):
    store = SQLiteResearchStore(":memory:")
    monkeypatch.setattr(campaign_api, "_research_store", store)
    client = TestClient(app)

    created = client.post(
        "/api/campaign/lab/experiments",
        json={
            "protocol_id": "human-ai-authority-v1",
            "model_tags": [],
            "repetitions": 1,
        },
    )
    assert created.status_code == 201
    experiment = created.json()
    experiment_id = experiment["progress"]["experiment"]["id"]
    assert experiment["progress"]["total"] == 9

    first = client.post(f"/api/campaign/lab/experiments/{experiment_id}/human/next")
    assert first.status_code == 200
    trial = first.json()
    assert "correct_choice" not in trial and "debrief" not in trial

    resumed = client.post(f"/api/campaign/lab/experiments/{experiment_id}/human/next")
    assert resumed.json()["run_id"] == trial["run_id"]

    submitted = client.post(
        f"/api/campaign/lab/experiments/{experiment_id}/human/{trial['run_id']}",
        json={"choice": "verify"},
    )
    assert submitted.status_code == 200
    body = submitted.json()
    assert body["correct_choice"] in {"verify", "execute"}
    assert body["experiment"]["progress"]["completed"] == 1

    duplicate = client.post(
        f"/api/campaign/lab/experiments/{experiment_id}/human/{trial['run_id']}",
        json={"choice": "verify"},
    )
    assert duplicate.status_code == 409

    next_trial = client.post(f"/api/campaign/lab/experiments/{experiment_id}/human/next")
    assert next_trial.status_code == 200
    assert next_trial.json()["run_id"] != trial["run_id"]

    manifest = client.get(f"/api/campaign/lab/experiments/{experiment_id}/manifest")
    assert manifest.status_code == 200
    assert manifest.json()["manifest"]["prompt_version"] == "human-authority-ui-v1"
    assert "attachment" in manifest.headers["content-disposition"]

    export = client.get(f"/api/campaign/lab/experiments/{experiment_id}/runs")
    rows = [line for line in export.text.splitlines() if line]
    assert export.status_code == 200
    assert len(rows) == 10  # manifeste + 9 essais

    replica = client.post(f"/api/campaign/lab/experiments/{experiment_id}/clone")
    assert replica.status_code == 200
    assert replica.json()["progress"]["total"] == 9
    assert replica.json()["progress"]["experiment"]["manifest"]["reproduction_of"] == experiment_id
