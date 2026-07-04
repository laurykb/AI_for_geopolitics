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


# --- motions de suspension (R4) --------------------------------------------------

SUSPEND_TEXT = "La plaidoirie n'a pas convaincu ; la menace demeure. VERDICT: SUSPENDRE"


class MotionAwareBackend(MockBackend):
    """Répond SUSPENDRE aux prompts d'arbitrage de motion, sinon la réponse par défaut."""

    def stream_generate(self, prompt, *, system=None, max_tokens=512, temperature=0.7):
        if system and "MOTION DE SUSPENSION" in system:
            yield SUSPEND_TEXT
            return
        yield from super().stream_generate(
            prompt, system=system, max_tokens=max_tokens, temperature=temperature
        )


@pytest.fixture
def motion_client():
    store = SQLiteGameStore(":memory:")
    backend = MotionAwareBackend("Analyse privée. MESSAGE: Position commune.")
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_backend] = lambda: backend
    game_api._sessions.clear()
    yield TestClient(app)
    app.dependency_overrides.clear()
    game_api._sessions.clear()
    store.close()


def _file_motion(client, game_id, country="iran", reason="escalade répétée"):
    return client.post(f"/api/games/{game_id}/motions", json={"country": country, "reason": reason})


def test_motion_flow_upheld(motion_client):
    game = _create(motion_client, countries=["china", "iran", "usa"])
    resp = _file_motion(motion_client, game["id"])
    assert resp.status_code == 201
    assert resp.json() == {"country": "iran", "reason": "escalade répétée", "round_no": 1}
    assert motion_client.get(f"/api/games/{game['id']}").json()["pending_motion"] == resp.json()

    events = _play(motion_client, game["id"])
    names = [n for n, _ in events]
    event = next(p for n, p in events if n == "event")["event"]
    assert event["event_type"] == "motion"
    assert event["actors"] == ["china", "iran", "usa"]  # tout le sommet débat la motion
    assert "motion_token" in names and "motion_verdict" in names
    verdict = next(p for n, p in events if n == "motion_verdict")
    assert verdict["country"] == "iran" and verdict["upheld"] is True
    assert "SUSPENDRE" in verdict["reasoning"]
    # la trajectoire encaisse l'issue sur A2 (agentivité humaine)
    trajectory = next(p for n, p in events if n == "trajectory")["state"]
    assert "Motion de suspension confirmée" in trajectory["explanation"]

    detail = motion_client.get(f"/api/games/{game['id']}").json()
    assert detail["suspended"] == ["iran"] and detail["pending_motion"] is None
    assert detail["rounds"][0]["judge"]["suspension"]["upheld"] is True
    judge_entries = [t for t in detail["rounds"][0]["transcript"] if t["speaker"] == "judge"]
    assert any("Motion contre iran" in t["content"] for t in judge_entries)
    # pas de nouvelle motion contre un pays déjà suspendu
    assert _file_motion(motion_client, game["id"], country="iran").status_code == 400


def test_suspension_lasts_exactly_one_round(motion_client):
    game = _create(motion_client, countries=["china", "iran", "usa"])
    _file_motion(motion_client, game["id"])
    _play(motion_client, game["id"])  # round 1 : la motion est débattue et confirmée

    events = _play(motion_client, game["id"])  # round 2 : l'iran est au banc
    assert next(p for n, p in events if n == "suspended") == {"countries": ["iran"]}
    part = next(p for n, p in events if n == "participation")
    assert "iran" not in part["spoke"] and "iran" not in part["silent"]

    events = _play(motion_client, game["id"])  # round 3 : il retrouve son siège
    assert "suspended" not in [n for n, _ in events]
    part = next(p for n, p in events if n == "participation")
    assert "iran" in part["spoke"] or "iran" in part["silent"]


def test_motion_rejected_without_verdict_marker(client):
    # MockBackend standard : pas de ligne VERDICT lisible -> repli conservateur = rejet.
    game = _create(client, countries=["china", "iran", "usa"])
    assert _file_motion(client, game["id"]).status_code == 201
    events = _play(client, game["id"])
    verdict = next(p for n, p in events if n == "motion_verdict")
    assert verdict["upheld"] is False
    detail = client.get(f"/api/games/{game['id']}").json()
    assert detail["suspended"] == []
    assert "suspended" not in [n for n, _ in _play(client, game["id"])]


def test_motion_validations(client):
    assert _file_motion(client, "nope").status_code == 404
    duo = _create(client, countries=["iran", "usa"])
    assert _file_motion(client, duo["id"]).status_code == 400  # au moins 3 pays
    game = _create(client, countries=["china", "iran", "usa"])
    assert _file_motion(client, game["id"], country="atlantide").status_code == 400
    assert _file_motion(client, game["id"]).status_code == 201
    assert _file_motion(client, game["id"], country="usa").status_code == 409  # déjà en attente
    resp = client.post(f"/api/games/{game['id']}/rounds", json={"event": {"title": "X"}})
    assert resp.status_code == 400  # la motion constitue l'événement du prochain round
    game_api._sessions.clear()  # session perdue -> relecture seule
    assert _file_motion(client, game["id"]).status_code == 409


# --- modes de jeu (R4 : fog, crisis, escalation) ---------------------------------


def test_library_lists_fog_and_crises(client):
    lib = client.get("/api/library").json()
    assert lib["fog"] and lib["crises"]
    assert all(s["id"] and s["title"] for s in lib["fog"])
    assert all(0.0 <= c["historical_escalation"] <= 1.0 for c in lib["crises"])


def test_fog_round_emits_perceptions(client):
    game = _create(client, countries=["iran", "usa"], mode="fog")
    fog_id = client.get("/api/library").json()["fog"][0]["id"]
    events = _play(client, game["id"], body={"fog_id": fog_id})
    perceptions = next(p for n, p in events if n == "perceptions")["perceptions"]
    assert set(perceptions) == {"iran", "usa"}
    assert all(0.0 <= p["confidence"] <= 1.0 for p in perceptions.values())
    detail = client.get(f"/api/games/{game['id']}").json()
    assert set(detail["rounds"][0]["judge"]["perceptions"]) == {"iran", "usa"}


def test_human_event_with_authored_fog(client):
    game = _create(client, countries=["iran", "usa"], mode="fog")
    body = {
        "event": {"title": "Sabotage nocturne", "actors": ["usa"]},
        "fog": {
            "uninformed": ["iran"],
            "disinformed_country": "usa",
            "suspected_actor": "iran",
            "narrative": "Des traces mènent vers l'Iran.",
        },
    }
    events = _play(client, game["id"], body=body)
    perceptions = next(p for n, p in events if n == "perceptions")["perceptions"]
    assert perceptions["iran"]["confidence"] <= 0.1  # pas au courant
    assert perceptions["usa"]["suspected_actor"] == "iran"  # désinformé


def test_crisis_round_emits_comparison(client):
    game = _create(client, countries=["iran", "usa"], mode="crisis")
    crisis = client.get("/api/library").json()["crises"][0]
    events = _play(client, game["id"], body={"crisis_id": crisis["id"]})
    event = next(p for n, p in events if n == "event")["event"]
    assert event["round_id"] == 1  # l'événement de la crise est re-daté pour la partie
    comparison = next(p for n, p in events if n == "comparison")
    assert comparison["crisis_id"] == crisis["id"]
    assert comparison["label"] in {"plus escaladé", "moins escaladé", "conforme"}
    assert comparison["historical_escalation"] == crisis["historical_escalation"]
    detail = client.get(f"/api/games/{game['id']}").json()
    assert detail["rounds"][0]["judge"]["comparison"]["label"] == comparison["label"]


def test_escalation_mode_emits_ladder(client):
    game = _create(client, countries=["iran", "usa"], mode="escalation")
    assert game["mode"] == "escalation"
    events = _play(client, game["id"])
    ladder = next(p for n, p in events if n == "ladder")
    assert 0 <= ladder["reached"] <= 9 and ladder["reached_label"]
    assert set(ladder["ceilings"]) == {"iran", "usa"}
    assert all(0 <= c["rung"] <= 9 and c["label"] for c in ladder["ceilings"].values())
    detail = client.get(f"/api/games/{game['id']}").json()
    assert detail["rounds"][0]["judge"]["ladder"]["reached"] == ladder["reached"]


def test_classic_round_has_no_mode_frames(client):
    game = _create(client, countries=["iran", "usa"])
    names = [n for n, _ in _play(client, game["id"])]
    assert not {"perceptions", "ladder", "comparison", "suspended"} & set(names)


def test_round_mode_validations(client):
    game = _create(client, countries=["iran", "usa"])
    post = lambda body: client.post(f"/api/games/{game['id']}/rounds", json=body)  # noqa: E731
    assert post({"fog_id": "nope"}).status_code == 400
    assert post({"crisis_id": "nope"}).status_code == 400
    assert post({"fog": {"uninformed": ["iran"]}}).status_code == 400  # fog humain sans event
    fog_id = client.get("/api/library").json()["fog"][0]["id"]
    assert post({"fog_id": fog_id, "event": {"title": "X"}}).status_code == 400
    crisis_id = client.get("/api/library").json()["crises"][0]["id"]
    assert post({"crisis_id": crisis_id, "fog_id": fog_id}).status_code == 400
    # les validations n'ont pas consommé le verrou : un round normal passe ensuite
    assert _play(client, game["id"])[-1][0] == "done"


class ExplodingStore(SQLiteGameStore):
    """`add_round` casse une fois : simule une panne en plein flux SSE."""

    def __init__(self):
        super().__init__(":memory:")
        self.exploded = False

    def add_round(self, round_):
        if not self.exploded:
            self.exploded = True
            raise RuntimeError("panne simulée")
        super().add_round(round_)


def test_round_failure_emits_error_frame_and_releases_lock():
    store = ExplodingStore()
    backend = MockBackend("Analyse privée. MESSAGE: Position commune.")
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_backend] = lambda: backend
    game_api._sessions.clear()
    try:
        client = TestClient(app)
        game = _create(client, countries=["usa", "iran"])

        events = _play(client, game["id"])
        names = [n for n, _ in events]
        assert names[-1] == "error" and "done" not in names
        assert "panne simulée" in events[-1][1]["detail"]

        # Verrou relâché : un nouveau round passe (la panne était one-shot).
        events = _play(client, game["id"])
        assert events[-1][0] == "done"
    finally:
        app.dependency_overrides.clear()
        game_api._sessions.clear()
        store.close()


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
