"""Persistance du marché — interface `MarketStore` + implémentation SQLite.

SQLite (fichier local ou `:memory:`) au début ; migration PostgreSQL plus tard (déjà dans la
stack). Tables : cf. `docs/spec_market.md` §8. L'interface `MarketStore` (Protocol) découple le
moteur du stockage → testable et remplaçable.

Note : les écritures s'auto-committent (contexte `with connexion`, rollback sur exception). Un
pari touche plusieurs tables sans transaction unique — acceptable en local, argent fictif.
"""

from __future__ import annotations

import sqlite3
from typing import Protocol

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

_SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL, balance REAL NOT NULL,
    initial_balance REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS markets (
    id TEXT PRIMARY KEY, round_id INTEGER NOT NULL, type TEXT NOT NULL, question TEXT NOT NULL,
    status TEXT NOT NULL, b REAL NOT NULL, criterion TEXT, resolved_outcome TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS outcomes (
    id TEXT PRIMARY KEY, market_id TEXT NOT NULL, label TEXT NOT NULL, q REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS positions (
    account_id TEXT NOT NULL, outcome_id TEXT NOT NULL, shares REAL NOT NULL,
    PRIMARY KEY (account_id, outcome_id)
);
CREATE TABLE IF NOT EXISTS trades (
    id TEXT PRIMARY KEY, account_id TEXT NOT NULL, market_id TEXT NOT NULL,
    outcome_id TEXT NOT NULL, shares REAL NOT NULL, cost REAL NOT NULL, price REAL NOT NULL,
    ts TEXT NOT NULL
);
"""


class MarketStore(Protocol):
    """Contrat de persistance dont dépend `MarketEngine` (implémenté par SQLite)."""

    def add_account(self, account: Account) -> None: ...
    def get_account(self, account_id: str) -> Account | None: ...
    def save_account(self, account: Account) -> None: ...
    def list_accounts(self) -> list[Account]: ...
    def add_market(self, market: Market) -> None: ...
    def get_market(self, market_id: str) -> Market | None: ...
    def save_market(self, market: Market) -> None: ...
    def list_markets(
        self, *, round_id: int | None = None, status: MarketStatus | None = None
    ) -> list[Market]: ...
    def get_position(self, account_id: str, outcome_id: str) -> Position | None: ...
    def save_position(self, position: Position) -> None: ...
    def list_positions(
        self, *, account_id: str | None = None, market_id: str | None = None
    ) -> list[Position]: ...
    def add_trade(self, trade: Trade) -> None: ...
    def list_trades(
        self, *, account_id: str | None = None, market_id: str | None = None
    ) -> list[Trade]: ...


class SQLiteMarketStore:
    """Implémentation SQLite de `MarketStore` (une connexion, `:memory:` par défaut)."""

    def __init__(self, path: str = ":memory:") -> None:
        # check_same_thread=False : FastAPI sert les routes sync dans un threadpool ; en local
        # (mono-utilisateur, verrouillage SQLite) partager l'unique connexion est acceptable.
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)

    def close(self) -> None:
        self._conn.close()

    # --- comptes ------------------------------------------------------------

    def add_account(self, account: Account) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT INTO accounts (id, name, kind, balance, initial_balance) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    account.id,
                    account.name,
                    account.kind.value,
                    account.balance,
                    account.initial_balance,
                ),
            )

    def get_account(self, account_id: str) -> Account | None:
        row = self._conn.execute(
            "SELECT * FROM accounts WHERE id = ?", (account_id,)
        ).fetchone()
        return _account(row) if row else None

    def save_account(self, account: Account) -> None:
        with self._conn:
            self._conn.execute(
                "UPDATE accounts SET name = ?, kind = ?, balance = ?, initial_balance = ? "
                "WHERE id = ?",
                (
                    account.name,
                    account.kind.value,
                    account.balance,
                    account.initial_balance,
                    account.id,
                ),
            )

    def list_accounts(self) -> list[Account]:
        rows = self._conn.execute("SELECT * FROM accounts ORDER BY rowid").fetchall()
        return [_account(r) for r in rows]

    # --- marchés + outcomes -------------------------------------------------

    def add_market(self, market: Market) -> None:
        criterion = market.criterion.model_dump_json() if market.criterion else None
        with self._conn:
            self._conn.execute(
                "INSERT INTO markets "
                "(id, round_id, type, question, status, b, criterion, resolved_outcome, "
                "created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    market.id,
                    market.round_id,
                    market.type.value,
                    market.question,
                    market.status.value,
                    market.b,
                    criterion,
                    market.resolved_outcome,
                    market.created_at,
                ),
            )
            self._conn.executemany(
                "INSERT INTO outcomes (id, market_id, label, q) VALUES (?, ?, ?, ?)",
                [(o.id, o.market_id, o.label, o.q) for o in market.outcomes],
            )

    def get_market(self, market_id: str) -> Market | None:
        row = self._conn.execute("SELECT * FROM markets WHERE id = ?", (market_id,)).fetchone()
        return self._market(row) if row else None

    def save_market(self, market: Market) -> None:
        """Met à jour le marché (statut, issue) ET les `q` de ses outcomes (après un trade)."""
        with self._conn:
            self._conn.execute(
                "UPDATE markets SET status = ?, resolved_outcome = ? WHERE id = ?",
                (market.status.value, market.resolved_outcome, market.id),
            )
            self._conn.executemany(
                "UPDATE outcomes SET q = ? WHERE id = ?",
                [(o.q, o.id) for o in market.outcomes],
            )

    def list_markets(
        self, *, round_id: int | None = None, status: MarketStatus | None = None
    ) -> list[Market]:
        clauses, params = [], []
        if round_id is not None:
            clauses.append("round_id = ?")
            params.append(round_id)
        if status is not None:
            clauses.append("status = ?")
            params.append(status.value)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self._conn.execute(
            f"SELECT * FROM markets{where} ORDER BY rowid", params
        ).fetchall()
        return [self._market(r) for r in rows]

    def _outcomes(self, market_id: str) -> list[Outcome]:
        rows = self._conn.execute(
            "SELECT * FROM outcomes WHERE market_id = ? ORDER BY rowid", (market_id,)
        ).fetchall()
        return [
            Outcome(id=r["id"], market_id=r["market_id"], label=r["label"], q=r["q"]) for r in rows
        ]

    def _market(self, row: sqlite3.Row) -> Market:
        criterion = (
            ResolutionCriterion.model_validate_json(row["criterion"]) if row["criterion"] else None
        )
        return Market(
            id=row["id"],
            round_id=row["round_id"],
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
        row = self._conn.execute(
            "SELECT * FROM positions WHERE account_id = ? AND outcome_id = ?",
            (account_id, outcome_id),
        ).fetchone()
        return _position(row) if row else None

    def save_position(self, position: Position) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT INTO positions (account_id, outcome_id, shares) VALUES (?, ?, ?) "
                "ON CONFLICT(account_id, outcome_id) DO UPDATE SET shares = excluded.shares",
                (position.account_id, position.outcome_id, position.shares),
            )

    def list_positions(
        self, *, account_id: str | None = None, market_id: str | None = None
    ) -> list[Position]:
        if market_id is not None:
            rows = self._conn.execute(
                "SELECT p.* FROM positions p JOIN outcomes o ON p.outcome_id = o.id "
                "WHERE o.market_id = ?"
                + (" AND p.account_id = ?" if account_id else "")
                + " ORDER BY p.rowid",
                (market_id, account_id) if account_id else (market_id,),
            ).fetchall()
        elif account_id is not None:
            rows = self._conn.execute(
                "SELECT * FROM positions WHERE account_id = ? ORDER BY rowid", (account_id,)
            ).fetchall()
        else:
            rows = self._conn.execute("SELECT * FROM positions ORDER BY rowid").fetchall()
        return [_position(r) for r in rows]

    # --- trades -------------------------------------------------------------

    def add_trade(self, trade: Trade) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT INTO trades "
                "(id, account_id, market_id, outcome_id, shares, cost, price, ts) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    trade.id,
                    trade.account_id,
                    trade.market_id,
                    trade.outcome_id,
                    trade.shares,
                    trade.cost,
                    trade.price,
                    trade.ts,
                ),
            )

    def list_trades(
        self, *, account_id: str | None = None, market_id: str | None = None
    ) -> list[Trade]:
        clauses, params = [], []
        if account_id is not None:
            clauses.append("account_id = ?")
            params.append(account_id)
        if market_id is not None:
            clauses.append("market_id = ?")
            params.append(market_id)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self._conn.execute(
            f"SELECT * FROM trades{where} ORDER BY rowid", params
        ).fetchall()
        return [_trade(r) for r in rows]


def _account(row: sqlite3.Row) -> Account:
    return Account(
        id=row["id"],
        name=row["name"],
        kind=AccountKind(row["kind"]),
        balance=row["balance"],
        initial_balance=row["initial_balance"],
    )


def _position(row: sqlite3.Row) -> Position:
    return Position(
        account_id=row["account_id"], outcome_id=row["outcome_id"], shares=row["shares"]
    )


def _trade(row: sqlite3.Row) -> Trade:
    return Trade(
        id=row["id"],
        account_id=row["account_id"],
        market_id=row["market_id"],
        outcome_id=row["outcome_id"],
        shares=row["shares"],
        cost=row["cost"],
        price=row["price"],
        ts=row["ts"],
    )
