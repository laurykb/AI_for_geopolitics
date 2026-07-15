"""Tests API du mode deadline / ultimatum (CC-11/G21) — offline, MockBackend + :memory:.

Scénarios de la spec : fiche avec deadline → conséquence au round k+1 si demande non
satisfaite (et pas sinon) ; décret GM en deux champs ; métriques taguées `sous_ultimatum` ;
section différentielle au bilan ; crise sans deadline strictement inchangée (rétro-compat).
"""

import json

import pytest
from fastapi.testclient import TestClient

from app import game_api
from app.game_api import get_backend, get_store
from app.main import app
from inference.mock_backend import MockBackend
from storage.game_store import SQLiteGameStore

# Fiche de crise scriptée sur 3 rounds, ultimatum à échéance au round 2.
CRISIS_WITH_DEADLINE = {
    "id": "cuba-test",
    "title": "Crise test avec ultimatum",
    "description": "Fiche de test G21",
    "events": [
        {
            "id": "e1",
            "round_id": 1,
            "event_type": "crisis",
            "title": "Blocus naval",
            "actors": ["usa", "iran"],
        },
        {
            "id": "e2",
            "round_id": 2,
            "event_type": "crisis",
            "title": "Le blocus se resserre",
            "actors": ["usa", "iran"],
        },
        {
            "id": "e3",
            "round_id": 3,
            "event_type": "crisis",
            "title": "Aube incertaine",
            "actors": ["usa", "iran"],
        },
    ],
    "deadline": {
        "round": 2,
        "demand": "retrait des missiles",
        "consequence": {"classe": "violente", "cible": "usa"},
    },
}


class SatisfiedJudgeBackend(MockBackend):
    """Constate « demande satisfaite » sur le verdict d'ultimatum ; défaut sinon."""

    def generate(self, prompt, *, system=None, **kw):
        result = super().generate(prompt, system=system, **kw)
        if "demand_satisfied" in prompt:
            return result.model_copy(
                update={"text": json.dumps({"escalation": 0.3, "demand_satisfied": True})}
            )
        return result


def _make_client(backend):
    store = SQLiteGameStore(":memory:")
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_backend] = lambda: backend
    game_api._sessions.clear()
    return TestClient(app)


@pytest.fixture
def client():
    """Juge muet sur l'ultimatum (JSON invalide) → demande réputée NON satisfaite."""
    yield _make_client(MockBackend("Analyse privée. MESSAGE: Position commune."))
    app.dependency_overrides.clear()
    game_api._sessions.clear()


@pytest.fixture
def satisfied_client():
    yield _make_client(SatisfiedJudgeBackend("Analyse privée. MESSAGE: Position commune."))
    app.dependency_overrides.clear()
    game_api._sessions.clear()


def _create(client, **kw):
    resp = client.post("/api/games", json=kw)
    assert resp.status_code == 201
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


def _register_crisis(client, crisis=CRISIS_WITH_DEADLINE):
    resp = client.post("/api/admin/crises", json={"owner_id": "tester", "crisis": crisis})
    assert resp.status_code == 201
    return resp.json()["id"]


def _crisis_game(client, **kw):
    crisis_id = _register_crisis(client)
    game = _create(client, countries=["usa", "iran"], mode="crisis", **kw)
    return game, crisis_id


# --- fiche avec deadline : expiration → conséquence au round k+1 --------------------


def test_ultimatum_expires_then_consequence_falls(client):
    game, crisis_id = _crisis_game(client)

    # Round 1 : l'ultimatum s'arme (échéance au round 2), le bandeau est nourri.
    events = _play(client, game["id"], body={"crisis_id": crisis_id})
    ultimatum = [p for n, p in events if n == "ultimatum"]
    assert ultimatum and ultimatum[0]["status"] == "armed"
    assert ultimatum[0]["round"] == 2 and ultimatum[0]["in_rounds"] == 1
    assert ultimatum[0]["demand"] == "retrait des missiles"
    deadlines = next(p for n, p in events if n == "deadlines")
    strip = [d for d in deadlines["items"] if d["kind"] == "ultimatum"]
    assert strip and "retrait des missiles" in strip[0]["label"]
    assert strip[0]["in_rounds"] == 1

    # Round 2 (échéance) : juge muet → non satisfaite → statut « expired ».
    events = _play(client, game["id"], body={"crisis_id": crisis_id})
    statuses = [p["status"] for n, p in events if n == "ultimatum"]
    assert statuses == ["armed", "expired"]
    verdict = next(p for n, p in events if n == "verdict")
    assert verdict["demand_satisfied"] is False
    deadlines = next(p for n, p in events if n == "deadlines")
    strip = [d for d in deadlines["items"] if d["kind"] == "ultimatum"]
    assert strip and "conséquence" in strip[0]["label"]

    # Round 3 : la conséquence EST l'événement du round (elle prime sur la fiche).
    events = _play(client, game["id"], body={"crisis_id": crisis_id})
    event = next(p for n, p in events if n == "event")["event"]
    assert event["event_type"] == "ultimatum"
    assert "retrait des missiles" in event["description"]
    statuses = [p["status"] for n, p in events if n == "ultimatum"]
    assert statuses == ["struck"]

    # Persistance : statuts et tags relus depuis les rounds.
    detail = client.get(f"/api/games/{game['id']}").json()
    judges = [r["judge"] for r in detail["rounds"]]
    assert [j["ultimatum"]["status"] for j in judges] == ["armed", "expired", "struck"]
    assert [j["sous_ultimatum"] for j in judges] == [True, True, False]


def test_ultimatum_satisfied_no_consequence(satisfied_client):
    game, crisis_id = _crisis_game(satisfied_client)
    _play(satisfied_client, game["id"], body={"crisis_id": crisis_id})

    # Round 2 (échéance) : le juge constate la demande satisfaite — menace levée.
    events = _play(satisfied_client, game["id"], body={"crisis_id": crisis_id})
    statuses = [p["status"] for n, p in events if n == "ultimatum"]
    assert statuses == ["armed", "satisfied"]
    assert next(p for n, p in events if n == "verdict")["demand_satisfied"] is True
    deadlines = next(p for n, p in events if n == "deadlines")
    assert not [d for d in deadlines["items"] if d["kind"] == "ultimatum"]

    # Round 3 : la fiche reprend son cours (pas de conséquence).
    events = _play(satisfied_client, game["id"], body={"crisis_id": crisis_id})
    event = next(p for n, p in events if n == "event")["event"]
    assert event["event_type"] == "crisis" and event["title"] == "Aube incertaine"
    assert not [p for n, p in events if n == "ultimatum"]


def test_motion_defers_consequence_and_strip_keeps_the_threat(client):
    """POLISH-1 — une motion en attente diffère la conséquence d'un round (spec G21) :
    pendant le round de motion, la menace doit RESTER au bandeau (DeadlineStrip) au
    lieu de disparaître silencieusement — la conséquence tombe bien au round suivant."""
    crisis_id = _register_crisis(client)
    game = _create(client, countries=["usa", "iran", "france"], mode="crisis")

    _play(client, game["id"], body={"crisis_id": crisis_id})  # round 1 : armé
    _play(client, game["id"], body={"crisis_id": crisis_id})  # round 2 : expiré

    # Une motion se dépose entre les rounds : elle prendra l'événement du round 3.
    resp = client.post(
        f"/api/games/{game['id']}/motions", json={"country": "france", "reason": "dérive"}
    )
    assert resp.status_code == 201

    # Round 3 : la motion EST l'événement (l'API refuse tout body : sans corps, comme
    # le front) — la conséquence est différée, la menace reste visible (trame
    # ultimatum « expired » + entrée du bandeau).
    events = _play(client, game["id"])
    event = next(p for n, p in events if n == "event")["event"]
    assert event["event_type"] == "motion"
    statuses = [p["status"] for n, p in events if n == "ultimatum"]
    assert "expired" in statuses, "la menace différée a disparu du théâtre"
    deadlines = next(p for n, p in events if n == "deadlines")
    strip = [d for d in deadlines["items"] if d["kind"] == "ultimatum"]
    assert strip, "la menace différée a disparu du bandeau d'échéances"
    assert "conséquence" in strip[0]["label"]

    # Round 4 : la conséquence tombe (un round de retard, pas d'oubli).
    events = _play(client, game["id"], body={"crisis_id": crisis_id})
    event = next(p for n, p in events if n == "event")["event"]
    assert event["event_type"] == "ultimatum"
    statuses = [p["status"] for n, p in events if n == "ultimatum"]
    assert statuses == ["struck"]


# --- décret GM : deux champs, échéance séance tenante -------------------------------


def test_decree_ultimatum_judged_same_round(client):
    game = _create(client, countries=["usa", "iran"])
    events = _play(
        client,
        game["id"],
        body={
            "event": {
                "title": "Ultimatum de Washington",
                "ultimatum": {"demand": "retrait immédiat", "classe": "violente"},
            }
        },
    )
    statuses = [p["status"] for n, p in events if n == "ultimatum"]
    assert statuses == ["armed", "expired"]  # échéance CE round, juge muet → expiré
    armed = next(p for n, p in events if n == "ultimatum")
    assert armed["source"] == "decree" and armed["in_rounds"] == 0
    assert armed["consequence"]["classe"] == "violente"

    # Round suivant sans body : la conséquence tombe toute seule.
    events = _play(client, game["id"])
    event = next(p for n, p in events if n == "event")["event"]
    assert event["event_type"] == "ultimatum"
    assert "retrait immédiat" in event["description"]


def test_decree_without_ultimatum_unchanged(client):
    game = _create(client, countries=["usa", "iran"])
    events = _play(client, game["id"], body={"event": {"title": "Simple décret"}})
    assert not [p for n, p in events if n == "ultimatum"]
    detail = client.get(f"/api/games/{game['id']}").json()
    assert detail["rounds"][0]["judge"]["sous_ultimatum"] is False
    assert "ultimatum" not in detail["rounds"][0]["judge"]


# --- rétro-compat : une crise sans deadline ne change en rien ------------------------


def test_crisis_without_deadline_unchanged(client):
    game = _create(client, countries=["iran", "usa"], mode="crisis")
    crisis = client.get("/api/library").json()["crises"][0]
    events = _play(client, game["id"], body={"crisis_id": crisis["id"]})
    names = [n for n, _ in events]
    assert "ultimatum" not in names
    verdict = next(p for n, p in events if n == "verdict")
    assert verdict["demand_satisfied"] is None
    detail = client.get(f"/api/games/{game['id']}").json()
    assert detail["rounds"][0]["judge"]["sous_ultimatum"] is False


# --- bilan : section différentielle avec/sans ----------------------------------------


def test_result_carries_ultimatum_differential(client):
    crisis = dict(CRISIS_WITH_DEADLINE, deadline={
        "round": 1,
        "demand": "retrait des missiles",
        "consequence": {"classe": "violente", "cible": "usa"},
    })
    crisis_id = _register_crisis(client, crisis)
    game = _create(client, countries=["usa", "iran"], mode="crisis", horizon=2)

    _play(client, game["id"], body={"crisis_id": crisis_id})  # round 1 : échéance, expiré
    events = _play(client, game["id"], body={"crisis_id": crisis_id})  # round 2 : conséquence
    over = next(p for n, p in events if n == "game_over")
    diff = over["ultimatum"]
    assert diff["avec"]["rounds"] == 1 and diff["sans"]["rounds"] == 1
    assert diff["avec"]["escalation"] is not None

    detail = client.get(f"/api/games/{game['id']}").json()
    assert detail["result"]["ultimatum"] == diff


def test_result_differential_absent_without_ultimatum(client):
    game = _create(client, countries=["usa", "iran"], horizon=1)
    events = _play(client, game["id"])
    over = next(p for n, p in events if n == "game_over")
    assert over["ultimatum"] is None


# --- restart : l'ultimatum vivant se reconstruit des rounds persistés -----------------


def test_ultimatum_survives_session_rebuild(client):
    game, crisis_id = _crisis_game(client)
    _play(client, game["id"], body={"crisis_id": crisis_id})  # round 1 : armé (échéance 2)

    game_api._sessions.pop(game["id"])  # « restart » : la session process est perdue
    assert client.get(f"/api/games/{game['id']}").json()["resumable"] is True

    events = _play(client, game["id"], body={"crisis_id": crisis_id})  # round 2 : échéance
    statuses = [p["status"] for n, p in events if n == "ultimatum"]
    assert statuses == ["armed", "expired"]

    events = _play(client, game["id"], body={"crisis_id": crisis_id})  # round 3 : conséquence
    event = next(p for n, p in events if n == "event")["event"]
    assert event["event_type"] == "ultimatum"
