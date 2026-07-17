"""Éditeur de crises maison (G12-b §5) : CRUD admin + partie de test + jouabilité.

Offline : TestClient + MockBackend + store `:memory:`. Prouve que le JSON est validé par
le MÊME schéma que `data/crises/*.json`, que la crise est propriétaire, et surtout qu'elle
est REJOUABLE (le round la résout via `_resolve_crisis`, comme une crise embarquée).
"""


import pytest
from fastapi.testclient import TestClient

from app import game_api
from app.game_api import get_backend, get_store
from app.main import app
from inference.mock_backend import MockBackend
from storage.game_store import SQLiteGameStore
from tests.sse import play as _play


@pytest.fixture
def client():
    store = SQLiteGameStore(":memory:")
    backend = MockBackend("Analyse privée. MESSAGE: Position commune.")
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_backend] = lambda: backend
    game_api._sessions.clear()
    yield TestClient(app)
    app.dependency_overrides.clear()
    game_api._sessions.clear()
    store.close()


def _crisis(cid="ma_crise", actors=("usa", "iran")):
    return {
        "id": cid,
        "title": "Ma crise maison",
        "description": "Une crise inventée pour le test.",
        "date": "2030-01",
        "events": [
            {
                "id": f"{cid}-1",
                "round_id": 1,
                "event_type": "custom",
                "title": "Événement inaugural",
                "description": "Il se passe quelque chose de grave.",
                "actors": list(actors),
                "location": "Quelque part",
                "severity": 0.6,
                "uncertainty": 0.4,
            }
        ],
        "historical_outcome": {
            "summary": "Résumé historique de test.",
            "escalation": 0.5,
            "measures": ["mesure A", "mesure B"],
        },
    }


def _post(client, crisis, owner="alice"):
    return client.post("/api/admin/crises", json={"owner_id": owner, "crisis": crisis})


# --- création + validation ---------------------------------------------------


def test_create_returns_validated_crisis(client):
    resp = _post(client, _crisis())
    assert resp.status_code == 201
    body = resp.json()
    assert body["id"] == "ma_crise" and body["owner_id"] == "alice"
    assert body["created_at"]  # horodaté à la création
    assert body["crisis"]["events"][0]["title"] == "Événement inaugural"


def test_create_rejects_crisis_without_events(client):
    bad = _crisis()
    bad["events"] = []
    resp = _post(client, bad)
    assert resp.status_code == 400
    assert "round" in resp.json()["detail"]


def test_create_rejects_invalid_schema(client):
    bad = _crisis()
    bad["events"][0]["severity"] = 5.0  # hors [0, 1] — refusé par le schéma Crisis
    resp = _post(client, bad)
    assert resp.status_code == 400


def test_create_rejects_collision_with_embedded_crisis(client):
    resp = _post(client, _crisis(cid="hormuz_energy_shock"))
    assert resp.status_code == 409
    assert "embarquée" in resp.json()["detail"]


# --- listing + propriété -----------------------------------------------------


def test_list_is_owner_scoped(client):
    _post(client, _crisis(cid="crise_alice"), owner="alice")
    _post(client, _crisis(cid="crise_bob"), owner="bob")
    ids_alice = {c["id"] for c in client.get("/api/admin/crises?owner=alice").json()}
    assert ids_alice == {"crise_alice"}
    ids_all = {c["id"] for c in client.get("/api/admin/crises").json()}
    assert {"crise_alice", "crise_bob"} <= ids_all


def test_upsert_replaces_same_id(client):
    _post(client, _crisis(cid="crise_x"))
    updated = _crisis(cid="crise_x")
    updated["title"] = "Titre révisé"
    assert _post(client, updated).status_code == 201
    got = [c for c in client.get("/api/admin/crises").json() if c["id"] == "crise_x"]
    assert len(got) == 1 and got[0]["crisis"]["title"] == "Titre révisé"


def test_cannot_overwrite_another_owners_crisis(client):
    # Garde de propriété : bob ne peut pas écraser (ni s'approprier) la crise d'alice —
    # même invariant que la RLS Supabase, pour que les deux stores concordent.
    _post(client, _crisis(cid="partagee"), owner="alice")
    resp = _post(client, _crisis(cid="partagee"), owner="bob")
    assert resp.status_code == 409
    got = client.get("/api/admin/crises").json()
    owners = {c["id"]: c["owner_id"] for c in got}
    assert owners["partagee"] == "alice"  # inchangé, pas de fuite entre joueurs


# --- suppression -------------------------------------------------------------


def test_delete_only_by_owner(client):
    _post(client, _crisis(cid="crise_x"), owner="alice")
    # un autre joueur ne peut pas supprimer la crise d'alice
    assert client.delete("/api/admin/crises/crise_x?owner=bob").status_code == 404
    assert client.delete("/api/admin/crises/crise_x?owner=alice").status_code == 204
    assert not client.get("/api/admin/crises").json()


# --- partie de test + jouabilité ---------------------------------------------


def test_test_endpoint_starts_unranked_crisis_game(client):
    _post(client, _crisis(cid="crise_x", actors=("usa", "iran")))
    resp = client.post("/api/admin/crises/crise_x/test?owner=alice")
    assert resp.status_code == 201
    game = resp.json()
    assert game["mode"] == "classic"  # RG-2 — « Crisis Replay » = partie classique + crisis_id
    assert game.get("ranked", False) is False  # partie de test => non classée
    assert set(game["countries"]) == {"iran", "usa"}


def test_test_endpoint_unknown_crisis_404(client):
    assert client.post("/api/admin/crises/nope/test?owner=alice").status_code == 404


def test_custom_crisis_is_playable_in_a_round(client):
    """La preuve : un round résout la crise MAISON comme une crise embarquée."""
    _post(client, _crisis(cid="crise_x", actors=("usa", "iran")))
    game = client.post("/api/games", json={"countries": ["usa", "iran"]}).json()
    events = _play(client, game["id"], {"crisis_id": "crise_x"})
    event = next(p for n, p in events if n == "event")["event"]
    assert event["title"] == "Événement inaugural"
    comparison = next(p for n, p in events if n == "comparison")
    assert comparison["crisis_id"] == "crise_x"
