"""Moteur du marché : ouverture, cotation et paris au prix LMSR.

`MarketEngine` orchestre les fonctions pures de `lmsr.py` et la persistance `MarketStore` :
`open_market` (crée un marché + outcomes à `q=0`), `quote` (devis sans exécution), `place_bet`
(exécute au prix LMSR, débite le compte, déplace `q` et la position). Argent **fictif**.
"""

from __future__ import annotations

import math
import threading
import uuid
from datetime import UTC, datetime

from market import lmsr
from market.models import (
    Account,
    AccountKind,
    Market,
    MarketStatus,
    MarketType,
    Outcome,
    Position,
    Quote,
    ResolutionCriterion,
    Trade,
)
from market.store import MarketStore

# Solde de départ d'un participant (crédits fictifs), base du P&L.
STARTING_BALANCE: float = 1000.0
# Libellés d'un marché binaire / seuil.
YES_NO: tuple[str, str] = ("YES", "NO")


class MarketError(Exception):
    """Erreur métier du marché (marché inconnu/fermé, solde insuffisant, pari invalide)."""


class UnknownMarket(MarketError): ...


class UnknownAccount(MarketError): ...


class UnknownOutcome(MarketError): ...


class MarketClosed(MarketError): ...


class InvalidBet(MarketError): ...


class InsufficientBalance(MarketError): ...


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class MarketEngine:
    """Ouvre des marchés, cote et exécute des paris au prix LMSR sur un `MarketStore`."""

    def __init__(self, store: MarketStore) -> None:
        self.store = store
        # Les paris sont des read-modify-write : un verrou moteur empêche deux requêtes
        # concurrentes de partir du même q/solde et de perdre une des mises.
        self.lock = threading.RLock()

    # --- comptes ------------------------------------------------------------

    def create_account(
        self,
        name: str,
        *,
        kind: AccountKind = AccountKind.HUMAN,
        balance: float = STARTING_BALANCE,
        account_id: str | None = None,
    ) -> Account:
        if not name.strip() or len(name) > 80:
            raise InvalidBet("nom de compte invalide")
        if not math.isfinite(balance) or balance < 0:
            raise InvalidBet("solde initial invalide")
        with self.lock:
            account = Account(
                id=account_id or _new_id("acc"), name=name.strip(), kind=kind, balance=balance
            )
            self.store.add_account(account)
            return account

    # --- ouverture ----------------------------------------------------------

    def open_market(
        self,
        *,
        round_id: int,
        question: str,
        labels: list[str],
        b: float,
        game_id: str | None = None,
        type: MarketType = MarketType.BINARY,
        criterion: ResolutionCriterion | None = None,
        market_id: str | None = None,
        created_at: str | None = None,
    ) -> Market:
        """Ouvre un marché à `q=0` (prix uniformes au départ)."""
        if len(labels) < 2 or len(labels) > 20:
            raise InvalidBet("un marché a besoin d'au moins 2 issues")
        clean_labels = [label.strip() for label in labels]
        if any(not label or len(label) > 80 for label in clean_labels):
            raise InvalidBet("libellé d'issue invalide")
        if len(set(clean_labels)) != len(clean_labels):
            raise InvalidBet("les libellés d'issue doivent être uniques")
        if not math.isfinite(b) or b <= 0:
            raise InvalidBet("la liquidité b doit être > 0")
        with self.lock:
            mid = market_id or _new_id("mkt")
            outcomes = [
                Outcome(id=f"{mid}:{i}", market_id=mid, label=label, q=0.0)
                for i, label in enumerate(clean_labels)
            ]
            market = Market(
                id=mid,
                round_id=round_id,
                game_id=game_id,
                question=question.strip(),
                type=type,
                status=MarketStatus.OPEN,
                b=b,
                outcomes=outcomes,
                criterion=criterion,
                created_at=created_at or _now_iso(),
            )
            self.store.add_market(market)
            return market

    def open_binary_market(
        self,
        *,
        round_id: int,
        question: str,
        b: float,
        game_id: str | None = None,
        type: MarketType = MarketType.BINARY,
        criterion: ResolutionCriterion | None = None,
        market_id: str | None = None,
        created_at: str | None = None,
    ) -> Market:
        """Raccourci pour un marché YES/NO (binaire ou seuil)."""
        return self.open_market(
            round_id=round_id,
            question=question,
            labels=list(YES_NO),
            b=b,
            game_id=game_id,
            type=type,
            criterion=criterion,
            market_id=market_id,
            created_at=created_at,
        )

    # --- cotation -----------------------------------------------------------

    def _require_market(self, market_id: str) -> Market:
        market = self.store.get_market(market_id)
        if market is None:
            raise UnknownMarket(market_id)
        return market

    def prices(self, market_id: str) -> dict[str, float]:
        """Prix courants (= probabilités implicites) par outcome, somment à 1."""
        with self.lock:
            market = self._require_market(market_id)
            ps = lmsr.price(market.q_vector(), market.b)
            return {o.id: p for o, p in zip(market.outcomes, ps, strict=True)}

    def quote(self, market_id: str, outcome_id: str, shares: float) -> Quote:
        """Devis d'un pari (coût + prix avant/après), sans rien exécuter."""
        if not math.isfinite(shares):
            raise InvalidBet("shares doit être un nombre fini")
        with self.lock:
            market = self._require_market(market_id)
            if market.find_outcome(outcome_id) is None:
                raise UnknownOutcome(outcome_id)
            i = market.outcome_index(outcome_id)
            q, b = market.q_vector(), market.b
            after = list(q)
            after[i] += shares
            return Quote(
                market_id=market_id,
                outcome_id=outcome_id,
                shares=shares,
                cost=lmsr.cost_to_trade(q, b, i, shares),
                price_before=lmsr.price(q, b)[i],
                price_after=lmsr.price(after, b)[i],
            )

    # --- paris --------------------------------------------------------------

    def place_bet(
        self, account_id: str, market_id: str, outcome_id: str, shares: float
    ) -> Trade:
        """Exécute un pari : débite le compte du coût LMSR, déplace `q` et la position.

        Le read-modify-write est sérialisé par ``self.lock``. SQLite fournit en plus
        ``apply_trade`` : marché, compte, position et journal y sont commités atomiquement.
        Les stores distants restent protégés des courses intra-processus et peuvent exposer
        la même primitive pour obtenir l'atomicité réseau.
        """
        if not math.isfinite(shares) or shares == 0:
            raise InvalidBet("shares ne peut pas être nul")
        with self.lock:
            market = self._require_market(market_id)
            if market.status is not MarketStatus.OPEN:
                raise MarketClosed(f"{market_id} n'est pas ouvert ({market.status.value})")
            outcome = market.find_outcome(outcome_id)
            if outcome is None:
                raise UnknownOutcome(outcome_id)
            account = self.store.get_account(account_id)
            if account is None:
                raise UnknownAccount(account_id)

            position = self.store.get_position(account_id, outcome_id) or Position(
                account_id=account_id, outcome_id=outcome_id, shares=0.0
            )
            if position.shares + shares < -1e-9:
                raise InvalidBet("vente impossible : position insuffisante")

            i = market.outcome_index(outcome_id)
            cost = lmsr.cost_to_trade(market.q_vector(), market.b, i, shares)
            if cost > account.balance:  # les ventes (cost < 0) créditent -> jamais bloquées
                raise InsufficientBalance(
                    f"coût {cost:.2f} > solde {account.balance:.2f}"
                )

            outcome.q += shares
            account.balance -= cost
            price_after = lmsr.price(market.q_vector(), market.b)[i]

            position.shares += shares

            trade = Trade(
                id=_new_id("trd"),
                account_id=account_id,
                market_id=market_id,
                outcome_id=outcome_id,
                shares=shares,
                cost=cost,
                price=price_after,
                ts=_now_iso(),
            )

            apply_trade = getattr(self.store, "apply_trade", None)
            if callable(apply_trade):
                apply_trade(market, account, position, trade)
            else:
                # Store distant : le verrou évite les courses dans ce process. Le backend
                # transactionnel doit fournir apply_trade pour l'atomicité inter-tables.
                self.store.save_market(market)
                self.store.save_account(account)
                self.store.save_position(position)
                self.store.add_trade(trade)
            return trade
