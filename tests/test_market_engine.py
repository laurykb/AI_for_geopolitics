"""Tests du moteur de marché : ouverture, cotation, paris au prix LMSR (offline)."""

from concurrent.futures import ThreadPoolExecutor

import pytest

from market import lmsr
from market.engine import (
    STARTING_BALANCE,
    InsufficientBalance,
    InvalidBet,
    MarketClosed,
    MarketEngine,
    UnknownAccount,
    UnknownMarket,
    UnknownOutcome,
)
from market.models import AccountKind, MarketStatus, MarketType
from market.store import SQLiteMarketStore


@pytest.fixture
def engine():
    store = SQLiteMarketStore(":memory:")
    eng = MarketEngine(store)
    yield eng
    store.close()


def _open(engine, b=10.0):
    return engine.open_market(
        round_id=1, question="L'Iran va-t-il condamner ?", labels=["YES", "NO"], b=b
    )


# --- ouverture -------------------------------------------------------------

def test_open_market_starts_uniform(engine):
    market = _open(engine)
    assert market.status is MarketStatus.OPEN
    assert [o.label for o in market.outcomes] == ["YES", "NO"]
    assert market.q_vector() == [0.0, 0.0]
    prices = engine.prices(market.id)
    assert sum(prices.values()) == pytest.approx(1.0)
    assert all(p == pytest.approx(0.5) for p in prices.values())  # q=0 -> 50/50


def test_open_binary_market_is_yes_no(engine):
    market = engine.open_binary_market(
        round_id=2, question="ΔUtopie > 0 ?", b=8.0, type=MarketType.THRESHOLD
    )
    assert market.type is MarketType.THRESHOLD
    assert [o.label for o in market.outcomes] == ["YES", "NO"]


def test_open_market_rejects_bad_inputs(engine):
    with pytest.raises(InvalidBet):
        engine.open_market(round_id=1, question="?", labels=["ONLY"], b=10.0)
    with pytest.raises(InvalidBet):
        engine.open_market(round_id=1, question="?", labels=["YES", "NO"], b=0.0)


# --- cotation --------------------------------------------------------------

def test_quote_matches_lmsr_and_does_not_mutate(engine):
    market = _open(engine)
    yes = market.outcomes[0].id
    quote = engine.quote(market.id, yes, shares=5.0)
    assert quote.cost == pytest.approx(lmsr.cost_to_trade([0.0, 0.0], 10.0, 0, 5.0))
    assert quote.price_before == pytest.approx(0.5)
    assert quote.price_after > quote.price_before  # acheter YES le fait monter
    # la cotation n'exécute rien : q inchangé
    assert engine.store.get_market(market.id).q_vector() == [0.0, 0.0]


# --- paris -----------------------------------------------------------------

def test_place_bet_debits_exact_lmsr_cost_and_moves_price(engine):
    market = _open(engine)
    yes, no = market.outcomes[0].id, market.outcomes[1].id
    account = engine.create_account("Alice")
    assert account.balance == STARTING_BALANCE

    expected_cost = lmsr.cost_to_trade([0.0, 0.0], 10.0, 0, 10.0)
    trade = engine.place_bet(account.id, market.id, yes, shares=10.0)

    assert trade.cost == pytest.approx(expected_cost)
    # le compte est débité du coût exact
    assert engine.store.get_account(account.id).balance == pytest.approx(
        STARTING_BALANCE - expected_cost
    )
    # les prix bougent : YES monte au-dessus de NO
    prices = engine.prices(market.id)
    assert prices[yes] > 0.5 > prices[no]
    assert trade.price == pytest.approx(prices[yes])
    # q et position mis à jour
    assert engine.store.get_market(market.id).q_vector() == [10.0, 0.0]
    assert engine.store.get_position(account.id, yes).shares == 10.0


def test_positions_accumulate_across_bets(engine):
    market = _open(engine)
    yes = market.outcomes[0].id
    account = engine.create_account("Bob")
    engine.place_bet(account.id, market.id, yes, shares=3.0)
    engine.place_bet(account.id, market.id, yes, shares=4.0)
    assert engine.store.get_position(account.id, yes).shares == pytest.approx(7.0)


def test_sell_credits_account_and_round_trip_is_neutral(engine):
    market = _open(engine)
    yes = market.outcomes[0].id
    account = engine.create_account("Carol")

    buy = engine.place_bet(account.id, market.id, yes, shares=6.0)
    balance_after_buy = engine.store.get_account(account.id).balance
    assert balance_after_buy == pytest.approx(STARTING_BALANCE - buy.cost)

    sell = engine.place_bet(account.id, market.id, yes, shares=-6.0)  # revente
    assert sell.cost < 0  # la vente crédite le compte
    # aller-retour neutre : solde et q reviennent au départ
    assert engine.store.get_account(account.id).balance == pytest.approx(STARTING_BALANCE)
    assert engine.store.get_market(market.id).q_vector() == pytest.approx([0.0, 0.0])
    assert engine.store.get_position(account.id, yes).shares == pytest.approx(0.0)


def test_naked_short_sale_is_rejected(engine):
    market = _open(engine)
    account = engine.create_account("NoShort")
    with pytest.raises(InvalidBet, match="position insuffisante"):
        engine.place_bet(account.id, market.id, market.outcomes[0].id, shares=-1.0)
    assert engine.store.get_account(account.id).balance == STARTING_BALANCE


def test_concurrent_bets_do_not_lose_updates(engine):
    market = _open(engine, b=100.0)
    yes = market.outcomes[0].id
    account = engine.create_account("Rafale")

    with ThreadPoolExecutor(max_workers=8) as pool:
        trades = list(
            pool.map(
                lambda _: engine.place_bet(account.id, market.id, yes, shares=1.0),
                range(20),
            )
        )

    assert len(trades) == 20
    assert engine.store.get_market(market.id).q_vector() == pytest.approx([20.0, 0.0])
    assert engine.store.get_position(account.id, yes).shares == pytest.approx(20.0)
    assert len(engine.store.list_trades(market_id=market.id)) == 20
    total_cost = lmsr.cost_to_trade([0.0, 0.0], 100.0, 0, 20.0)
    assert engine.store.get_account(account.id).balance == pytest.approx(
        STARTING_BALANCE - total_cost
    )


def test_insufficient_balance_is_rejected(engine):
    market = _open(engine)
    yes = market.outcomes[0].id
    account = engine.create_account("Poor", balance=1.0)
    with pytest.raises(InsufficientBalance):
        engine.place_bet(account.id, market.id, yes, shares=50.0)  # coût >> 1 crédit
    # rien n'a bougé
    assert engine.store.get_market(market.id).q_vector() == [0.0, 0.0]
    assert engine.store.get_account(account.id).balance == 1.0


def test_bet_on_closed_market_is_rejected(engine):
    market = _open(engine)
    yes = market.outcomes[0].id
    account = engine.create_account("Dan")
    market.status = MarketStatus.LOCKED
    engine.store.save_market(market)
    with pytest.raises(MarketClosed):
        engine.place_bet(account.id, market.id, yes, shares=1.0)


def test_bet_guards(engine):
    market = _open(engine)
    yes = market.outcomes[0].id
    account = engine.create_account("Eve")
    with pytest.raises(InvalidBet):
        engine.place_bet(account.id, market.id, yes, shares=0.0)
    with pytest.raises(UnknownMarket):
        engine.place_bet(account.id, "absent", yes, shares=1.0)
    with pytest.raises(UnknownOutcome):
        engine.place_bet(account.id, market.id, "absent", shares=1.0)
    with pytest.raises(UnknownAccount):
        engine.place_bet("absent", market.id, yes, shares=1.0)


def test_bot_account_kind(engine):
    account = engine.create_account("Forecaster", kind=AccountKind.BOT)
    assert engine.store.get_account(account.id).kind is AccountKind.BOT
