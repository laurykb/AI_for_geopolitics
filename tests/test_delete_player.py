"""Tests G14 backend (§3 Compte) : DELETE /api/players/{id} — les parties publiées
sont conservées ANONYMES (owner_id effacé), tout le reste est purgé (parties privées,
fiche de ligue, historiques LP/XP, crises maison)."""

import pytest
from fastapi.testclient import TestClient

from app import game_api
from app.game_api import get_backend, get_store
from app.main import app
from inference.mock_backend import MockBackend
from storage.game_store import (
    CustomCrisisRecord,
    LpHistoryEntry,
    SQLiteGameStore,
)


@pytest.fixture
def client_store():
    store = SQLiteGameStore(":memory:")
    backend = MockBackend("Analyse. MESSAGE: Position.")
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_backend] = lambda: backend
    game_api._sessions.clear()
    yield TestClient(app), store
    app.dependency_overrides.clear()
    game_api._sessions.clear()
    store.close()


def _create_game(client, owner_id: str) -> str:
    resp = client.post(
        "/api/games", json={"countries": ["usa", "iran"], "owner_id": owner_id}
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def test_delete_player_anonymizes_published_and_purges_the_rest(client_store):
    client, store = client_store
    assert client.post("/api/players", json={"id": "p1", "pseudo": "Alice"}).status_code == 201
    assert client.post("/api/players", json={"id": "p2", "pseudo": "Bob"}).status_code == 201

    published_id = _create_game(client, "p1")
    private_id = _create_game(client, "p1")
    other_id = _create_game(client, "p2")

    # La partie « publiée » l'est par le store (le flux publish exige une partie finie).
    published = store.get_game(published_id)
    published.published = True
    store.save_game(published)

    store.add_lp_history(
        LpHistoryEntry(id="h1", player_id="p1", game_id=private_id, delta=12, ts="t")
    )
    store.upsert_custom_crisis(
        CustomCrisisRecord(
            id="crise-maison",
            owner_id="p1",
            crisis={"id": "crise-maison", "title": "Test"},
            created_at="t",
        )
    )

    resp = client.delete("/api/players/p1")
    assert resp.status_code == 204

    # La fiche de ligue et ses traces disparaissent.
    assert client.get("/api/players/p1").status_code == 404
    assert store.list_lp_history("p1") == []
    assert all(c.owner_id != "p1" for c in store.list_custom_crises())

    # La partie publiée survit, anonyme ; la privée est purgée (record + session).
    survivor = store.get_game(published_id)
    assert survivor is not None and survivor.published is True
    assert survivor.owner_id is None
    assert store.get_game(private_id) is None
    assert private_id not in game_api._sessions
    assert client.get(f"/api/games/{private_id}").status_code == 404

    # Les données des autres joueurs ne bougent pas.
    other = store.get_game(other_id)
    assert other is not None and other.owner_id == "p2"
    assert client.get("/api/players/p2").status_code == 200


def test_delete_unknown_player_is_a_404(client_store):
    client, _ = client_store
    assert client.delete("/api/players/fantome").status_code == 404
