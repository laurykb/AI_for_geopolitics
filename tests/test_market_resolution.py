"""Tests de la résolution des marchés : mappers purs + settle 1/0 + hook ΔUtopie (offline)."""

import pytest

from core.decisions import AgentDecision
from core.events import GeoEvent
from core.risk import RiskScore
from core.rounds import RoundSummary
from market.engine import STARTING_BALANCE, MarketEngine
from market.models import (
    AccountKind,
    MarketStatus,
    MarketType,
    ResolutionCriterion,
    ResolutionKind,
)
from market.resolution import (
    ResolutionError,
    action_label,
    council_label,
    resolve,
    resolve_and_settle,
    settle,
    threshold_label,
    utopia_delta,
)
from market.store import SQLiteMarketStore
from simulation.action_space import ActionType
from simulation.trajectory import TrajectoryState


@pytest.fixture
def engine():
    store = SQLiteMarketStore(":memory:")
    yield MarketEngine(store)
    store.close()


def _summary(decisions):
    return RoundSummary(
        round_id=1,
        event=GeoEvent(id="e", round_id=1, event_type="crisis", title="T"),
        decisions=decisions,
        risk=RiskScore(
            round_id=1, escalation=0.4, economic_disruption=0.2,
            alliance_fracture=0.0, uncertainty=0.0,
        ),
    )


def _decision(country, action, target=None):
    return AgentDecision(country=country, round_id=1, action=action, target=target)


# --- mappers purs ----------------------------------------------------------

def test_action_label_matches_country_action_target():
    summary = _summary([_decision("iran", ActionType.CONDEMN, target="saudi")])
    assert action_label(summary, country="iran", action="condemn", target="saudi") == "YES"
    assert action_label(summary, country="iran", action="condemn") == "YES"  # cible optionnelle
    assert action_label(summary, country="iran", action="condemn", target="usa") == "NO"  # cible ≠
    assert action_label(summary, country="usa", action="condemn") == "NO"  # pays ≠
    assert action_label(summary, country="iran", action="support") == "NO"  # action ≠


def test_threshold_label_on_sign():
    assert threshold_label(0.01) == "YES"
    assert threshold_label(0.0) == "NO"  # strictement > 0
    assert threshold_label(-0.2) == "NO"


def test_council_label_validates_winner():
    assert council_label("china", ["china", "usa"]) == "china"
    with pytest.raises(ResolutionError):
        council_label("iran", ["china", "usa"])


def test_utopia_delta_from_history():
    assert utopia_delta([]) == 0.0
    assert utopia_delta([TrajectoryState.neutral()]) == 0.0  # un seul point -> 0
    a = TrajectoryState(round_id=1, utopia=0.50)
    b = TrajectoryState(round_id=2, utopia=0.55)
    assert utopia_delta([a, b]) == pytest.approx(0.05)
    assert utopia_delta([b, a]) == pytest.approx(-0.05)


# --- dispatch resolve ------------------------------------------------------

def test_resolve_action_market(engine):
    crit = ResolutionCriterion(
        kind=ResolutionKind.ACTION, country="iran", action="condemn", target="saudi"
    )
    market = engine.open_binary_market(
        round_id=1, question="L'Iran condamne-t-il l'Arabie ?", b=10.0, criterion=crit
    )
    yes, no = market.outcomes[0].id, market.outcomes[1].id
    hit = _summary([_decision("iran", ActionType.CONDEMN, target="saudi")])
    miss = _summary([_decision("iran", ActionType.SUPPORT, target="saudi")])
    assert resolve(market, hit) == yes
    assert resolve(market, miss) == no


def test_resolve_trajectory_market_uses_delta_utopia(engine):
    crit = ResolutionCriterion(kind=ResolutionKind.TRAJECTORY)
    market = engine.open_binary_market(
        round_id=1, question="L'indice Utopie va-t-il monter ?", b=10.0,
        type=MarketType.THRESHOLD, criterion=crit,
    )
    yes, no = market.outcomes[0].id, market.outcomes[1].id
    empty = _summary([])
    assert resolve(market, empty, delta_utopia=0.03) == yes
    assert resolve(market, empty, delta_utopia=-0.03) == no


def test_resolve_council_market(engine):
    crit = ResolutionCriterion(kind=ResolutionKind.COUNCIL)
    market = engine.open_market(
        round_id=1, question="Quelle SI gagne le Conseil ?", labels=["china", "usa", "eu"],
        b=10.0, type=MarketType.CATEGORICAL, criterion=crit,
    )
    china = market.outcomes[0].id
    assert resolve(market, _summary([]), council_winner="china") == china
    with pytest.raises(ResolutionError):
        resolve(market, _summary([]))  # council_winner requis


def test_resolve_requires_criterion(engine):
    market = engine.open_binary_market(round_id=1, question="?", b=10.0)  # sans critère
    with pytest.raises(ResolutionError):
        resolve(market, _summary([]))


def test_criterion_survives_store_round_trip(engine):
    crit = ResolutionCriterion(kind=ResolutionKind.ACTION, country="iran", action="condemn")
    market = engine.open_binary_market(round_id=1, question="?", b=10.0, criterion=crit)
    reloaded = engine.store.get_market(market.id)
    assert reloaded.criterion == crit  # persisté en JSON puis relu


# --- settlement ------------------------------------------------------------

def test_settle_pays_one_per_winning_share_and_zero_to_losers(engine):
    crit = ResolutionCriterion(kind=ResolutionKind.TRAJECTORY)
    market = engine.open_binary_market(
        round_id=1, question="ΔUtopie > 0 ?", b=10.0, criterion=crit
    )
    yes, no = market.outcomes[0].id, market.outcomes[1].id
    winner = engine.create_account("Winner")
    loser = engine.create_account("Loser")
    engine.place_bet(winner.id, market.id, yes, shares=5.0)
    engine.place_bet(loser.id, market.id, no, shares=5.0)
    winner_before = engine.store.get_account(winner.id).balance
    loser_before = engine.store.get_account(loser.id).balance

    market = engine.store.get_market(market.id)  # recharge (q à jour)
    result = resolve_and_settle(engine.store, market, _summary([]), delta_utopia=0.02)

    assert result.winning_outcome == yes
    assert result.payouts == {winner.id: 5.0}  # 1 crédit par part gagnante
    assert engine.store.get_account(winner.id).balance == pytest.approx(winner_before + 5.0)
    assert engine.store.get_account(loser.id).balance == pytest.approx(loser_before)  # 0 au perdant
    resolved = engine.store.get_market(market.id)
    assert resolved.status is MarketStatus.RESOLVED and resolved.resolved_outcome == yes


def test_settle_is_idempotent(engine):
    crit = ResolutionCriterion(kind=ResolutionKind.TRAJECTORY)
    market = engine.open_binary_market(round_id=1, question="?", b=10.0, criterion=crit)
    yes = market.outcomes[0].id
    account = engine.create_account("Alice")
    engine.place_bet(account.id, market.id, yes, shares=4.0)

    market = engine.store.get_market(market.id)
    first = settle(engine.store, market, yes)
    paid = engine.store.get_account(account.id).balance
    assert first.payouts == {account.id: 4.0}

    market = engine.store.get_market(market.id)  # déjà RESOLVED
    second = settle(engine.store, market, yes)
    assert second.already_settled is True
    assert engine.store.get_account(account.id).balance == paid  # pas de double paiement


def test_full_cycle_winner_profits(engine):
    """open -> bets -> resolve(RoundSummary) -> settle : le gagnant est en positif."""
    crit = ResolutionCriterion(
        kind=ResolutionKind.ACTION, country="iran", action="condemn"
    )
    market = engine.open_binary_market(
        round_id=1, question="L'Iran condamne-t-il ?", b=20.0, criterion=crit
    )
    yes = market.outcomes[0].id
    bot = engine.create_account("Bot", kind=AccountKind.BOT)
    engine.place_bet(bot.id, market.id, yes, shares=10.0)

    market = engine.store.get_market(market.id)
    resolve_and_settle(
        engine.store, market, _summary([_decision("iran", ActionType.CONDEMN)])
    )
    # a parié 10 parts YES et YES gagne -> solde final > solde de départ
    assert engine.store.get_account(bot.id).balance > STARTING_BALANCE
