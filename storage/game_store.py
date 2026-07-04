"""Persistance des parties — interface `GameStore` + implémentation SQLite.

Schéma aligné sur la Phase R2 du plan de refonte (`docs/REFONTE_PLAN.md`) : tables `games`,
`rounds`, `transcripts`. SQLite (fichier local ou `:memory:`) en local ; la bascule
Supabase/Postgres au déploiement = une autre implémentation du même Protocol, sans toucher
l'API de jeu. Même patron que `market/store.py`.

Le transcript inclut les prises de parole du Game Master (`speaker="gm"`) et du juge
(`speaker="judge"`) : rejouer une partie = relire la table dans l'ordre (id de round, seq).
"""

from __future__ import annotations

import json
import sqlite3
from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, Field

_SCHEMA = """
CREATE TABLE IF NOT EXISTS games (
    id TEXT PRIMARY KEY, scenario TEXT NOT NULL, horizon INTEGER NOT NULL,
    status TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS rounds (
    id TEXT PRIMARY KEY, game_id TEXT NOT NULL, round_no INTEGER NOT NULL,
    event_json TEXT NOT NULL, deltas_json TEXT NOT NULL, risk_json TEXT NOT NULL,
    judge_json TEXT NOT NULL, trajectory_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS transcripts (
    id TEXT PRIMARY KEY, round_id TEXT NOT NULL, seq INTEGER NOT NULL,
    speaker TEXT NOT NULL, model TEXT NOT NULL, content TEXT NOT NULL,
    reasoning TEXT NOT NULL, ts TEXT NOT NULL
);
"""


class GameStatus(StrEnum):
    RUNNING = "running"
    FINISHED = "finished"


class GameRecord(BaseModel):
    """Ligne `games` : une partie (le monde vivant reste en mémoire process)."""

    id: str
    scenario: str
    horizon: int
    status: GameStatus = GameStatus.RUNNING
    created_at: str


class RoundRecord(BaseModel):
    """Ligne `rounds` : le round arbitré, sérialisé pour la relecture."""

    id: str
    game_id: str
    round_no: int
    event: dict = Field(default_factory=dict)
    deltas: list[dict] = Field(default_factory=list)
    risk: dict = Field(default_factory=dict)
    judge: dict = Field(default_factory=dict)
    trajectory: dict = Field(default_factory=dict)


class TranscriptEntry(BaseModel):
    """Ligne `transcripts` : une prise de parole du théâtre (pays, GM ou juge)."""

    id: str
    round_id: str
    seq: int
    speaker: str  # id pays, "gm" ou "judge"
    model: str = ""
    content: str = ""
    reasoning: str = ""
    ts: str = ""


class GameStore(Protocol):
    """Contrat de persistance dont dépend l'API de jeu (implémenté par SQLite)."""

    def add_game(self, game: GameRecord) -> None: ...
    def get_game(self, game_id: str) -> GameRecord | None: ...
    def save_game(self, game: GameRecord) -> None: ...
    def list_games(self) -> list[GameRecord]: ...
    def add_round(self, round_: RoundRecord) -> None: ...
    def list_rounds(self, game_id: str) -> list[RoundRecord]: ...
    def add_transcript(self, entries: list[TranscriptEntry]) -> None: ...
    def list_transcript(self, round_id: str) -> list[TranscriptEntry]: ...


class SQLiteGameStore:
    """Implémentation SQLite de `GameStore` (une connexion, `:memory:` par défaut)."""

    def __init__(self, path: str = ":memory:") -> None:
        # check_same_thread=False : FastAPI sert les routes sync dans un threadpool ; en local
        # (mono-utilisateur, verrouillage SQLite) partager l'unique connexion est acceptable.
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)

    def close(self) -> None:
        self._conn.close()

    # --- parties --------------------------------------------------------------

    def add_game(self, game: GameRecord) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT INTO games (id, scenario, horizon, status, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (game.id, game.scenario, game.horizon, game.status.value, game.created_at),
            )

    def get_game(self, game_id: str) -> GameRecord | None:
        row = self._conn.execute("SELECT * FROM games WHERE id = ?", (game_id,)).fetchone()
        return _game(row) if row else None

    def save_game(self, game: GameRecord) -> None:
        with self._conn:
            self._conn.execute(
                "UPDATE games SET scenario = ?, horizon = ?, status = ? WHERE id = ?",
                (game.scenario, game.horizon, game.status.value, game.id),
            )

    def list_games(self) -> list[GameRecord]:
        rows = self._conn.execute("SELECT * FROM games ORDER BY rowid").fetchall()
        return [_game(r) for r in rows]

    # --- rounds ----------------------------------------------------------------

    def add_round(self, round_: RoundRecord) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT INTO rounds (id, game_id, round_no, event_json, deltas_json, "
                "risk_json, judge_json, trajectory_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    round_.id,
                    round_.game_id,
                    round_.round_no,
                    json.dumps(round_.event, ensure_ascii=False),
                    json.dumps(round_.deltas, ensure_ascii=False),
                    json.dumps(round_.risk, ensure_ascii=False),
                    json.dumps(round_.judge, ensure_ascii=False),
                    json.dumps(round_.trajectory, ensure_ascii=False),
                ),
            )

    def list_rounds(self, game_id: str) -> list[RoundRecord]:
        rows = self._conn.execute(
            "SELECT * FROM rounds WHERE game_id = ? ORDER BY round_no", (game_id,)
        ).fetchall()
        return [_round(r) for r in rows]

    # --- transcripts -------------------------------------------------------------

    def add_transcript(self, entries: list[TranscriptEntry]) -> None:
        with self._conn:
            self._conn.executemany(
                "INSERT INTO transcripts (id, round_id, seq, speaker, model, content, "
                "reasoning, ts) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (e.id, e.round_id, e.seq, e.speaker, e.model, e.content, e.reasoning, e.ts)
                    for e in entries
                ],
            )

    def list_transcript(self, round_id: str) -> list[TranscriptEntry]:
        rows = self._conn.execute(
            "SELECT * FROM transcripts WHERE round_id = ? ORDER BY seq", (round_id,)
        ).fetchall()
        return [_entry(r) for r in rows]


# --- mapping lignes -> modèles ---------------------------------------------------


def _game(row: sqlite3.Row) -> GameRecord:
    return GameRecord(
        id=row["id"],
        scenario=row["scenario"],
        horizon=row["horizon"],
        status=GameStatus(row["status"]),
        created_at=row["created_at"],
    )


def _round(row: sqlite3.Row) -> RoundRecord:
    return RoundRecord(
        id=row["id"],
        game_id=row["game_id"],
        round_no=row["round_no"],
        event=json.loads(row["event_json"]),
        deltas=json.loads(row["deltas_json"]),
        risk=json.loads(row["risk_json"]),
        judge=json.loads(row["judge_json"]),
        trajectory=json.loads(row["trajectory_json"]),
    )


def _entry(row: sqlite3.Row) -> TranscriptEntry:
    return TranscriptEntry(
        id=row["id"],
        round_id=row["round_id"],
        seq=row["seq"],
        speaker=row["speaker"],
        model=row["model"],
        content=row["content"],
        reasoning=row["reasoning"],
        ts=row["ts"],
    )
