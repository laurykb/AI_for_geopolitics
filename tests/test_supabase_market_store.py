"""Tests du SupabaseMarketStore (PostgREST simulé en mémoire — offline, cf. conftest).

La preuve principale : le **vrai `MarketEngine`** tourne sur ce store (ouvrir un marché,
coter, parier), exactement comme il tourne sur SQLite.
"""

import pytest

from market.engine import MarketEngine
from market.models import (
    AccountKind,
    MarketStatus,
    ResolutionCriterion,
    ResolutionKind,
)
from market.supabase_store import SupabaseMarketStore


@pytest.fixture
def store(fake_postgrest):
    return SupabaseMarketStore(fake_postgrest.client())


def test_from_env_requires_config(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)
    with pytest.raises(RuntimeError, match="SUPABASE_URL"):
        SupabaseMarketStore.from_env()


def test_engine_bets_on_supabase_store(store):
    """Bout-en-bout : compte, marché binaire, pari LMSR — tout persiste via PostgREST."""
    engine = MarketEngine(store)
    account = engine.create_account("alice", kind=AccountKind.HUMAN)
    market = engine.open_binary_market(round_id=1, question="Utopie finale ?", b=50.0)

    yes = market.outcomes[0]
    quote = engine.quote(market.id, yes.id, 10.0)
    trade = engine.place_bet(account.id, market.id, yes.id, 10.0)
    assert trade.cost == pytest.approx(quote.cost)

    # Tout relu depuis le store : solde débité, q déplacé, position et trade présents.
    assert store.get_account(account.id).balance == pytest.approx(1000.0 - trade.cost)
    fresh = store.get_market(market.id)
    assert [o.label for o in fresh.outcomes] == ["YES", "NO"]  # ordre d'ouverture conservé
    assert fresh.outcomes[0].q == pytest.approx(10.0)
    assert store.get_position(account.id, yes.id).shares == pytest.approx(10.0)
    assert len(store.list_trades(market_id=market.id)) == 1


def test_market_criterion_roundtrip(store):
    engine = MarketEngine(store)
    criterion = ResolutionCriterion(kind=ResolutionKind.TRAJECTORY)
    market = engine.open_binary_market(
        round_id=3, question="ΔU > 0 ?", b=25.0, criterion=criterion
    )
    fresh = store.get_market(market.id)
    assert fresh.criterion is not None and fresh.criterion.kind is ResolutionKind.TRAJECTORY
    assert store.get_market("absent") is None


def test_list_markets_filters(store):
    engine = MarketEngine(store)
    m1 = engine.open_binary_market(round_id=1, question="a", b=10.0)
    engine.open_binary_market(round_id=2, question="b", b=10.0)

    m1.status = MarketStatus.RESOLVED
    m1.resolved_outcome = m1.outcomes[0].id
    store.save_market(m1)

    assert [m.question for m in store.list_markets()] == ["a", "b"]
    assert [m.id for m in store.list_markets(round_id=1)] == [m1.id]
    assert [m.id for m in store.list_markets(status=MarketStatus.RESOLVED)] == [m1.id]
    assert store.list_markets(round_id=1, status=MarketStatus.OPEN) == []
    assert store.get_market(m1.id).resolved_outcome == m1.outcomes[0].id


def test_positions_filtered_by_market(store):
    """La jointure position↔marché se fait côté client (deux selects)."""
    engine = MarketEngine(store)
    alice = engine.create_account("alice")
    m1 = engine.open_binary_market(round_id=1, question="a", b=50.0)
    m2 = engine.open_binary_market(round_id=1, question="b", b=50.0)
    engine.place_bet(alice.id, m1.id, m1.outcomes[0].id, 5.0)
    engine.place_bet(alice.id, m2.id, m2.outcomes[1].id, 3.0)

    only_m1 = store.list_positions(market_id=m1.id)
    assert [p.outcome_id for p in only_m1] == [m1.outcomes[0].id]
    assert len(store.list_positions(account_id=alice.id)) == 2

    # Upsert de position : re-parier sur la même issue remplace la ligne.
    engine.place_bet(alice.id, m1.id, m1.outcomes[0].id, 2.0)
    assert store.get_position(alice.id, m1.outcomes[0].id).shares == pytest.approx(7.0)
    assert len(store.list_positions(account_id=alice.id)) == 2


def test_game_id_link_roundtrip(store):
    engine = MarketEngine(store)
    linked = engine.open_binary_market(
        round_id=1, game_id="game42", question="Utopie ?", b=50.0
    )
    engine.open_binary_market(round_id=1, question="autre", b=50.0)

    assert store.get_market(linked.id).game_id == "game42"
    assert [m.id for m in store.list_markets(game_id="game42")] == [linked.id]
    assert store.list_markets(game_id="inconnu") == []
