"""Tests du GameStore SQLite — R2 : snapshots de session, mode, migration."""

import sqlite3

from storage.game_store import (
    GameRecord,
    GameStatus,
    SessionSnapshot,
    SQLiteGameStore,
)


def _game(game_id: str = "g1", mode: str = "classic") -> GameRecord:
    return GameRecord(
        id=game_id, scenario="red_sea", horizon=5, mode=mode, created_at="2026-07-05T00:00:00"
    )


def _snapshot(game_id: str = "g1", **kw) -> SessionSnapshot:
    defaults = dict(
        world={"current_round": 1, "countries": {"usa": {}}},
        clock={"current_date": "2025-07-01", "base_months": 6},
        recent=["Crise en mer Rouge"],
        pending_motion=None,
        suspended=[],
        play_as=None,
        updated_at="2026-07-05T00:00:00",
    )
    defaults.update(kw)
    return SessionSnapshot(game_id=game_id, **defaults)


# --- mode ---------------------------------------------------------------------


def test_game_mode_roundtrip():
    store = SQLiteGameStore(":memory:")
    store.add_game(_game(mode="escalation"))
    got = store.get_game("g1")
    assert got is not None and got.mode == "escalation"

    got.mode = "fog"
    store.save_game(got)
    assert store.get_game("g1").mode == "fog"


def test_migration_adds_mode_to_legacy_db(tmp_path):
    """Une base créée avant R2 (games sans colonne mode) s'ouvre et se migre."""
    path = str(tmp_path / "legacy.db")
    conn = sqlite3.connect(path)
    conn.executescript(
        "CREATE TABLE games (id TEXT PRIMARY KEY, scenario TEXT NOT NULL, "
        "horizon INTEGER NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL);"
    )
    conn.execute(
        "INSERT INTO games VALUES ('old', 'red_sea', 5, 'running', '2026-01-01T00:00:00')"
    )
    conn.commit()
    conn.close()

    store = SQLiteGameStore(path)
    got = store.get_game("old")
    assert got is not None
    assert got.mode == "classic"  # défaut appliqué par la migration
    assert got.status is GameStatus.RUNNING
    store.close()


# --- snapshots de session -------------------------------------------------------


def test_snapshot_absent():
    store = SQLiteGameStore(":memory:")
    assert store.get_session_snapshot("nope") is None
    assert store.list_session_snapshots() == []


def test_snapshot_roundtrip():
    store = SQLiteGameStore(":memory:")
    store.add_game(_game())
    snap = _snapshot(
        pending_motion={"country": "iran", "reason": "accaparement"},
        suspended=["china"],
        play_as="france",
    )
    store.save_session_snapshot(snap)

    got = store.get_session_snapshot("g1")
    assert got == snap
    assert store.list_session_snapshots() == ["g1"]


def test_snapshot_upsert_overwrites():
    store = SQLiteGameStore(":memory:")
    store.add_game(_game())
    store.save_session_snapshot(_snapshot(recent=["a"], updated_at="t1"))
    store.save_session_snapshot(_snapshot(recent=["a", "b"], updated_at="t2"))

    got = store.get_session_snapshot("g1")
    assert got.recent == ["a", "b"] and got.updated_at == "t2"
    assert store.list_session_snapshots() == ["g1"]  # une seule ligne par partie


def test_snapshot_none_motion_stays_none():
    store = SQLiteGameStore(":memory:")
    store.save_session_snapshot(_snapshot(pending_motion=None))
    assert store.get_session_snapshot("g1").pending_motion is None
