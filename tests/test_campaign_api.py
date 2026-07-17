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
from tests.sse import play as _play

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
            "requires": ["c1"],  # G12-b — arbre : c2 s'ouvre quand c1 est fini
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


def test_real_campaign_json_is_a_valid_tree():
    # G12-b §4 + CC-5 — le vrai fichier : le tutoriel (ch. 0) puis l'arbre des 7 crises,
    # Ormuz jouable, chemin Y sur Suez, prérequis existants, boss ★★★★★.
    from pathlib import Path

    data = json.loads(Path("data/campaign/campaign.json").read_text(encoding="utf-8"))
    camp = campaign_mod.Campaign.model_validate(data)
    ids = [c.id for c in camp.chapters]
    assert ids[0] == "sommet-inaugural" and len(ids) == 8
    assert camp.chapter("ormuz").coming_soon is False and camp.chapter("ormuz").requires == []
    assert set(camp.chapter("suez_56").requires) == {"berlin_48", "golfe_90"}  # chemin en Y
    assert set(camp.chapter("able_archer_83").requires) == {"irak_03", "cuba_62"}
    assert camp.chapter("able_archer_83").difficulty == 5  # le boss
    assert camp.chapter("berlin_48").coming_soon is True  # fiche Cowork à venir
    known = set(ids)
    for c in camp.chapters:  # aucun prérequis ne pointe vers un chapitre inexistant
        assert set(c.requires) <= known


def test_unlock_tree_y_paths_and_thresholds():
    # G12-b §4 — arbre : chemins en Y (D exige B ET C) + seuil de score pour les ★★★+.
    tree = campaign_mod.Campaign.model_validate(
        {
            "title": "arbre",
            "unlock_score": 50,
            "chapters": [
                {"id": "a", "crisis_id": "x", "title": "A", "difficulty": 1},
                {"id": "b", "crisis_id": "x", "title": "B", "difficulty": 2, "requires": ["a"]},
                {"id": "c", "crisis_id": "x", "title": "C", "difficulty": 2, "requires": ["a"]},
                {"id": "d", "crisis_id": "x", "title": "D", "difficulty": 3, "requires": ["b", "c"]},  # noqa: E501
                {"id": "e", "crisis_id": "x", "title": "E", "difficulty": 4, "requires": ["d"]},
            ],
        }
    )
    u = campaign_mod.unlocked_chapters
    assert u(tree, {})["a"] is True and u(tree, {})["b"] is False  # A ouvert, B fermé
    opened = u(tree, {"a": 0.0})  # A fini (★ : présence suffit) → B et C s'ouvrent
    assert opened["b"] is True and opened["c"] is True and opened["d"] is False
    assert u(tree, {"a": 0.0, "b": 0.0})["d"] is False  # chemin Y : C manque
    assert u(tree, {"a": 0.0, "b": 0.0, "c": 0.0})["d"] is True  # B ET C finis
    done = {"a": 0.0, "b": 0.0, "c": 0.0}
    assert u(tree, {**done, "d": 40.0})["e"] is False  # D (★★★) fini mais score < 50
    assert u(tree, {**done, "d": 60.0})["e"] is True  # D ≥ 50 → E s'ouvre


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
    assert game["scenario"] == "campaign:c1" and game["mode"] == "campaign"

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
