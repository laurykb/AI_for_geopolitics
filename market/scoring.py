"""Scoring & calibration : P&L, score de Brier, leaderboard — l'artefact de recherche (§5).

- **P&L** = solde − solde initial (par compte).
- **Brier** = moyenne de `(p − résultat)²`, résultat ∈ {0,1} ; **plus bas = mieux calibré** →
  « qui prédit le mieux la super-intelligence ».

Faute de prédiction explicite (le `forecaster.py` LLM en fournira), on dérive les prédictions des
**positions** : chaque **achat** exprime `p =` prix implicite post-trade de l'issue achetée, avec
`résultat = 1` si cette issue a gagné. Ne compte que les marchés **résolus** et les **achats**
(une vente = gestion de position, pas une nouvelle prévision). Argent **fictif**.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from market.models import Account, AccountKind, MarketStatus
from market.store import MarketStore


class Prediction(BaseModel):
    """Une prévision élémentaire pour le Brier : proba assignée + issue réalisée."""

    probability: float = Field(ge=0.0, le=1.0)
    result: int = Field(ge=0, le=1)  # 1 si l'issue prédite a gagné, sinon 0


def brier_score(predictions: list[Prediction]) -> float | None:
    """Moyenne de `(p − résultat)²`. `None` si aucune prévision (rien à scorer)."""
    if not predictions:
        return None
    return sum((p.probability - p.result) ** 2 for p in predictions) / len(predictions)


def pnl(account: Account) -> float:
    """Profit & Loss = solde courant − solde initial (crédits fictifs)."""
    base = account.initial_balance if account.initial_balance is not None else account.balance
    return account.balance - base


def account_predictions(store: MarketStore, account_id: str) -> list[Prediction]:
    """Prévisions déduites des achats du compte sur des marchés résolus (proxy de position)."""
    predictions: list[Prediction] = []
    for trade in store.list_trades(account_id=account_id):
        if trade.shares <= 0:  # seuls les achats expriment une prévision
            continue
        market = store.get_market(trade.market_id)
        if market is None or market.status is not MarketStatus.RESOLVED:
            continue
        won = 1 if trade.outcome_id == market.resolved_outcome else 0
        predictions.append(Prediction(probability=trade.price, result=won))
    return predictions


def account_brier(store: MarketStore, account_id: str) -> float | None:
    """Score de Brier d'un compte (`None` s'il n'a pas de prévision résolue)."""
    return brier_score(account_predictions(store, account_id))


class LeaderboardEntry(BaseModel):
    """Ligne de classement : P&L (gain fictif) + Brier (calibration, plus bas = mieux)."""

    account_id: str
    name: str
    kind: AccountKind
    pnl: float
    brier: float | None = None


def leaderboard(store: MarketStore) -> list[LeaderboardEntry]:
    """Classement de tous les comptes, trié par P&L décroissant."""
    entries = [
        LeaderboardEntry(
            account_id=a.id,
            name=a.name,
            kind=a.kind,
            pnl=pnl(a),
            brier=account_brier(store, a.id),
        )
        for a in store.list_accounts()
    ]
    entries.sort(key=lambda e: e.pnl, reverse=True)
    return entries
