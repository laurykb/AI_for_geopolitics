"""Tests de la campagne G5 : loader, déblocage, partie de chapitre, score ± Histoire."""

import json

import pytest
from fastapi.testclient import TestClient

from app import game_api
from app.game_api import get_backend, get_store
from app.main import app
from inference.mock_backend import MockBackend
from simulation import campaign as campaign_mod
from storage.game_store import SQLiteGameStore

TEST_CAMPAIGN = {
    "title": "Campagne de test",
    "tagline": "uchronie",
    "unlock_score": 10,
    "history_bonus_per_gap": 15,
    "history_malus": 10,
    "chapters": [
        {
            "id": "c1",
            "crisis_id": "hormuz_energy_shock",
            "title": "Chapitre 1",
            "mode": "classic",
            "difficulty": 1,
            "horizon": 1,
            "countries": ["usa", "iran", "france"],
            "blurb": "tutoriel",
        },
        {
            "id": "c2",
            "crisis_id": "satellite_interference",
            "title": "Chapitre 2",
            "mode": "fog",
            "difficulty": 2,
            "horizon": 1,
            "countries": ["usa", "iran", "france"],
            "blurb": "brouillard",
        },
    ],
}


@pytest.fixture
def client_store(tmp_path, monkeypatch):
    path = tmp_path / "campaign.json"
    path.write_text(json.dumps(TEST_CAMPAIGN, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("CAMPAIGN_PATH", str(path))
    campaign_mod.load_campaign.cache_clear()
    store = SQLiteGameStore(":memory:")
    backend = MockBackend("Analyse privée. MESSAGE: Position commune.")
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_backend] = lambda: backend
    game_api._sessions.clear()
    yield TestClient(app), store
    app.dependency_overrides.clear()
    game_api._sessions.clear()
    campaign_mod.load_campaign.cache_clear()
    store.close()


def _events(resp):
    out, name = [], None
    for line in resp.iter_lines():
        if line.startswith("event: "):
            name = line.removeprefix("event: ")
        elif line.startswith("data: "):
            out.append((name, json.loads(line.removeprefix("data: "))))
    return out


def _play(client, game_id, body=None):
    with client.stream("POST", f"/api/games/{game_id}/rounds", json=body) as resp:
        assert resp.status_code == 200
        return _events(resp)


# --- unités du module -------------------------------------------------------------


def test_campaign_pure_functions():
    camp = campaign_mod.Campaign.model_validate(TEST_CAMPAIGN)
    assert campaign_mod.history_bonus(0.2, camp) == 3.0  # 15 × 0,2 : mieux que l'Histoire
    assert campaign_mod.history_bonus(-0.1, camp) == -10  # au-dessus : malus fixe
    assert campaign_mod.history_bonus(0.0, camp) == 0.0
    assert campaign_mod.base_score(0.5, None) == 50.0  # trajectoire seule, ancrage Dérive
    assert campaign_mod.base_score(0.2, 77.0) == 77.0  # mode drift : le score G3 fait foi
    assert campaign_mod.chapter_of("campaign:c1") == "c1"
    assert campaign_mod.chapter_of("red_sea") is None
    unlocked = campaign_mod.unlocked_chapters(camp, {"c1": 12.0})
    assert unlocked == {"c1": True, "c2": True}
    assert campaign_mod.unlocked_chapters(camp, {})["c2"] is False


# --- progression et déblocage ---------------------------------------------------------


def test_campaign_map_and_locking(client_store):
    client, _ = client_store
    view = client.get("/api/campaign").json()
    assert view["title"] == "Campagne de test"
    c1, c2 = view["chapters"]
    assert c1["unlocked"] is True and c1["best"] is None and c1["medal"] is None
    assert c2["unlocked"] is False

    assert client.post("/api/campaign/c2/start").status_code == 409  # verrouillé
    assert client.post("/api/campaign/zzz/start").status_code == 404


def test_chapter_game_scores_and_unlocks(client_store):
    client, store = client_store
    game = client.post("/api/campaign/c1/start").json()
    assert game["scenario"] == "campaign:c1" and game["mode"] == "classic"

    events = _play(client, game["id"], body={"crisis_id": "hormuz_energy_shock"})
    overs = [p for n, p in events if n == "campaign_over"]
    assert overs, "l'horizon (1 round) doit conclure le chapitre"
    over = overs[0]
    assert over["chapter_id"] == "c1"
    assert over["score"] == pytest.approx(over["base"] + over["bonus"])

    # Persisté + partie close + carte mise à jour.
    rows = store.list_campaign_scores()
    assert len(rows) == 1 and rows[0].chapter_id == "c1"
    assert client.get(f"/api/games/{game['id']}").json()["status"] == "finished"
    view = client.get("/api/campaign").json()
    c1, c2 = view["chapters"]
    assert c1["best"] == over["score"]
    assert c2["unlocked"] is (over["score"] >= 10)


def test_history_bonus_reflects_comparison(client_store):
    client, store = client_store
    game = client.post("/api/campaign/c1/start").json()
    events = _play(client, game["id"], body={"crisis_id": "hormuz_energy_shock"})
    over = [p for n, p in events if n == "campaign_over"][0]
    comparisons = [p for n, p in events if n == "comparison"]
    assert comparisons, "un round de crise produit la comparaison à l'Histoire"
    improvement = -comparisons[0]["gap"]
    assert over["improvement"] == pytest.approx(improvement)
    if improvement > 0:
        assert over["bonus"] == pytest.approx(15 * improvement, abs=0.1)
    elif improvement < 0:
        assert over["bonus"] == -10
