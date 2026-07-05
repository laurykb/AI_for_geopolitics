"""Tests du bot marché (POST /api/games/{id}/market/bot) — offline, MockBackend.

Le bot forecaster cote le marché « utopie finale » de la partie : il l'ouvre au
besoin (lien `markets.game_id`), prévoit, et parie sur son avantage — ou s'abstient.
"""

import pytest
from fastapi.testclient import TestClient

from app import game_api
from app.game_api import get_backend, get_store
from app.main import app
from app.market_api import get_engine
from inference.mock_backend import MockBackend
from market.engine import STARTING_BALANCE, MarketEngine
from market.models import MarketStatus
from market.store import SQLiteMarketStore
from storage.game_store import SQLiteGameStore


def _setup(backend):
    store = SQLiteGameStore(":memory:")
    engine = MarketEngine(SQLiteMarketStore(":memory:"))
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_backend] = lambda: backend
    app.dependency_overrides[get_engine] = lambda: engine
    game_api._sessions.clear()
    return TestClient(app), store, engine


@pytest.fixture
def confident():
    """Bot sûr de lui : le backend répond une proba YES de 0,85 en JSON valide."""
    yield _setup(MockBackend('{"probability": 0.85}'))
    app.dependency_overrides.clear()
    game_api._sessions.clear()


@pytest.fixture
def illisible():
    """Backend hors format : le forecaster replie sur des probas uniformes."""
    yield _setup(MockBackend("aucune idée, désolé"))
    app.dependency_overrides.clear()
    game_api._sessions.clear()


def _create(client, **kw):
    resp = client.post("/api/games", json={"countries": ["usa", "iran"], **kw})
    assert resp.status_code == 201
    return resp.json()


def test_bot_opens_game_market_and_bets(confident):
    client, store, engine = confident
    game = _create(client)

    resp = client.post(f"/api/games/{game['id']}/market/bot")
    assert resp.status_code == 200
    run = resp.json()
    assert run["opened"] is True
    assert run["probabilities"]["YES"] == pytest.approx(0.85)
    assert run["trade"] is not None and run["trade"]["label"] == "YES"
    assert run["prices"]["YES"] > 0.5  # le pari a déplacé la cote

    # Le marché de la partie existe, lié par game_id, visible via l'API marché.
    markets = client.get(f"/api/markets?game_id={game['id']}").json()
    assert len(markets) == 1 and markets[0]["game_id"] == game["id"]
    assert markets[0]["id"] == run["market_id"]

    # Le compte bot a payé son pari (argent fictif).
    account = client.get(f"/api/accounts/{run['account_id']}").json()
    assert account["kind"] == "bot" and account["balance"] < STARTING_BALANCE


def test_bot_second_pass_reuses_market_and_account(confident):
    client, store, engine = confident
    game = _create(client)
    first = client.post(f"/api/games/{game['id']}/market/bot").json()
    second = client.post(f"/api/games/{game['id']}/market/bot").json()

    assert second["opened"] is False
    assert second["market_id"] == first["market_id"]
    assert second["account_id"] == first["account_id"]
    assert len(engine.store.list_accounts()) == 1  # un seul compte par modèle


def test_bot_abstains_without_edge(illisible):
    client, store, engine = illisible
    game = _create(client)
    run = client.post(f"/api/games/{game['id']}/market/bot").json()

    # Repli uniforme = pas d'avantage sur des prix uniformes -> abstention.
    assert run["opened"] is True
    assert run["probabilities"]["YES"] == pytest.approx(0.5)
    assert run["trade"] is None
    assert engine.store.list_trades() == []


def test_bot_survives_restart_via_snapshot(confident):
    client, store, engine = confident
    game = _create(client)
    game_api._sessions.clear()  # restart : le monde vient du snapshot, sans agents

    resp = client.post(f"/api/games/{game['id']}/market/bot")
    assert resp.status_code == 200 and resp.json()["trade"] is not None


def test_bot_unknown_game_404(confident):
    client, _, _ = confident
    assert client.post("/api/games/nope/market/bot").status_code == 404


def test_bot_409_when_market_resolved(confident):
    client, store, engine = confident
    game = _create(client)
    run = client.post(f"/api/games/{game['id']}/market/bot").json()

    market = engine.store.get_market(run["market_id"])
    market.status = MarketStatus.RESOLVED
    engine.store.save_market(market)
    assert client.post(f"/api/games/{game['id']}/market/bot").status_code == 409
