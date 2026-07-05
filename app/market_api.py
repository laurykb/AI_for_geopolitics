"""API FastAPI du marché de prédiction (spéc `docs/spec_market.md` §7).

Endpoints REST pour rendre le marché **jouable** depuis l'UI : lister/détailler les marchés (+ prix
LMSR courants), parier, consulter un compte (solde + positions + P&L), le leaderboard, et résoudre
un round (settlement, le Juge = oracle). S'ajoutent `POST /api/accounts` et `POST /api/markets`
(non listés au §7) pour que l'API soit autonome. Argent **fictif**.

Le moteur est injecté via `get_engine` (singleton process, SQLite `:memory:` par défaut, ou
`MARKET_DB_PATH`). En test, on surcharge la dépendance par un moteur `:memory:` isolé.
"""

from __future__ import annotations

import os
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core.decisions import AgentDecision
from core.events import GeoEvent
from core.risk import RiskScore
from core.rounds import RoundSummary
from market import scoring
from market.engine import (
    InsufficientBalance,
    InvalidBet,
    MarketClosed,
    MarketEngine,
    UnknownAccount,
    UnknownMarket,
    UnknownOutcome,
)
from market.models import (
    Account,
    AccountKind,
    Market,
    MarketStatus,
    MarketType,
    ResolutionCriterion,
    Trade,
)
from market.resolution import ResolutionError, SettlementResult, resolve_and_settle
from market.store import SQLiteMarketStore
from market.supabase_store import SupabaseMarketStore

_engine: MarketEngine | None = None


def get_engine() -> MarketEngine:
    """Moteur de marché du process, sur le store choisi par `STORE_BACKEND` (R2) :
    `sqlite` (défaut — `:memory:`, ou `MARKET_DB_PATH`) ou `supabase` (PostgREST ;
    exige `SUPABASE_URL` + `SUPABASE_SERVICE_KEY`)."""
    global _engine
    if _engine is None:
        if os.getenv("STORE_BACKEND", "sqlite") == "supabase":
            _engine = MarketEngine(SupabaseMarketStore.from_env())
        else:
            _engine = MarketEngine(SQLiteMarketStore(os.getenv("MARKET_DB_PATH", ":memory:")))
    return _engine


router = APIRouter(prefix="/api", tags=["market"])


# --- schémas d'API ------------------------------------------------------------


class OutcomeView(BaseModel):
    id: str
    label: str
    q: float
    price: float  # probabilité implicite courante (LMSR)


class MarketView(BaseModel):
    id: str
    round_id: int
    question: str
    type: MarketType
    status: MarketStatus
    b: float
    resolved_outcome: str | None
    outcomes: list[OutcomeView]
    volume: float  # somme des |parts| échangées


class OpenMarketRequest(BaseModel):
    round_id: int
    question: str
    b: float = Field(gt=0.0)
    labels: list[str] = Field(default_factory=lambda: ["YES", "NO"])
    type: MarketType = MarketType.BINARY
    criterion: ResolutionCriterion | None = None


class CreateAccountRequest(BaseModel):
    name: str
    kind: AccountKind = AccountKind.HUMAN
    balance: float | None = None  # None -> solde de départ par défaut


class BetRequest(BaseModel):
    account_id: str
    market_id: str
    outcome_id: str
    shares: float


class PositionView(BaseModel):
    market_id: str
    outcome_id: str
    label: str
    shares: float


class AccountView(BaseModel):
    id: str
    name: str
    kind: AccountKind
    balance: float
    initial_balance: float
    pnl: float
    positions: list[PositionView]


class DecisionInput(BaseModel):
    country: str
    action: str
    target: str | None = None


class ResolveRequest(BaseModel):
    """Contexte de résolution d'un round (fourni par l'appelant interne, ex. la simulation)."""

    delta_utopia: float = 0.0
    council_winner: str | None = None
    decisions: list[DecisionInput] = Field(default_factory=list)


# --- helpers ------------------------------------------------------------------


def _market_view(engine: MarketEngine, market: Market) -> MarketView:
    prices = engine.prices(market.id)
    volume = sum(abs(t.shares) for t in engine.store.list_trades(market_id=market.id))
    return MarketView(
        id=market.id,
        round_id=market.round_id,
        question=market.question,
        type=market.type,
        status=market.status,
        b=market.b,
        resolved_outcome=market.resolved_outcome,
        outcomes=[
            OutcomeView(id=o.id, label=o.label, q=o.q, price=prices[o.id]) for o in market.outcomes
        ],
        volume=volume,
    )


def _outcome_index(engine: MarketEngine) -> dict[str, tuple[str, str]]:
    """`outcome_id -> (market_id, label)` pour enrichir les positions d'un compte."""
    index: dict[str, tuple[str, str]] = {}
    for market in engine.store.list_markets():
        for outcome in market.outcomes:
            index[outcome.id] = (market.id, outcome.label)
    return index


def _summary_from_decisions(round_id: int, decisions: list[DecisionInput]) -> RoundSummary:
    """RoundSummary minimal pour les mappers de résolution (seules les décisions comptent)."""
    return RoundSummary(
        round_id=round_id,
        event=GeoEvent(
            id=f"r{round_id}", round_id=round_id, event_type="resolve", title="resolve"
        ),
        decisions=[
            AgentDecision(country=d.country, round_id=round_id, action=d.action, target=d.target)
            for d in decisions
        ],
        risk=RiskScore(
            round_id=round_id, escalation=0.0, economic_disruption=0.0,
            alliance_fracture=0.0, uncertainty=0.0,
        ),
    )


# --- routes -------------------------------------------------------------------


@router.get("/markets", response_model=list[MarketView])
def list_markets(
    engine: Annotated[MarketEngine, Depends(get_engine)],
    round_id: int | None = None,
    status: MarketStatus | None = None,
) -> list[MarketView]:
    """Marchés (filtrables par round et statut) + prix LMSR courants."""
    markets = engine.store.list_markets(round_id=round_id, status=status)
    return [_market_view(engine, m) for m in markets]


@router.post("/markets", response_model=MarketView, status_code=201)
def open_market(
    body: OpenMarketRequest, engine: Annotated[MarketEngine, Depends(get_engine)]
) -> MarketView:
    """Ouvre un marché (q=0, prix uniformes)."""
    try:
        market = engine.open_market(
            round_id=body.round_id,
            question=body.question,
            labels=body.labels,
            b=body.b,
            type=body.type,
            criterion=body.criterion,
        )
    except InvalidBet as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _market_view(engine, market)


@router.get("/markets/{market_id}", response_model=MarketView)
def get_market(
    market_id: str, engine: Annotated[MarketEngine, Depends(get_engine)]
) -> MarketView:
    market = engine.store.get_market(market_id)
    if market is None:
        raise HTTPException(status_code=404, detail=f"marché inconnu : {market_id}")
    return _market_view(engine, market)


@router.post("/accounts", response_model=Account, status_code=201)
def create_account(
    body: CreateAccountRequest, engine: Annotated[MarketEngine, Depends(get_engine)]
) -> Account:
    if body.balance is None:
        return engine.create_account(body.name, kind=body.kind)
    return engine.create_account(body.name, kind=body.kind, balance=body.balance)


@router.get("/accounts/{account_id}", response_model=AccountView)
def get_account(
    account_id: str, engine: Annotated[MarketEngine, Depends(get_engine)]
) -> AccountView:
    account = engine.store.get_account(account_id)
    if account is None:
        raise HTTPException(status_code=404, detail=f"compte inconnu : {account_id}")
    initial = account.initial_balance if account.initial_balance is not None else account.balance
    index = _outcome_index(engine)
    positions = [
        PositionView(
            market_id=index.get(p.outcome_id, ("", ""))[0],
            outcome_id=p.outcome_id,
            label=index.get(p.outcome_id, ("", ""))[1],
            shares=p.shares,
        )
        for p in engine.store.list_positions(account_id=account_id)
        if p.shares != 0.0
    ]
    return AccountView(
        id=account.id,
        name=account.name,
        kind=account.kind,
        balance=account.balance,
        initial_balance=initial,
        pnl=scoring.pnl(account),
        positions=positions,
    )


@router.post("/bet", response_model=Trade)
def place_bet(
    body: BetRequest, engine: Annotated[MarketEngine, Depends(get_engine)]
) -> Trade:
    """Exécute un pari au prix LMSR, débite le compte."""
    try:
        return engine.place_bet(body.account_id, body.market_id, body.outcome_id, body.shares)
    except (UnknownMarket, UnknownAccount, UnknownOutcome) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (MarketClosed, InsufficientBalance, InvalidBet) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/leaderboard", response_model=list[scoring.LeaderboardEntry])
def leaderboard(
    engine: Annotated[MarketEngine, Depends(get_engine)],
) -> list[scoring.LeaderboardEntry]:
    return scoring.leaderboard(engine.store)


@router.post("/rounds/{round_id}/resolve", response_model=list[SettlementResult])
def resolve_round(
    round_id: int, body: ResolveRequest, engine: Annotated[MarketEngine, Depends(get_engine)]
) -> list[SettlementResult]:
    """Règle tous les marchés non résolus d'un round (le Juge = oracle)."""
    summary = _summary_from_decisions(round_id, body.decisions)
    results: list[SettlementResult] = []
    for market in engine.store.list_markets(round_id=round_id):
        if market.status is MarketStatus.RESOLVED:
            continue
        try:
            results.append(
                resolve_and_settle(
                    engine.store, market, summary,
                    delta_utopia=body.delta_utopia, council_winner=body.council_winner,
                )
            )
        except ResolutionError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    return results
