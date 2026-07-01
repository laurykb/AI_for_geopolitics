"""Tests du scoring : P&L, Brier (cas connus), leaderboard (offline)."""

import pytest

from core.events import GeoEvent
from core.risk import RiskScore
from core.rounds import RoundSummary
from market.engine import MarketEngine
from market.models import Account, AccountKind, ResolutionCriterion, ResolutionKind
from market.resolution import resolve_and_settle
from market.scoring import (
    Prediction,
    account_brier,
    brier_score,
    leaderboard,
    pnl,
)
from market.store import SQLiteMarketStore


@pytest.fixture
def engine():
    store = SQLiteMarketStore(":memory:")
    yield MarketEngine(store)
    store.close()


def _summary():
    return RoundSummary(
        round_id=1,
        event=GeoEvent(id="e", round_id=1, event_type="c", title="T"),
        decisions=[],
        risk=RiskScore(
            round_id=1, escalation=0.0, economic_disruption=0.0,
            alliance_fracture=0.0, uncertainty=0.0,
        ),
    )


def _p(prob, result):
    return Prediction(probability=prob, result=result)


# --- Brier sur cas connus --------------------------------------------------

def test_brier_none_when_empty():
    assert brier_score([]) is None


def test_brier_perfect_is_zero():
    assert brier_score([_p(1.0, 1), _p(0.0, 0)]) == pytest.approx(0.0)


def test_brier_worst_is_one():
    assert brier_score([_p(1.0, 0), _p(0.0, 1)]) == pytest.approx(1.0)


def test_brier_uninformed_half_is_quarter():
    assert brier_score([_p(0.5, 1), _p(0.5, 0)]) == pytest.approx(0.25)


def test_brier_single_case():
    assert brier_score([_p(0.7, 1)]) == pytest.approx(0.09)  # (0.7 - 1)^2


# --- P&L -------------------------------------------------------------------

def test_pnl_is_balance_minus_initial():
    assert pnl(Account(id="a", name="A", balance=1200.0, initial_balance=1000.0)) == 200.0
    assert pnl(Account(id="b", name="B", balance=800.0, initial_balance=1000.0)) == -200.0
    # initial_balance auto-rempli = balance -> P&L nul à la création
    assert pnl(Account(id="c", name="C", balance=1000.0)) == 0.0


# --- intégration : prédictions déduites des positions ----------------------

def _resolved_market(engine, winning="YES"):
    """Ouvre un marché seuil et le résout sur YES ou NO."""
    crit = ResolutionCriterion(kind=ResolutionKind.TRAJECTORY)
    market = engine.open_binary_market(round_id=1, question="ΔU>0 ?", b=20.0, criterion=crit)
    return market


def test_account_brier_from_buys_on_resolved_market(engine):
    market = _resolved_market(engine)
    yes = market.outcomes[0].id
    sharp = engine.create_account("Sharp")
    engine.place_bet(sharp.id, market.id, yes, shares=10.0)  # achat YES
    trade_price = engine.store.list_trades(account_id=sharp.id)[0].price

    market = engine.store.get_market(market.id)
    resolve_and_settle(engine.store, market, _summary(), delta_utopia=0.05)  # YES gagne

    # une seule prévision : (prix payé, 1) -> Brier = (price - 1)^2
    assert account_brier(engine.store, sharp.id) == pytest.approx((trade_price - 1.0) ** 2)


def test_open_market_and_sells_are_excluded_from_brier(engine):
    market = _resolved_market(engine)
    yes = market.outcomes[0].id
    trader = engine.create_account("Trader")
    engine.place_bet(trader.id, market.id, yes, shares=6.0)
    engine.place_bet(trader.id, market.id, yes, shares=-6.0)  # vente : exclue

    # marché encore ouvert -> aucune prévision comptée
    assert account_brier(engine.store, trader.id) is None

    market = engine.store.get_market(market.id)
    resolve_and_settle(engine.store, market, _summary(), delta_utopia=0.05)
    # après résolution : seul l'achat compte (1 prévision), pas la vente
    preds = engine.store.list_trades(account_id=trader.id)
    assert len([t for t in preds if t.shares > 0]) == 1
    assert account_brier(engine.store, trader.id) is not None


# --- leaderboard -----------------------------------------------------------

def test_leaderboard_sorted_by_pnl_desc(engine):
    market = _resolved_market(engine)
    yes, no = market.outcomes[0].id, market.outcomes[1].id
    winner = engine.create_account("Winner")
    loser = engine.create_account("Loser", kind=AccountKind.BOT)
    engine.place_bet(winner.id, market.id, yes, shares=10.0)
    engine.place_bet(loser.id, market.id, no, shares=10.0)

    market = engine.store.get_market(market.id)
    resolve_and_settle(engine.store, market, _summary(), delta_utopia=0.05)  # YES gagne

    board = leaderboard(engine.store)
    assert [e.name for e in board] == ["Winner", "Loser"]  # trié par P&L décroissant
    assert board[0].pnl > 0 and board[0].pnl > board[1].pnl
    assert board[1].kind is AccountKind.BOT
    # le gagnant a parié sur la bonne issue -> Brier bas ; le perdant -> Brier haut
    assert board[0].brier is not None and board[1].brier is not None
    assert board[0].brier < board[1].brier


def test_leaderboard_brier_none_without_resolved_bets(engine):
    engine.create_account("Idle")
    board = leaderboard(engine.store)
    assert board[0].brier is None and board[0].pnl == 0.0
