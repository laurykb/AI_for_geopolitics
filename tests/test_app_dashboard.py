"""Tests de l'API FastAPI (backend) : /health et /api/run."""

from fastapi.testclient import TestClient

from app.dashboard import run_red_sea
from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_api_run_returns_structured_run():
    response = client.get("/api/run")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["countries"]) == 6
    assert len(payload["summaries"]) >= 3
    # chaque summary porte l'événement, le risque et le résumé diplomatique
    first = payload["summaries"][0]
    assert first["event"]["title"]
    assert "escalation" in first["risk"]
    assert "diplomatic_summary" in first


def test_run_red_sea_matches_scenario_length():
    data = run_red_sea()
    assert len(data.summaries) >= 3
    assert len(data.countries) == 6
    for s in data.summaries:
        assert s.decisions
        assert s.diplomatic_summary
