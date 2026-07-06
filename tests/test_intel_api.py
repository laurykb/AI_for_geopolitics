"""Tests du renseignement G4 (POST /games/{id}/intel) — offline, MockBackend + RAG seed."""

import json

import pytest
from fastapi.testclient import TestClient

from app import game_api
from app.game_api import get_backend, get_store
from app.main import app
from inference.mock_backend import MockBackend
from storage.game_store import SQLiteGameStore

COUNTRIES = ["usa", "iran", "france"]


@pytest.fixture
def client_store():
    store = SQLiteGameStore(":memory:")
    backend = MockBackend("Analyse privée. MESSAGE: Position commune.")
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_backend] = lambda: backend
    game_api._sessions.clear()
    yield TestClient(app), store
    app.dependency_overrides.clear()
    game_api._sessions.clear()
    store.close()


def _create(client, **kw):
    resp = client.post("/api/games", json={"countries": COUNTRIES, **kw})
    assert resp.status_code == 201, resp.text
    return resp.json()


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


def _intel(client, game_id, **body):
    return client.post(f"/api/games/{game_id}/intel", json=body)


# --- budget ----------------------------------------------------------------------


def test_budget_flows_and_survives_restart(client_store):
    client, _ = client_store
    game = _create(client)
    assert game["intel_budget"] == 100

    resp = _intel(client, game["id"], action="brief")
    assert resp.status_code == 200
    body = resp.json()
    assert body["cost"] == 25 and body["budget"] == 75
    assert body["brief"] and "[source:" in body["brief"]  # brief RAG sourcé

    game_api._sessions.clear()  # restart : le budget vit dans le snapshot
    _play(client, game["id"])  # reconstruit
    assert client.get(f"/api/games/{game['id']}").json()["intel_budget"] == 75


def test_budget_exhaustion_is_400(client_store):
    client, _ = client_store
    game = _create(client)
    for _ in range(4):  # 4 briefs × 25 = 100
        assert _intel(client, game["id"], action="brief").status_code == 200
    resp = _intel(client, game["id"], action="verify", claim="x", speaker="usa")
    assert resp.status_code == 400
    assert "insuffisant" in resp.json()["detail"]


def test_purchases_are_recorded_and_announced(client_store):
    client, store = client_store
    game = _create(client)
    _intel(client, game["id"], action="brief")
    events = _play(client, game["id"])

    frames = [p for n, p in events if n == "intel"]
    assert frames and frames[0]["actions"] == [{"action": "brief"}]  # rédigé, sans contenu
    record = store.list_rounds(game["id"])[0]
    assert record.judge["intel"]["actions"][0]["action"] == "brief"


# --- vérification -----------------------------------------------------------------


def test_verify_corroborates_from_corpus(client_store):
    client, _ = client_store
    game = _create(client)
    resp = _intel(
        client,
        game["id"],
        action="verify",
        claim="La liberté de navigation en mer Rouge est menacée par les attaques.",
        speaker="usa",
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["verdict"] in ("corroboré", "invérifiable")
    if body["verdict"] == "corroboré":
        assert body["source"]


def test_verify_flags_the_deviant(client_store, tmp_path, monkeypatch):
    from simulation import drift_game
    from tests.test_drift_api import TEST_PARAMS

    params_file = tmp_path / "drift.json"
    params_file.write_text(json.dumps(TEST_PARAMS), encoding="utf-8")
    monkeypatch.setenv("DRIFT_PARAMS_PATH", str(params_file))
    drift_game.load_params.cache_clear()

    client, _ = client_store
    game = _create(client, mode="drift")
    deviant = drift_game.assign(game["id"], sorted(COUNTRIES))[0]
    _play(client, game["id"])  # round 1 : un acte constatable au dossier (params de test)

    resp = _intel(
        client, game["id"], action="verify", claim="Nous n'avons rien fait.", speaker=deviant
    )
    assert resp.json()["verdict"] == "non corroboré"  # l'arme anti-manipulateur
    innocent = next(c for c in COUNTRIES if c != deviant)
    resp = _intel(client, game["id"], action="verify", claim="zzz introuvable", speaker=innocent)
    assert resp.json()["verdict"] == "invérifiable"
    drift_game.load_params.cache_clear()


# --- désinformation ----------------------------------------------------------------


def test_disinfo_once_fog_only_and_lands_next_round(client_store):
    client, store = client_store
    classic = _create(client)
    resp = _intel(
        client,
        classic["id"],
        action="disinfo",
        disinfo={"disinformed_country": "iran", "suspected_actor": "usa", "narrative": "faux"},
    )
    assert resp.status_code == 400  # mode fog exigé

    game = _create(client, mode="fog")
    ok = _intel(
        client,
        game["id"],
        action="disinfo",
        disinfo={
            "disinformed_country": "iran",
            "suspected_actor": "france",
            "narrative": "La France masse des forces en Méditerranée.",
        },
    )
    assert ok.status_code == 200
    dup = _intel(
        client,
        game["id"],
        action="disinfo",
        disinfo={"disinformed_country": "usa", "narrative": "bis"},
    )
    assert dup.status_code == 409  # une fois par partie

    events = _play(client, game["id"])
    percs = [p for n, p in events if n == "perceptions"]
    assert percs and "iran" in percs[0]["perceptions"]
    assert "Méditerranée" in percs[0]["perceptions"]["iran"]["narrative"]
    record = store.list_rounds(game["id"])[0]
    assert record.judge["intel"]["disinfo"]["exposed"] in (True, False)  # tirage seedé


# --- brief dissipe le fog du joueur ---------------------------------------------------


def test_brief_clears_next_fog_for_the_player(client_store):
    client, _ = client_store
    game = _create(client, mode="fog", play_as="usa", turn_seconds=2)
    assert _intel(client, game["id"], action="brief").status_code == 200

    fake = "Une flotte iranienne fantôme approche."
    events = _play(
        client,
        game["id"],
        body={
            "event": {"title": "Incident en mer", "severity": 0.5},
            "fog": {"disinformed_country": "usa", "suspected_actor": "iran", "narrative": fake},
        },
    )
    percs = [p for n, p in events if n == "perceptions"]
    # Vue limitée G2 : le joueur ne voit que SA perception — et le brief l'a dissipée.
    assert percs and set(percs[0]["perceptions"]) == {"usa"}
    assert percs[0]["perceptions"]["usa"]["narrative"] != fake
