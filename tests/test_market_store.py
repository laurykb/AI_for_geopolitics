"""Tests de la persistance SQLite du marché (round-trips + filtres)."""

import pytest

from market.models import (
    Account,
    AccountKind,
    Market,
    MarketStatus,
    MarketType,
    Outcome,
    Position,
    Trade,
)
from market.store import SQLiteMarketStore


@pytest.fixture
def store():
    s = SQLiteMarketStore(":memory:")
    yield s
    s.close()


def _market(mid="m1", round_id=1, status=MarketStatus.OPEN):
    return Market(
        id=mid,
        round_id=round_id,
        question="L'Iran va-t-il condamner ?",
        type=MarketType.BINARY,
        status=status,
        b=10.0,
        outcomes=[
            Outcome(id=f"{mid}:0", market_id=mid, label="YES", q=0.0),
            Outcome(id=f"{mid}:1", market_id=mid, label="NO", q=0.0),
        ],
        created_at="2025-01-01T00:00:00+00:00",
    )


def test_account_round_trip_and_update(store):
    store.add_account(Account(id="a1", name="Alice", kind=AccountKind.HUMAN, balance=1000.0))
    got = store.get_account("a1")
    assert got.name == "Alice" and got.kind is AccountKind.HUMAN and got.balance == 1000.0

    got.balance = 950.0
    store.save_account(got)
    assert store.get_account("a1").balance == 950.0
    assert [a.id for a in store.list_accounts()] == ["a1"]
    assert store.get_account("absent") is None


def test_market_round_trip_preserves_outcome_order(store):
    store.add_market(_market())
    got = store.get_market("m1")
    assert got is not None
    assert got.type is MarketType.BINARY and got.status is MarketStatus.OPEN and got.b == 10.0
    assert [o.label for o in got.outcomes] == ["YES", "NO"]  # ordre stable
    assert got.q_vector() == [0.0, 0.0]


def test_save_market_updates_status_resolution_and_q(store):
    store.add_market(_market())
    market = store.get_market("m1")
    market.outcomes[0].q = 5.0
    market.status = MarketStatus.RESOLVED
    market.resolved_outcome = "m1:0"
    store.save_market(market)

    reloaded = store.get_market("m1")
    assert reloaded.q_vector() == [5.0, 0.0]
    assert reloaded.status is MarketStatus.RESOLVED
    assert reloaded.resolved_outcome == "m1:0"


def test_list_markets_filters_by_round_and_status(store):
    store.add_market(_market(mid="m1", round_id=1, status=MarketStatus.OPEN))
    store.add_market(_market(mid="m2", round_id=1, status=MarketStatus.RESOLVED))
    store.add_market(_market(mid="m3", round_id=2, status=MarketStatus.OPEN))

    assert {m.id for m in store.list_markets(round_id=1)} == {"m1", "m2"}
    assert {m.id for m in store.list_markets(status=MarketStatus.OPEN)} == {"m1", "m3"}
    assert {m.id for m in store.list_markets(round_id=1, status=MarketStatus.OPEN)} == {"m1"}


def test_position_upsert(store):
    store.save_position(Position(account_id="a1", outcome_id="m1:0", shares=3.0))
    store.save_position(Position(account_id="a1", outcome_id="m1:0", shares=8.0))  # upsert
    assert store.get_position("a1", "m1:0").shares == 8.0
    assert store.get_position("a1", "absent") is None


def test_list_positions_by_account_and_market(store):
    store.add_market(_market(mid="m1"))
    store.add_market(_market(mid="m2"))
    store.save_position(Position(account_id="a1", outcome_id="m1:0", shares=1.0))
    store.save_position(Position(account_id="a1", outcome_id="m2:0", shares=2.0))
    store.save_position(Position(account_id="a2", outcome_id="m1:1", shares=3.0))

    assert len(store.list_positions(account_id="a1")) == 2
    assert {p.account_id for p in store.list_positions(market_id="m1")} == {"a1", "a2"}
    assert len(store.list_positions(account_id="a1", market_id="m1")) == 1


def test_trades_round_trip_and_filters(store):
    t = Trade(
        id="t1", account_id="a1", market_id="m1", outcome_id="m1:0",
        shares=5.0, cost=2.6, price=0.62, ts="2025-01-01T00:00:00+00:00",
    )
    store.add_trade(t)
    store.add_trade(Trade(**{**t.model_dump(), "id": "t2", "market_id": "m2"}))
    assert [t.id for t in store.list_trades(account_id="a1")] == ["t1", "t2"]
    assert [t.id for t in store.list_trades(market_id="m2")] == ["t2"]
    assert store.list_trades(market_id="m1")[0].cost == 2.6
