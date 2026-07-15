"""Tests CC-6 / G16 — le Défi du jour (« Le Sommet du jour »).

Le même sommet pour tout le monde, dérivé DÉTERMINISTE de la date UTC ; une seule
tentative classée par joueur et par jour (re-run en partie libre non scorée) ; le
score du jour tombe au hook de fin existant ; l'API du défi ne spoile JAMAIS la
crise (ni id, ni titre, ni description — la carte accueil affiche « ??? »)."""

import json

import pytest
from fastapi.testclient import TestClient

from app import game_api
from app.game_api import get_backend, get_store
from app.main import app
from simulation.crisis import load_crises
from simulation.daily import DATE_PREFIX, challenge_for, date_of, today_utc
from simulation.loader import load_world
from storage.game_store import SQLiteGameStore

ROSTER = [
    "usa", "china", "iran", "france", "egypt", "saudi_arabia", "uk",
    "russia", "india", "japan", "germany", "brazil",
]


# --- le module pur ----------------------------------------------------------------


def test_challenge_is_deterministic_for_a_date():
    crises = load_crises()
    a = challenge_for("2026-07-15", crises, ROSTER)
    b = challenge_for("2026-07-15", crises, ROSTER)
    assert a == b  # même date → même défi, pour tout le monde
    assert challenge_for("2026-07-16", crises, ROSTER) != a  # le lendemain, ça change


def test_challenge_shape_summit_of_seven_with_the_actors_seated():
    crises = load_crises()
    ch = challenge_for("2026-07-15", crises, ROSTER)
    assert len(ch.countries) == 7
    assert ch.play_as in ch.countries
    assert ch.horizon == 4
    crisis = next(c for c in crises if c.id == ch.crisis_id)
    actors = {a for e in crisis.events for a in e.actors}
    assert actors <= set(ch.countries)  # la crise se joue avec ses acteurs à la table


def test_challenge_pool_excludes_the_tutorial():
    crises = load_crises()
    picked = {challenge_for(f"2026-07-{d:02d}", crises, ROSTER).crisis_id for d in range(1, 29)}
    assert "sommet_inaugural" not in picked  # le chapitre 0 n'est pas un défi
    assert len(picked) >= 2  # la rotation utilise bien le pool


def test_date_of_scenario():
    assert date_of(f"{DATE_PREFIX}2026-07-15") == "2026-07-15"
    assert date_of("red_sea") is None


# --- l'API ------------------------------------------------------------------------


@pytest.fixture
def client_store():
    store = SQLiteGameStore(":memory:")
    from inference.mock_backend import MockBackend

    backend = MockBackend("Analyse. MESSAGE: Position.")
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_backend] = lambda: backend
    game_api._sessions.clear()
    yield TestClient(app), store
    app.dependency_overrides.clear()
    game_api._sessions.clear()
    store.close()


def _finish(client, game_id: str, horizon: int) -> None:
    """Joue la partie jusqu'au bout (MockBackend) — le hook de fin score le défi."""
    for _ in range(horizon):
        with client.stream("POST", f"/api/games/{game_id}/rounds", json={}) as resp:
            assert resp.status_code == 200
            for _line in resp.iter_lines():
                pass


def test_daily_never_spoils_the_crisis(client_store):
    client, _ = client_store
    resp = client.get("/api/daily")
    assert resp.status_code == 200
    body = json.dumps(resp.json()).lower()
    for crisis in load_crises():  # ni id, ni titre, ni description d'aucune crise
        assert crisis.id.lower() not in body
        if crisis.title:
            assert crisis.title.lower() not in body
    view = resp.json()
    assert len(view["countries"]) == 7 and view["play_as"] in view["countries"]
    assert view["attempted"] is False


def test_one_ranked_attempt_per_day_then_free_reruns(client_store):
    client, store = client_store
    assert client.post("/api/players", json={"id": "p1", "pseudo": "Alice"}).status_code == 201

    first = client.post("/api/daily/start", json={"owner_id": "p1"})
    assert first.status_code == 201
    assert first.json()["ranked"] is True

    again = client.post("/api/daily/start", json={"owner_id": "p1"})
    assert again.status_code == 409  # une seule tentative classée par jour

    rerun = client.post("/api/daily/start", json={"owner_id": "p1", "free": True})
    assert rerun.status_code == 201
    assert rerun.json()["ranked"] is False  # le re-run est une partie libre

    # `attempted` se voit sur la carte accueil.
    assert client.get("/api/daily", params={"player": "p1"}).json()["attempted"] is True
    assert client.get("/api/daily", params={"player": "p2"}).json()["attempted"] is False


def test_daily_round_plays_the_challenge_crisis_imposed_server_side(client_store):
    client, _ = client_store
    client.post("/api/players", json={"id": "p1", "pseudo": "Alice"})
    game = client.post(
        "/api/daily/start", json={"owner_id": "p1", "turn_seconds": 2}
    ).json()
    with client.stream("POST", f"/api/games/{game['id']}/rounds", json={}) as resp:
        assert resp.status_code == 200
        events = []
        name = None
        for line in resp.iter_lines():
            if line.startswith("event: "):
                name = line.removeprefix("event: ")
            elif line.startswith("data: ") and name == "event":
                events.append(json.loads(line.removeprefix("data: ")))
    posted = events[0]["event"]
    challenge = challenge_for(today_utc(), load_crises(), sorted(load_world().countries))
    crisis = next(c for c in load_crises() if c.id == challenge.crisis_id)
    assert posted["title"] == crisis.events[0].title  # la crise du jour, pas le GM


def test_score_falls_once_and_feeds_the_leaderboard(client_store):
    client, store = client_store
    client.post("/api/players", json={"id": "p1", "pseudo": "Alice"})
    # turn_seconds au plancher : le tour humain expire vite (abstention), le test
    # joue les 4 rounds en quelques secondes au lieu de 4 × 90 s.
    game = client.post(
        "/api/daily/start", json={"owner_id": "p1", "turn_seconds": 2}
    ).json()
    _finish(client, game["id"], game["horizon"])
    scores = store.list_daily_scores()
    assert len(scores) == 1 and scores[0].player_id == "p1"
    assert 0.0 <= scores[0].score <= 100.0

    # Le re-run libre ne re-score pas (score unique : la 1re tentative fait foi).
    rerun = client.post(
        "/api/daily/start", json={"owner_id": "p1", "free": True, "turn_seconds": 2}
    ).json()
    _finish(client, rerun["id"], rerun["horizon"])
    assert len(store.list_daily_scores()) == 1

    view = client.get("/api/daily", params={"player": "p1"}).json()
    assert view["leaderboard"][0]["pseudo"] == "Alice"
    assert view["leaderboard"][0]["rank"] == 1
    assert view["my_rank"] == 1
