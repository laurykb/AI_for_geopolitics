"""Tests du récit de partie G6 : pivots par code, épilogue unique, publication."""

import json

import pytest
from fastapi.testclient import TestClient

from app import game_api
from app.game_api import get_backend, get_store
from app.main import app
from inference.mock_backend import MockBackend
from simulation import narrative
from storage.game_store import SQLiteGameStore

COUNTRIES = ["usa", "iran", "france"]

NARRATOR_TEXT = (
    "TITRE: Trois rounds qui ont tenu le détroit\n"
    "Le sommet s'est ouvert dans la méfiance. usa a déclaré : « Position commune. »\n"
    "Au deuxième acte, la tension est montée puis retombée.\n"
    "Épilogue : le conseil a tenu la ligne."
)


@pytest.fixture
def client_store():
    store = SQLiteGameStore(":memory:")
    backend = MockBackend(f"Analyse privée. MESSAGE: Position commune.\n{NARRATOR_TEXT}")
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_backend] = lambda: backend
    game_api._sessions.clear()
    yield TestClient(app), store
    app.dependency_overrides.clear()
    game_api._sessions.clear()
    store.close()


def _events(resp):
    out, name = [], None
    for line in resp.iter_lines():
        if line.startswith("event: "):
            name = line.removeprefix("event: ")
        elif line.startswith("data: "):
            out.append((name, json.loads(line.removeprefix("data: "))))
    return out


def _finished_game(client, store, **kw):
    game = client.post(
        "/api/games", json={"countries": COUNTRIES, "horizon": 2, **kw}
    ).json()
    for _ in range(2):
        with client.stream("POST", f"/api/games/{game['id']}/rounds", json=None) as resp:
            assert resp.status_code == 200
            _events(resp)
    record = store.get_game(game["id"])
    record.status = record.status.__class__("finished")
    store.save_game(record)
    return game


# --- unités narrative ---------------------------------------------------------------


def test_extract_pivots_picks_biggest_swings():
    rounds = [
        {"round_no": 1, "utopia": 0.52, "event_title": "a"},  # +0.02
        {"round_no": 2, "utopia": 0.40, "event_title": "b"},  # −0.12
        {"round_no": 3, "utopia": 0.41, "event_title": "c"},  # +0.01
        {"round_no": 4, "utopia": 0.60, "event_title": "d"},  # +0.19
        {"round_no": 5, "utopia": 0.55, "event_title": "e"},  # −0.05
    ]
    pivots = narrative.extract_pivots(rounds)
    assert [p.round_no for p in pivots] == [2, 4, 5]  # les 3 plus grands |ΔU|, en ordre
    assert pivots[1].delta_u == pytest.approx(0.19, abs=1e-6)


def test_pick_quote_ignores_gm_and_judge():
    entries = [
        {"speaker": "gm", "content": "Un très long événement " * 20},
        {"speaker": "usa", "content": "Nous proposons une trêve."},
        {"speaker": "judge", "content": "Verdict " * 50},
    ]
    quote = narrative.pick_quote(entries)
    assert quote is not None and quote.speaker == "usa"


def test_parse_epilogue_title_bounded():
    title, story = narrative.parse_epilogue("TITRE: " + "x" * 100 + "\nLe récit.")
    assert len(title) <= 60 and story == "Le récit."
    title, _ = narrative.parse_epilogue("")
    assert title  # repli


# --- endpoints -------------------------------------------------------------------------


def test_epilogue_generated_once_and_immutable(client_store):
    client, store = client_store
    game = _finished_game(client, store)

    first = client.post(f"/api/games/{game['id']}/epilogue")
    assert first.status_code == 200
    epilogue = first.json()
    assert epilogue["title"] and len(epilogue["title"]) <= 60
    assert epilogue["story"]
    assert 1 <= len(epilogue["pivots"]) <= 3
    assert epilogue["pivots"][0]["quote"]["speaker"] in COUNTRIES

    second = client.post(f"/api/games/{game['id']}/epilogue").json()
    assert second["generated_at"] == epilogue["generated_at"]  # jamais régénéré
    detail = client.get(f"/api/games/{game['id']}").json()
    assert detail["epilogue"]["title"] == epilogue["title"]


def test_epilogue_requires_finished_game(client_store):
    client, _ = client_store
    game = client.post("/api/games", json={"countries": COUNTRIES}).json()
    assert client.post(f"/api/games/{game['id']}/epilogue").status_code == 409


def test_publish_sets_flag_and_generates(client_store):
    client, store = client_store
    game = _finished_game(client, store)
    assert client.get(f"/api/games/{game['id']}").json()["published"] is False

    resp = client.post(f"/api/games/{game['id']}/publish")
    assert resp.status_code == 200 and resp.json()["published"] is True
    record = store.get_game(game["id"])
    assert record.published is True and record.epilogue is not None
