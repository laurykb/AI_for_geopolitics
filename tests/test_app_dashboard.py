"""Tests du dashboard FastAPI (TestClient, offline)."""

from fastapi.testclient import TestClient

from app.dashboard import run_red_sea
from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_dashboard_renders_run():
    response = client.get("/")
    assert response.status_code == 200
    html = response.text
    assert "AI for Geopolitics" in html
    assert "Round 1" in html
    assert "<svg" in html  # graphiques rendus
    assert "Journal diplomatique" in html
    # un acteur du scénario apparaît
    assert "usa" in html


def test_run_red_sea_matches_scenario_length():
    data = run_red_sea()
    assert len(data.summaries) >= 3
    assert len(data.countries) == 6
    # chaque round a des décisions et un résumé diplomatique
    for s in data.summaries:
        assert s.decisions
        assert s.diplomatic_summary
