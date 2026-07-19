"""Tests CC-5 / G10 — le chapitre 0 « Le Sommet inaugural » (tutoriel scripté).

Le chapitre 0 est une partie normale paramétrée : crise scriptée de 3 événements
(patron crise existant), difficulté Débutant forcée (imperdable : amplitude plafonnée),
ouvert d'entrée, marqué `tutorial` pour que le front lance le guidage (TourProvider)."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import game_api
from app.game_api import get_backend, get_store
from app.main import app
from inference.mock_backend import MockBackend
from simulation import campaign as campaign_mod
from simulation.crisis import load_crises
from storage.game_store import SQLiteGameStore
from tests.sse import events as _events

TUTORIAL_CHAPTER = "sommet-inaugural"
TUTORIAL_CRISIS = "sommet_inaugural"


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


def test_campaign_declares_the_tutorial_chapter_first():
    data = json.loads(Path("data/campaign/campaign.json").read_text(encoding="utf-8"))
    camp = campaign_mod.Campaign.model_validate(data)
    ch = camp.chapter(TUTORIAL_CHAPTER)
    assert camp.chapters[0].id == TUTORIAL_CHAPTER  # le chapitre 0 ouvre l'ère
    assert ch is not None and ch.tutorial is True
    assert ch.requires == [] and ch.coming_soon is False  # accessible d'entrée
    assert ch.difficulty == 1 and ch.horizon == 3 and ch.mode == "classic"
    assert ch.crisis_id == TUTORIAL_CRISIS
    assert len(ch.countries) >= 3  # une motion doit pouvoir se débattre
    # Les autres chapitres ne sont PAS des tutoriels (défaut du champ).
    assert all(not c.tutorial for c in camp.chapters if c.id != TUTORIAL_CHAPTER)


def test_tutorial_crisis_is_scripted_on_three_rounds():
    crises = {c.id: c for c in load_crises()}
    crisis = crises[TUTORIAL_CRISIS]
    assert [e.round_id for e in crisis.events] == [1, 2, 3]  # 3 rounds scriptés
    data = json.loads(Path("data/campaign/campaign.json").read_text(encoding="utf-8"))
    cast = set(campaign_mod.Campaign.model_validate(data).chapter(TUTORIAL_CHAPTER).countries)
    for event in crisis.events:  # chaque événement parle du casting du chapitre
        assert set(event.actors) <= cast


def test_start_tutorial_is_a_beginner_game_and_flag_is_exposed(client_store):
    client, store = client_store
    view = client.get("/api/campaign").json()
    ch = next(c for c in view["chapters"] if c["id"] == TUTORIAL_CHAPTER)
    assert ch["tutorial"] is True and ch["unlocked"] is True

    game = client.post(f"/api/campaign/{TUTORIAL_CHAPTER}/start")
    assert game.status_code == 201
    body = game.json()
    assert body["horizon"] == 3
    # Imperdable : la difficulté Débutant plafonne l'amplitude des verdicts.
    assert store.get_game(body["id"]).difficulty == "beginner"
    assert body["play_as"] == "france"  # le tutoriel fait réellement parler et voter


def test_tutorial_keeps_the_guest_owner_and_human_delegation(client_store):
    client, store = client_store
    game = client.post(
        f"/api/campaign/{TUTORIAL_CHAPTER}/start",
        json={"owner_id": "guest_demo", "play_as": "france"},
    )

    assert game.status_code == 201
    body = game.json()
    record = store.get_game(body["id"])
    assert record.owner_id == "guest_demo"
    assert body["play_as"] == "france"
    assert body["role"] == "player"


def test_scripted_crisis_advances_one_event_per_round(client_store):
    client, _ = client_store
    game = client.post(f"/api/campaign/{TUTORIAL_CHAPTER}/start").json()
    crisis = {c.id: c for c in load_crises()}[TUTORIAL_CRISIS]

    for round_no in (1, 2):  # le script avance avec les rounds (plus de events[0] figé)
        with client.stream(
            "POST",
            f"/api/games/{game['id']}/rounds",
            json={"crisis_id": TUTORIAL_CRISIS},
        ) as resp:
            assert resp.status_code == 200
            events = _events(resp)
        posted = next(p["event"] for name, p in events if name == "event")
        assert posted["title"] == crisis.events[round_no - 1].title
        assert posted["round_id"] == round_no
