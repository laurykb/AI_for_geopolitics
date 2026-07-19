"""Tests de l'API FastAPI du marché (offline, TestClient + moteur :memory: injecté)."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.market_api import get_engine
from market.engine import STARTING_BALANCE, MarketEngine
from market.store import SQLiteMarketStore


@pytest.fixture
def client():
    store = SQLiteMarketStore(":memory:")
    engine = MarketEngine(store)
    app.dependency_overrides[get_engine] = lambda: engine
    yield TestClient(app)
    app.dependency_overrides.clear()
    store.close()


def _open_trajectory_market(client, round_id=1):
    resp = client.post(
        "/api/markets",
        json={
            "round_id": round_id,
            "question": "L'indice Utopie va-t-il monter ?",
            "b": 20.0,
            "type": "threshold",
            "criterion": {"kind": "trajectory"},
        },
    )
    assert resp.status_code == 201
    return resp.json()


def _account(client, name="Alice", **kw):
    resp = client.post("/api/accounts", json={"name": name, **kw})
    assert resp.status_code == 201
    return resp.json()


def _bet(client, account, market, outcome, shares):
    return client.post(
        "/api/bet",
        json={
            "account_id": account["id"],
            "market_id": market["id"],
            "outcome_id": outcome,
            "shares": shares,
        },
    )


# --- marchés + prix --------------------------------------------------------

def test_open_list_and_detail_market_with_prices(client):
    market = _open_trajectory_market(client)
    assert [o["label"] for o in market["outcomes"]] == ["YES", "NO"]
    assert sum(o["price"] for o in market["outcomes"]) == pytest.approx(1.0)
    assert all(o["price"] == pytest.approx(0.5) for o in market["outcomes"])  # q=0 -> 50/50

    listed = client.get("/api/markets", params={"round_id": 1}).json()
    assert [m["id"] for m in listed] == [market["id"]]

    detail = client.get(f"/api/markets/{market['id']}").json()
    assert detail["question"].startswith("L'indice Utopie") and detail["volume"] == 0.0


def test_get_unknown_market_404(client):
    assert client.get("/api/markets/absent").status_code == 404


# --- comptes ---------------------------------------------------------------

def test_create_and_get_account(client):
    account = _account(client)
    assert account["balance"] == STARTING_BALANCE
    view = client.get(f"/api/accounts/{account['id']}").json()
    assert view["pnl"] == 0.0 and view["positions"] == []
    assert view["kind"] == "human"


def test_get_unknown_account_404(client):
    assert client.get("/api/accounts/absent").status_code == 404


# --- paris -----------------------------------------------------------------

def test_bet_debits_account_moves_price_and_records_position(client):
    market = _open_trajectory_market(client)
    yes = market["outcomes"][0]["id"]
    account = _account(client)
    trade = _bet(client, account, market, yes, 10.0).json()
    assert trade["cost"] > 0 and trade["shares"] == 10.0

    view = client.get(f"/api/accounts/{account['id']}").json()
    assert view["balance"] == pytest.approx(STARTING_BALANCE - trade["cost"])
    assert view["pnl"] == pytest.approx(-trade["cost"])
    assert len(view["positions"]) == 1 and view["positions"][0]["label"] == "YES"

    updated = client.get(f"/api/markets/{market['id']}").json()
    prices = {o["label"]: o["price"] for o in updated["outcomes"]}
    assert prices["YES"] > 0.5 > prices["NO"]  # acheter YES le fait monter
    assert updated["volume"] == pytest.approx(10.0)


def test_bet_insufficient_balance_returns_400(client):
    market = _open_trajectory_market(client)
    yes = market["outcomes"][0]["id"]
    account = _account(client, name="Poor", balance=1.0)
    assert _bet(client, account, market, yes, 50.0).status_code == 400


def test_bet_unknown_market_returns_404(client):
    account = _account(client)
    resp = client.post(
        "/api/bet",
        json={"account_id": account["id"], "market_id": "absent", "outcome_id": "x", "shares": 1.0},
    )
    assert resp.status_code == 404


def test_market_payloads_are_bounded_and_finite(client):
    assert client.post("/api/accounts", json={"name": "x", "balance": 1001}).status_code == 422
    assert client.post("/api/accounts", json={"name": "x" * 81}).status_code == 422
    assert (
        client.post(
            "/api/markets",
            json={"round_id": 1, "question": "q" * 501, "b": 20, "labels": ["YES", "NO"]},
        ).status_code
        == 422
    )
    market = _open_trajectory_market(client)
    account = _account(client)
    assert _bet(client, account, market, market["outcomes"][0]["id"], 1001).status_code == 422


def test_api_rejects_naked_short_sale(client):
    market = _open_trajectory_market(client)
    account = _account(client)
    response = _bet(client, account, market, market["outcomes"][0]["id"], -5)
    assert response.status_code == 400
    assert "position insuffisante" in response.json()["detail"]


# --- résolution + leaderboard ----------------------------------------------

def test_resolve_trajectory_round_settles_and_ranks(client):
    market = _open_trajectory_market(client)
    yes, no = market["outcomes"][0]["id"], market["outcomes"][1]["id"]
    winner = _account(client, name="Winner")
    loser = _account(client, name="Loser")
    _bet(client, winner, market, yes, 10.0)
    _bet(client, loser, market, no, 10.0)

    resolved = client.post("/api/rounds/1/resolve", json={"delta_utopia": 0.05})
    assert resolved.status_code == 200
    results = resolved.json()
    assert results[0]["winning_outcome"] == yes

    board = client.get("/api/leaderboard").json()
    assert [e["name"] for e in board] == ["Winner", "Loser"]  # trié par P&L
    assert board[0]["pnl"] > 0 and board[0]["brier"] < board[1]["brier"]

    # idempotence : re-résoudre ne repaie pas
    again = client.post("/api/rounds/1/resolve", json={"delta_utopia": 0.05}).json()
    assert again == [] or all(r["already_settled"] for r in again)


def test_resolve_action_market_with_posted_decisions(client):
    market = client.post(
        "/api/markets",
        json={
            "round_id": 2,
            "question": "L'Iran condamne-t-il ?",
            "b": 20.0,
            "criterion": {"kind": "action", "country": "iran", "action": "condemn"},
        },
    ).json()
    yes = market["outcomes"][0]["id"]
    bot = _account(client, name="Bot", kind="bot")
    _bet(client, bot, market, yes, 10.0)

    resolved = client.post(
        "/api/rounds/2/resolve",
        json={"decisions": [{"country": "iran", "action": "condemn"}]},
    ).json()
    assert resolved[0]["winning_outcome"] == yes
    assert client.get(f"/api/accounts/{bot['id']}").json()["pnl"] > 0  # a parié juste


# --- sélection du store par variable d'env (R2) ----------------------------------


def test_get_engine_backend_selection(monkeypatch):
    from app import market_api

    monkeypatch.setattr(market_api, "_engine", None)
    monkeypatch.setenv("STORE_BACKEND", "supabase")
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)
    with pytest.raises(RuntimeError, match="SUPABASE_URL"):
        market_api.get_engine()

    monkeypatch.setenv("STORE_BACKEND", "sqlite")
    engine = market_api.get_engine()
    assert isinstance(engine.store, SQLiteMarketStore)
    monkeypatch.setattr(market_api, "_engine", None)
