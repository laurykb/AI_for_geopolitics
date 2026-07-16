"""Tests du GameStore SQLite — R2 : snapshots de session, mode, migration."""

import sqlite3

from storage.game_store import (
    CustomCrisisRecord,
    GameRecord,
    GameStatus,
    PlayerRecord,
    SessionSnapshot,
    SQLiteGameStore,
    XpHistoryEntry,
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


def test_ownership_fields_roundtrip():
    # G11 — propriété + classement : owner_id / ranked / difficulty / drift_enabled.
    store = SQLiteGameStore(":memory:")
    game = _game("g5")
    game.owner_id = "u_laury"
    game.ranked = True
    game.difficulty = "expert"
    game.drift_enabled = False
    store.add_game(game)

    got = store.get_game("g5")
    assert got is not None
    assert (got.owner_id, got.ranked, got.difficulty, got.drift_enabled) == (
        "u_laury",
        True,
        "expert",
        False,
    )

    got.owner_id = "u_other"
    store.save_game(got)
    assert store.get_game("g5").owner_id == "u_other"


def test_ownership_defaults():
    store = SQLiteGameStore(":memory:")
    store.add_game(_game("g6"))
    got = store.get_game("g6")
    assert got.owner_id is None
    assert got.ranked is False
    assert got.difficulty == "intermediate"
    assert got.drift_enabled is True


def test_result_json_roundtrip():
    # G11-c — le bilan de fin de partie survit au store.
    store = SQLiteGameStore(":memory:")
    game = _game("gr")
    store.add_game(game)
    game.result = {"u_final": 0.68, "verdict": "utopie"}
    game.status = GameStatus.FINISHED
    store.save_game(game)
    got = store.get_game("gr")
    assert got.status is GameStatus.FINISHED
    assert got.result == {"u_final": 0.68, "verdict": "utopie"}


def test_player_upsert_preserves_xp():
    # G11-c/RG-1 — compte joueur : upsert rafraîchit le pseudo sans clobber l'XP.
    store = SQLiteGameStore(":memory:")
    store.upsert_player(PlayerRecord(id="u1", pseudo="Laury"))
    assert store.get_player("u1").xp == 0

    store.set_player_xp("u1", 84)
    store.upsert_player(PlayerRecord(id="u1", pseudo="Laury2", xp=999))  # ne clobbe pas l'xp

    got = store.get_player("u1")
    assert (got.pseudo, got.xp) == ("Laury2", 84)  # pseudo rafraîchi, xp intact
    assert store.get_player("absent") is None


def test_xp_and_market_balance_roundtrip():
    # G12 — carrière : xp (ne baisse jamais), solde de marché (incrément), xp_history.
    store = SQLiteGameStore(":memory:")
    store.upsert_player(PlayerRecord(id="u1", pseudo="Laury"))
    assert store.get_player("u1").xp == 0 and store.get_player("u1").market_balance == 0.0

    store.set_player_xp("u1", 84)
    store.add_market_balance("u1", 12.5)
    store.add_market_balance("u1", -4.0)
    store.add_xp_history(
        XpHistoryEntry(id="x1", player_id="u1", game_id="g1", delta=84, reason="classic", ts="t1")
    )
    got = store.get_player("u1")
    assert got.xp == 84
    assert got.market_balance == 8.5
    assert [h.delta for h in store.list_xp_history("u1")] == [84]
    # upsert ne clobbe ni xp ni le solde.
    store.upsert_player(PlayerRecord(id="u1", pseudo="Laury2", xp=999))
    assert store.get_player("u1").xp == 84


def test_custom_crises_roundtrip():
    # G12-b §5 — crises maison : upsert (remplace même id), listing, delete propriétaire.
    store = SQLiteGameStore(":memory:")
    assert store.list_custom_crises() == []

    store.upsert_custom_crisis(
        CustomCrisisRecord(id="c1", owner_id="alice", crisis={"id": "c1", "title": "V1"})
    )
    store.upsert_custom_crisis(
        CustomCrisisRecord(id="c2", owner_id="bob", crisis={"id": "c2", "title": "B"})
    )
    # upsert sur le même id remplace (pas de doublon).
    store.upsert_custom_crisis(
        CustomCrisisRecord(id="c1", owner_id="alice", crisis={"id": "c1", "title": "V2"})
    )
    got = {c.id: c for c in store.list_custom_crises()}
    assert set(got) == {"c1", "c2"}
    assert got["c1"].crisis["title"] == "V2" and got["c1"].owner_id == "alice"

    # delete propriétaire uniquement : bob ne supprime pas la crise d'alice.
    assert store.delete_custom_crisis("c1", "bob") is False
    assert store.delete_custom_crisis("c1", "alice") is True
    assert {c.id for c in store.list_custom_crises()} == {"c2"}
    assert store.delete_custom_crisis("absent", "alice") is False


def test_migration_adds_ownership_columns(tmp_path):
    """Une base d'avant G11 (games sans owner_id) s'ouvre, se migre, garde ses défauts."""
    path = str(tmp_path / "pre_g11.db")
    conn = sqlite3.connect(path)
    conn.executescript(
        "CREATE TABLE games (id TEXT PRIMARY KEY, scenario TEXT NOT NULL, "
        "horizon INTEGER NOT NULL, mode TEXT NOT NULL DEFAULT 'classic', "
        "status TEXT NOT NULL, created_at TEXT NOT NULL, role TEXT NOT NULL "
        "DEFAULT 'council');"
    )
    conn.execute(
        "INSERT INTO games (id, scenario, horizon, status, created_at) "
        "VALUES ('old', 'red_sea', 5, 'running', '2026-01-01T00:00:00')"
    )
    conn.commit()
    conn.close()

    store = SQLiteGameStore(path)
    got = store.get_game("old")
    assert got is not None
    assert got.owner_id is None  # partie héritée : sans propriétaire (admin seul la voit)
    assert got.ranked is False
    assert got.difficulty == "intermediate"
    assert got.drift_enabled is True
    store.close()


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


def test_admin_flag_and_prompts_roundtrip():
    # G7-c : le flag admin survit au store ; la table prompts suit le patron transcripts.
    from storage.game_store import PromptEntry

    store = SQLiteGameStore(":memory:")
    game = _game("g9")
    game.admin = True
    store.add_game(game)
    assert store.get_game("g9").admin is True
    assert store.get_game("g9").mode == "classic"

    store.add_prompts(
        [
            PromptEntry(id="p2", round_id="r1", seq=1, country="gm", role="gm", prompt="B"),
            PromptEntry(
                id="p1", round_id="r1", seq=0, country="usa", role="country", prompt="A"
            ),
            PromptEntry(
                id="p3", round_id="r2", seq=0, country="judge", role="judge", prompt="C"
            ),
        ]
    )
    got = store.list_prompts("r1")
    assert [(e.seq, e.country) for e in got] == [(0, "usa"), (1, "gm")]
    assert store.list_prompts("inconnu") == []
    store.close()
