"""`SupabaseMarketStore` — l'implémentation Supabase du Protocol `MarketStore` (Phase R2).

Tables `market_*` de `supabase/schema.sql`, parlées via PostgREST
(`storage/postgrest.py`). Écart assumé avec SQLite : `list_positions(market_id=…)`
fait la jointure côté client (deux selects) plutôt qu'un embed PostgREST — volumes
minuscules, lisibilité d'abord.
"""

from __future__ import annotations

import os

from market.models import (
    Account,
    AccountKind,
    Market,
    MarketStatus,
    MarketType,
    Outcome,
    Position,
    ResolutionCriterion,
    Trade,
)
from storage.postgrest import PostgrestClient


class SupabaseMarketStore:
    """Implémentation Supabase/PostgREST de `MarketStore` (schéma `supabase/schema.sql`)."""

    def __init__(self, client: PostgrestClient) -> None:
        self._db = client

    @classmethod
    def from_env(cls) -> SupabaseMarketStore:
        """Construit depuis `SUPABASE_URL` + `SUPABASE_SERVICE_KEY` (service_role)."""
        url, key = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_SERVICE_KEY")
        if not url or not key:
            raise RuntimeError(
                "STORE_BACKEND=supabase exige SUPABASE_URL et SUPABASE_SERVICE_KEY"
            )
        return cls(PostgrestClient(url, key))

    def close(self) -> None:
        self._db.close()

    # --- comptes ------------------------------------------------------------

    def add_account(self, account: Account) -> None:
        self._db.insert("market_accounts", [_account_row(account)])

    def get_account(self, account_id: str) -> Account | None:
        rows = self._db.select("market_accounts", {"id": account_id})
        return _account(rows[0]) if rows else None

    def save_account(self, account: Account) -> None:
        row = _account_row(account)
        del row["id"]
        self._db.update("market_accounts", {"id": account.id}, row)

    def list_accounts(self) -> list[Account]:
        return [_account(r) for r in self._db.select("market_accounts", order="id.asc")]

    # --- marchés + outcomes -------------------------------------------------

    def add_market(self, market: Market) -> None:
        self._db.insert("markets", [_market_row(market)])
        self._db.insert(
            "market_outcomes",
            [{"id": o.id, "market_id": o.market_id, "label": o.label, "q": o.q}
             for o in market.outcomes],
        )

    def get_market(self, market_id: str) -> Market | None:
        rows = self._db.select("markets", {"id": market_id})
        return self._market(rows[0]) if rows else None

    def save_market(self, market: Market) -> None:
        """Met à jour le marché (statut, issue) ET les `q` de ses outcomes (après un trade)."""
        self._db.update(
            "markets",
            {"id": market.id},
            {"status": market.status.value, "resolved_outcome": market.resolved_outcome},
        )
        for outcome in market.outcomes:
            self._db.update("market_outcomes", {"id": outcome.id}, {"q": outcome.q})

    def list_markets(
        self,
        *,
        round_id: int | None = None,
        game_id: str | None = None,
        status: MarketStatus | None = None,
    ) -> list[Market]:
        match: dict[str, object] = {}
        if round_id is not None:
            match["round_id"] = round_id
        if game_id is not None:
            match["game_id"] = game_id
        if status is not None:
            match["status"] = status.value
        rows = self._db.select("markets", match, order="created_at.asc")
        return [self._market(r) for r in rows]

    def _outcomes(self, market_id: str) -> list[Outcome]:
        # id = "{market_id}:{i}" (engine.open_market) : trier par id = ordre d'ouverture.
        rows = self._db.select("market_outcomes", {"market_id": market_id}, order="id.asc")
        return [
            Outcome(id=r["id"], market_id=r["market_id"], label=r["label"], q=r["q"])
            for r in rows
        ]

    def _market(self, row: dict) -> Market:
        criterion = (
            ResolutionCriterion.model_validate_json(row["criterion"]) if row["criterion"] else None
        )
        return Market(
            id=row["id"],
            round_id=row["round_id"],
            game_id=row["game_id"],
            question=row["question"],
            type=MarketType(row["type"]),
            status=MarketStatus(row["status"]),
            b=row["b"],
            criterion=criterion,
            resolved_outcome=row["resolved_outcome"],
            created_at=row["created_at"],
            outcomes=self._outcomes(row["id"]),
        )

    # --- positions ----------------------------------------------------------

    def get_position(self, account_id: str, outcome_id: str) -> Position | None:
        rows = self._db.select(
            "market_positions", {"account_id": account_id, "outcome_id": outcome_id}
        )
        return _position(rows[0]) if rows else None

    def save_position(self, position: Position) -> None:
        self._db.upsert(
            "market_positions",
            {
                "account_id": position.account_id,
                "outcome_id": position.outcome_id,
                "shares": position.shares,
            },
        )

    def list_positions(
        self, *, account_id: str | None = None, market_id: str | None = None
    ) -> list[Position]:
        match: dict[str, object] = {}
        if account_id is not None:
            match["account_id"] = account_id
        rows = self._db.select("market_positions", match)
        if market_id is not None:
            outcome_ids = {o.id for o in self._outcomes(market_id)}
            rows = [r for r in rows if r["outcome_id"] in outcome_ids]
        return [_position(r) for r in rows]

    # --- trades -------------------------------------------------------------

    def add_trade(self, trade: Trade) -> None:
        self._db.insert("market_trades", [trade.model_dump()])

    def list_trades(
        self, *, account_id: str | None = None, market_id: str | None = None
    ) -> list[Trade]:
        match: dict[str, object] = {}
        if account_id is not None:
            match["account_id"] = account_id
        if market_id is not None:
            match["market_id"] = market_id
        rows = self._db.select("market_trades", match, order="ts.asc")
        return [Trade(**r) for r in rows]


# --- mapping lignes <-> modèles ---------------------------------------------------


def _account_row(account: Account) -> dict:
    return {
        "id": account.id,
        "name": account.name,
        "kind": account.kind.value,
        "balance": account.balance,
        "initial_balance": account.initial_balance,
    }


def _account(row: dict) -> Account:
    return Account(
        id=row["id"],
        name=row["name"],
        kind=AccountKind(row["kind"]),
        balance=row["balance"],
        initial_balance=row["initial_balance"],
    )


def _market_row(market: Market) -> dict:
    return {
        "id": market.id,
        "round_id": market.round_id,
        "game_id": market.game_id,
        "type": market.type.value,
        "question": market.question,
        "status": market.status.value,
        "b": market.b,
        "criterion": market.criterion.model_dump_json() if market.criterion else None,
        "resolved_outcome": market.resolved_outcome,
        "created_at": market.created_at,
    }


def _position(row: dict) -> Position:
    return Position(
        account_id=row["account_id"], outcome_id=row["outcome_id"], shares=row["shares"]
    )
