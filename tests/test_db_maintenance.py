"""TDD pour `scripts/db_maintenance.py` — l'outillage de nettoyage de `games.db` /
`research.db`. Fixtures construites via `SQLiteGameStore`/`SQLiteResearchStore` réels
(jamais de SQL à la main pour le schéma applicatif) pour survivre aux migrations.

Couvre les décisions arbitrées de la tâche : le dry-run ne modifie rien ; `--apply` ne
purge QUE les parties orphelines (owner_id fantôme) non publiées ; une orpheline publiée
est anonymisée (comme `DELETE /players/{id}`), jamais supprimée ; le WAL est tronqué et
VACUUM réduit la taille ; le script refuse de tourner sur une base verrouillée.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

from research.store import ExperimentRecord, SQLiteResearchStore
from storage.game_store import GameRecord, GameStatus, PlayerRecord, SQLiteGameStore

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import db_maintenance as dbm  # noqa: E402

# --- fixtures ---------------------------------------------------------------------


def _game(
    id_: str,
    *,
    owner_id: str | None,
    published: bool = False,
    status: GameStatus = GameStatus.RUNNING,
    created_at: str = "2026-01-01T00:00:00+00:00",
) -> GameRecord:
    return GameRecord(
        id=id_,
        scenario="crise-test",
        horizon=5,
        status=status,
        created_at=created_at,
        owner_id=owner_id,
        published=published,
    )


@pytest.fixture
def games_db(tmp_path: Path) -> Path:
    path = tmp_path / "games.db"
    store = SQLiteGameStore(str(path))
    store.upsert_player(PlayerRecord(id="alive", pseudo="Alice", created_at="t"))
    # joueur vivant -> jamais touchée
    store.add_game(_game("g-alive-owner", owner_id="alive"))
    # owner_id fantôme, jamais publiée -> supprimée en cascade
    store.add_game(_game("g-orphan-private", owner_id="ghost"))
    # owner_id fantôme, publiée -> anonymisée (jamais supprimée)
    store.add_game(_game("g-orphan-published", owner_id="ghost2", published=True))
    # ère pré-auth (owner_id NULL) -> jamais touchée, quel que soit son âge
    store.add_game(
        _game("g-owner-null", owner_id=None, created_at="2026-07-19T00:00:00+00:00")
    )
    # partie récente et finie, pour peupler le rapport par statut/âge
    store.add_game(
        _game(
            "g-finished-recent",
            owner_id="alive",
            status=GameStatus.FINISHED,
            created_at="2026-07-19T00:00:00+00:00",
        )
    )
    store.close()
    return path


def _experiment(id_: str, status: str) -> ExperimentRecord:
    return ExperimentRecord(
        id=id_,
        protocol_id="uranium-alpha-beta-v1",
        title="essai",
        status=status,
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
    )


@pytest.fixture
def research_db(tmp_path: Path) -> Path:
    path = tmp_path / "research.db"
    store = SQLiteResearchStore(str(path))
    store.create_experiment(_experiment("e-completed", "completed"), [])
    store.create_experiment(_experiment("e-queued", "queued"), [])
    store.close()
    return path


def _bloat_with_unflushed_wal(path: Path) -> sqlite3.Connection:
    """Simule une base fragmentée + un WAL jamais checkpointé (comme `research.db`
    en prod) : sans ça, VACUUM n'a rien à réclamer et le test ne prouverait rien.
    Table de service générique — la fonction testée est agnostique du schéma.

    Renvoie la connexion SANS la fermer : SQLite checkpointe et supprime le WAL tout
    seul quand la DERNIÈRE connexion se ferme, ce qui effacerait la preuve avant même
    que le test ait pu constater le « avant ». L'appelant la ferme une fois fini."""
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA wal_autocheckpoint = 0")  # pas d'auto-checkpoint furtif
    conn.execute("CREATE TABLE _filler (blob TEXT)")
    blob = "x" * 4000
    conn.executemany("INSERT INTO _filler (blob) VALUES (?)", [(blob,) for _ in range(600)])
    conn.commit()
    conn.execute("DELETE FROM _filler WHERE rowid % 2 = 0")  # fragmente : pages libres
    conn.commit()
    return conn


# --- scan_games ---------------------------------------------------------------------


def test_scan_games_reports_counts_ages_and_orphans(games_db: Path):
    from datetime import UTC, datetime

    report = dbm.scan_games(games_db, now=datetime(2026, 7, 20, tzinfo=UTC))

    assert report.total == 5
    assert report.players == 1
    assert report.by_status == {"running": 4, "finished": 1}
    assert report.by_age_bucket.get("> 30 jours", 0) == 3  # les 3 créées en janvier
    assert report.by_age_bucket.get("< 7 jours", 0) == 2  # owner-null + finished-recent
    assert report.orphans_to_delete == ["g-orphan-private"]
    assert report.orphans_to_anonymize == ["g-orphan-published"]


def test_scan_games_is_read_only(games_db: Path):
    """Le simple scan (mode rapport) ne doit rien écrire dans le fichier."""
    before = games_db.read_bytes()
    dbm.scan_games(games_db)
    assert games_db.read_bytes() == before


# --- scan_research --------------------------------------------------------------------


def test_scan_research_reports_counts(research_db: Path):
    report = dbm.scan_research(research_db)
    assert report.total_experiments == 2
    assert report.by_status == {"completed": 1, "queued": 1}


# --- purge_orphan_games (--apply) -------------------------------------------------------


def test_purge_deletes_only_the_unpublished_orphan(games_db: Path):
    report = dbm.scan_games(games_db)
    dbm.purge_orphan_games(games_db, report)

    store = SQLiteGameStore(str(games_db))
    try:
        assert store.get_game("g-orphan-private") is None
        # la partie vivante et la partie sans owner (pré-auth) sont intactes
        alive = store.get_game("g-alive-owner")
        assert alive is not None and alive.owner_id == "alive"
        orphan_null = store.get_game("g-owner-null")
        assert orphan_null is not None and orphan_null.owner_id is None
        finished = store.get_game("g-finished-recent")
        assert finished is not None
    finally:
        store.close()


def test_purge_anonymizes_the_published_orphan_instead_of_deleting_it(games_db: Path):
    report = dbm.scan_games(games_db)
    dbm.purge_orphan_games(games_db, report)

    store = SQLiteGameStore(str(games_db))
    try:
        survivor = store.get_game("g-orphan-published")
        assert survivor is not None
        assert survivor.owner_id is None
        assert survivor.published is True
    finally:
        store.close()


def test_dry_run_never_calls_purge_leaves_everything(games_db: Path):
    before = games_db.read_bytes()
    report = dbm.scan_games(games_db)
    # dry-run = ne PAS appeler purge_orphan_games (c'est le contrat de main() sans --apply)
    assert dbm.scan_games(games_db) == report
    assert games_db.read_bytes() == before


# --- checkpoint_and_vacuum ------------------------------------------------------------


def test_checkpoint_and_vacuum_truncates_wal_and_shrinks_size(research_db: Path):
    keeper = _bloat_with_unflushed_wal(research_db)
    try:
        wal_path = research_db.with_name(research_db.name + "-wal")
        assert wal_path.exists() and wal_path.stat().st_size > 0

        before, after = dbm.checkpoint_and_vacuum(research_db)

        assert after < before
        assert not wal_path.exists() or wal_path.stat().st_size == 0
    finally:
        keeper.close()


def test_checkpoint_and_vacuum_is_a_noop_on_a_missing_file(tmp_path: Path):
    missing = tmp_path / "absent.db"
    assert dbm.checkpoint_and_vacuum(missing) == (0, 0)


# --- garde-fou verrouillage ------------------------------------------------------------


def test_ensure_unlocked_raises_when_another_writer_holds_the_db(games_db: Path):
    blocker = sqlite3.connect(str(games_db), timeout=0.1)
    blocker.execute("BEGIN IMMEDIATE")
    try:
        with pytest.raises(dbm.DatabaseLockedError):
            dbm.ensure_unlocked(games_db)
    finally:
        blocker.execute("ROLLBACK")
        blocker.close()


def test_ensure_unlocked_passes_on_an_idle_database(games_db: Path):
    dbm.ensure_unlocked(games_db)  # ne lève rien


def test_ensure_unlocked_passes_on_a_missing_file(tmp_path: Path):
    dbm.ensure_unlocked(tmp_path / "absent.db")  # ne lève rien


# --- main() (câblage CLI bout en bout) --------------------------------------------------


def test_main_dry_run_leaves_both_databases_untouched(games_db: Path, research_db: Path):
    games_before = games_db.read_bytes()
    research_before = research_db.read_bytes()

    code = dbm.main(["--games-db", str(games_db), "--research-db", str(research_db)])

    assert code == 0
    assert games_db.read_bytes() == games_before
    assert research_db.read_bytes() == research_before


def test_main_apply_purges_and_checkpoints(games_db: Path, research_db: Path):
    code = dbm.main(
        ["--games-db", str(games_db), "--research-db", str(research_db), "--apply"]
    )
    assert code == 0

    store = SQLiteGameStore(str(games_db))
    try:
        assert store.get_game("g-orphan-private") is None
        survivor = store.get_game("g-orphan-published")
        assert survivor is not None and survivor.owner_id is None
        assert store.get_game("g-alive-owner") is not None
    finally:
        store.close()


def test_main_refuses_to_run_on_a_locked_database(games_db: Path, research_db: Path):
    blocker = sqlite3.connect(str(games_db), timeout=0.1)
    blocker.execute("BEGIN IMMEDIATE")
    try:
        before = games_db.read_bytes()
        code = dbm.main(
            ["--games-db", str(games_db), "--research-db", str(research_db), "--apply"]
        )
        assert code != 0
        assert games_db.read_bytes() == before
    finally:
        blocker.execute("ROLLBACK")
        blocker.close()
