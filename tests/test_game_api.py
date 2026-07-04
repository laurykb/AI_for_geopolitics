"""Tests de l'API de jeu R1 (offline : TestClient + MockBackend + store :memory:)."""

import json

import pytest
from fastapi.testclient import TestClient

from app import game_api
from app.game_api import get_backend, get_store, sse_frame, step_event
from app.main import app
from inference.mock_backend import MockBackend
from simulation.live_round import TokenStep, TurnStartStep
from storage.game_store import SQLiteGameStore


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


def _create(client, **kw):
    resp = client.post("/api/games", json=kw)
    assert resp.status_code == 201
    return resp.json()


def _events(resp) -> list[tuple[str, dict]]:
    """Parse un flux SSE en liste (event, payload)."""
    out, name = [], None
    for line in resp.iter_lines():
        if line.startswith("event: "):
            name = line.removeprefix("event: ")
        elif line.startswith("data: "):
            out.append((name, json.loads(line.removeprefix("data: "))))
    return out


def _play(client, game_id, body=None) -> list[tuple[str, dict]]:
    with client.stream("POST", f"/api/games/{game_id}/rounds", json=body) as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        return _events(resp)


# --- création de partie ------------------------------------------------------


def test_create_game_with_all_countries(client):
    game = _create(client)
    assert game["id"] and game["live"] is True
    assert game["status"] == "running" and game["horizon"] == 5
    assert len(game["countries"]) >= 2


def test_create_game_with_subset(client):
    game = _create(client, countries=["usa", "iran"], horizon=3)
    assert game["countries"] == ["iran", "usa"]
    assert game["horizon"] == 3


def test_create_game_rejects_unknown_country(client):
    resp = client.post("/api/games", json={"countries": ["usa", "atlantide"]})
    assert resp.status_code == 400
    assert "atlantide" in resp.json()["detail"]


def test_create_game_rejects_single_country(client):
    resp = client.post("/api/games", json={"countries": ["usa"]})
    assert resp.status_code == 400


# --- round SSE -----------------------------------------------------------------


def test_round_streams_full_step_sequence(client):
    game = _create(client, countries=["usa", "iran"])
    events = _play(client, game["id"])

    names = [n for n, _ in events]
    assert names[0] == "date" and names[1] == "event"
    assert names[-1] == "done"
    # théâtre : au moins une prise de parole streamée token par token
    assert "turn_start" in names and "token" in names and "message_done" in names
    # arbitrage + observables de fin de round
    for expected in ("participation", "verdict", "communique", "risk", "trajectory", "summary"):
        assert expected in names, f"étape manquante : {expected}"
    assert events[-1][1] == {"round_no": 1}


def test_round_payloads_are_json_shaped(client):
    game = _create(client, countries=["usa", "iran"])
    events = _play(client, game["id"])
    payloads = dict(events)  # dernier payload par nom (suffisant ici)

    assert payloads["event"]["event"]["round_id"] == 1
    token = next(p for n, p in events if n == "token")
    assert set(token) == {"country", "token"}
    assert 0.0 <= payloads["trajectory"]["state"]["utopia"] <= 1.0
    assert 0.0 <= payloads["verdict"]["escalation"] <= 1.0


def test_round_with_human_event_skips_gm(client):
    game = _create(client, countries=["usa", "iran"])
    events = _play(client, game["id"], body={"event": {"title": "Crise décrétée par l'humain"}})
    event = next(p for n, p in events if n == "event")
    assert event["event"]["title"] == "Crise décrétée par l'humain"


def test_round_respects_max_turns(client):
    game = _create(client, countries=["usa", "iran"])
    events = _play(client, game["id"], body={"max_turns": 1})
    assert sum(1 for n, _ in events if n == "turn_start") == 1


def test_round_on_unknown_game_is_404(client):
    assert client.post("/api/games/nope/rounds").status_code == 404


def test_round_without_live_session_is_409(client):
    game = _create(client)
    game_api._sessions.clear()  # simule un redémarrage du process
    resp = client.post(f"/api/games/{game['id']}/rounds")
    assert resp.status_code == 409


# --- persistance + relecture ---------------------------------------------------


def test_get_game_returns_world_rounds_and_transcript(client):
    game = _create(client, countries=["usa", "iran"])
    _play(client, game["id"])

    detail = client.get(f"/api/games/{game['id']}").json()
    assert detail["live"] is True
    assert detail["world"]["current_round"] == 1
    assert len(detail["rounds"]) == 1

    round_ = detail["rounds"][0]
    assert round_["round_no"] == 1
    assert round_["event"]["title"]
    assert "communique" in round_["judge"] and "escalation" in round_["judge"]
    assert round_["trajectory"]["axes"].keys() >= {"A1", "A2"}

    transcript = round_["transcript"]
    speakers = [t["speaker"] for t in transcript]
    assert speakers[0] == "gm" and speakers[-1] == "judge"  # théâtre complet GM -> juge
    assert any(s in {"usa", "iran"} for s in speakers)
    country_turns = [t for t in transcript if t["speaker"] in {"usa", "iran"}]
    assert all(t["content"] for t in country_turns)
    assert all(t["reasoning"] for t in country_turns)  # réflexion privée persistée
    assert [t["seq"] for t in transcript] == list(range(len(transcript)))


def test_rounds_accumulate_and_replay_survives_session_loss(client):
    game = _create(client, countries=["usa", "iran"])
    _play(client, game["id"])
    _play(client, game["id"])

    game_api._sessions.clear()  # redémarrage simulé : relecture seule
    detail = client.get(f"/api/games/{game['id']}").json()
    assert detail["live"] is False and detail["world"] is None
    assert [r["round_no"] for r in detail["rounds"]] == [1, 2]
    assert all(r["transcript"] for r in detail["rounds"])


def test_get_unknown_game_is_404(client):
    assert client.get("/api/games/nope").status_code == 404


def test_list_games(client):
    _create(client)
    _create(client, countries=["usa", "iran"])
    games = client.get("/api/games").json()
    assert len(games) == 2 and all(g["live"] for g in games)


def test_lock_released_after_round(client):
    game = _create(client, countries=["usa", "iran"])
    _play(client, game["id"])
    events = _play(client, game["id"])  # un 2e round passe : le verrou a été relâché
    assert events[-1] == ("done", {"round_no": 2})


# --- unités : sérialisation SSE -------------------------------------------------


def test_step_event_names_and_payloads():
    name, payload = step_event(TokenStep(country="usa", token="bonjour"))
    assert (name, payload) == ("token", {"country": "usa", "token": "bonjour"})
    name, payload = step_event(TurnStartStep(country="iran", model="mistral", pass_no=0))
    assert name == "turn_start"
    assert payload == {"country": "iran", "model": "mistral", "pass_no": 0}


def test_sse_frame_format():
    frame = sse_frame("token", {"country": "usa", "token": "é"})
    assert frame == 'event: token\ndata: {"country": "usa", "token": "é"}\n\n'
