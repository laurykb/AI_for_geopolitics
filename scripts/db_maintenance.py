"""Maintenance des bases SQLite du projet — `games.db` (parties/joueurs) et
`research.db` (expériences du Laboratoire).

Mode par défaut = RAPPORT (dry-run), aucune écriture : compte les parties par statut/âge,
les joueurs, la taille des fichiers, et ce qui SERAIT purgé. `--apply` déclenche la purge
PRUDENTE puis `PRAGMA wal_checkpoint(TRUNCATE)` + `VACUUM` sur les deux bases.

La purge ne touche QUE les parties ORPHELINES : `owner_id` non NULL mais qui ne correspond
plus à aucun joueur de la table `players` (comptes purgés/invités d'avant le correctif de
purge, voir `app/game_api.py::delete_player`). Jamais touchées : les parties d'un joueur
existant, les parties `owner_id` NULL (ère pré-auth), et — parmi les orphelines — les
parties publiées, qui sont ANONYMISÉES (`owner_id` -> None, même geste que la suppression
de compte) plutôt que supprimées. La cascade de suppression réutilise
`storage.game_store.SQLiteGameStore.delete_game` : elle n'est pas réinventée ici.

`research.db` n'est JAMAIS purgée (les expériences sont la matière du labo) : seuls le
checkpoint WAL et le VACUUM s'appliquent.

Garde-fou : si un serveur (API) tient déjà le fichier ouvert en écriture, le script refuse
de tourner plutôt que de risquer une contention avec l'API en marche.

Usage :
    python scripts/db_maintenance.py [--games-db games.db] [--research-db research.db]
    python scripts/db_maintenance.py --apply   # purge + checkpoint + VACUUM réels
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # exécutable depuis scripts/

from storage.game_store import SQLiteGameStore  # noqa: E402

_AGE_UNDER_WEEK = "< 7 jours"
_AGE_UNDER_MONTH = "7-30 jours"
_AGE_OVER_MONTH = "> 30 jours"
_AGE_UNKNOWN = "date inconnue"


class DatabaseLockedError(RuntimeError):
    """La base SQLite est verrouillée par un autre processus (le serveur tourne)."""


@dataclass
class GamesReport:
    """Ce que `scan_games` observe, et ce que `purge_orphan_games` ferait de chaque
    partie orpheline (calculé une fois, réutilisé tel quel par l'apply — pas de re-scan
    entre le rapport affiché et l'action, pour que l'un et l'autre restent cohérents)."""

    total: int = 0
    by_status: dict[str, int] = field(default_factory=dict)
    by_age_bucket: dict[str, int] = field(default_factory=dict)
    players: int = 0
    orphans_to_delete: list[str] = field(default_factory=list)  # privées -> delete_game
    orphans_to_anonymize: list[str] = field(default_factory=list)  # publiées -> owner=None
    size_bytes: int = 0
    estimated_vacuum_bytes: int = 0


@dataclass
class ResearchReport:
    total_experiments: int = 0
    by_status: dict[str, int] = field(default_factory=dict)
    total_runs: int = 0
    size_bytes: int = 0
    wal_bytes: int = 0
    estimated_vacuum_bytes: int = 0


# --- utilitaires fichiers ------------------------------------------------------------


def _sidecar_size(path: Path, suffix: str) -> int:
    sidecar = path.with_name(path.name + suffix)
    return sidecar.stat().st_size if sidecar.exists() else 0


def _total_size(path: Path) -> int:
    """Taille du fichier principal + WAL/SHM éventuels — la vraie empreinte disque."""
    if not path.exists():
        return 0
    return path.stat().st_size + _sidecar_size(path, "-wal") + _sidecar_size(path, "-shm")


def _estimated_vacuum_size(conn: sqlite3.Connection) -> int:
    """Estimation SANS écrire : (pages utilisées) x (taille de page). Lecture pure des
    pragmas de comptabilité SQLite — ce que VACUUM récupérerait réellement."""
    page_size = conn.execute("PRAGMA page_size").fetchone()[0]
    page_count = conn.execute("PRAGMA page_count").fetchone()[0]
    freelist = conn.execute("PRAGMA freelist_count").fetchone()[0]
    return max(page_count - freelist, 0) * page_size


def _human_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("o", "Ko", "Mo", "Go"):
        if size < 1024:
            return f"{size:.0f} {unit}" if unit == "o" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} To"


def _age_bucket(created_at: str, now: datetime) -> str:
    try:
        created = datetime.fromisoformat(created_at)
    except ValueError:
        return _AGE_UNKNOWN
    if created.tzinfo is None:
        created = created.replace(tzinfo=UTC)
    age_days = (now - created).days
    if age_days < 7:
        return _AGE_UNDER_WEEK
    if age_days < 30:
        return _AGE_UNDER_MONTH
    return _AGE_OVER_MONTH


# --- garde-fou verrouillage ------------------------------------------------------------


def ensure_unlocked(path: Path) -> None:
    """Sonde une transaction d'écriture immédiate puis l'annule (aucune donnée touchée,
    y compris en dry-run). Si un autre processus tient déjà un verrou d'écriture (l'API en
    marche, en train d'écrire), `BEGIN IMMEDIATE` échoue et on refuse de continuer."""
    if not path.exists():
        return
    conn = sqlite3.connect(str(path), timeout=0.5)
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("ROLLBACK")
    except sqlite3.OperationalError as exc:
        raise DatabaseLockedError(
            f"{path} est verrouillée par un autre processus — éteins l'API d'abord."
        ) from exc
    finally:
        conn.close()


# --- games.db --------------------------------------------------------------------------


def scan_games(path: Path, *, now: datetime | None = None) -> GamesReport:
    """Lecture SEULE : compte, classe par statut/âge, et repère les orphelines sans rien
    modifier. `purge_orphan_games` consomme directement les listes produites ici."""
    if not path.exists():
        return GamesReport()
    now = now or datetime.now(UTC)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    try:
        games = conn.execute(
            "SELECT id, status, created_at, owner_id, published FROM games"
        ).fetchall()
        players = {row[0] for row in conn.execute("SELECT id FROM players")}
        by_status: dict[str, int] = {}
        by_age: dict[str, int] = {}
        orphans_to_delete: list[str] = []
        orphans_to_anonymize: list[str] = []
        for row in games:
            by_status[row["status"]] = by_status.get(row["status"], 0) + 1
            bucket = _age_bucket(row["created_at"], now)
            by_age[bucket] = by_age.get(bucket, 0) + 1
            owner_id = row["owner_id"]
            if owner_id is not None and owner_id not in players:
                if row["published"]:
                    orphans_to_anonymize.append(row["id"])
                else:
                    orphans_to_delete.append(row["id"])
        size_bytes = _total_size(path)
        estimated = _estimated_vacuum_size(conn)
    finally:
        conn.close()
    return GamesReport(
        total=len(games),
        by_status=by_status,
        by_age_bucket=by_age,
        players=len(players),
        orphans_to_delete=orphans_to_delete,
        orphans_to_anonymize=orphans_to_anonymize,
        size_bytes=size_bytes,
        estimated_vacuum_bytes=estimated,
    )


def purge_orphan_games(path: Path, report: GamesReport) -> None:
    """--apply uniquement. Réutilise `SQLiteGameStore.delete_game` (cascade rounds /
    transcripts / prompts / snapshot / campaign_scores déjà correcte, pas réinventée) et
    `set_game_owner` pour l'anonymisation — même geste que `DELETE /api/players/{id}`."""
    if not report.orphans_to_delete and not report.orphans_to_anonymize:
        return
    store = SQLiteGameStore(str(path))
    try:
        for game_id in report.orphans_to_delete:
            store.delete_game(game_id)
        for game_id in report.orphans_to_anonymize:
            store.set_game_owner(game_id, None)
    finally:
        store.close()


# --- research.db -----------------------------------------------------------------------


def scan_research(path: Path) -> ResearchReport:
    """Lecture SEULE. Rien n'est jamais purgé côté recherche — seul le rapport (statuts,
    taille, WAL) sert à décider s'il vaut la peine de checkpointer/vacuumer."""
    if not path.exists():
        return ResearchReport()
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    try:
        experiments = conn.execute("SELECT status FROM research_experiments").fetchall()
        by_status: dict[str, int] = {}
        for row in experiments:
            by_status[row["status"]] = by_status.get(row["status"], 0) + 1
        total_runs = conn.execute("SELECT COUNT(*) FROM research_runs").fetchone()[0]
        estimated = _estimated_vacuum_size(conn)
    finally:
        conn.close()
    return ResearchReport(
        total_experiments=len(experiments),
        by_status=by_status,
        total_runs=total_runs,
        size_bytes=_total_size(path),
        wal_bytes=_sidecar_size(path, "-wal"),
        estimated_vacuum_bytes=estimated,
    )


# --- checkpoint + VACUUM (commun aux deux bases) ----------------------------------------


def checkpoint_and_vacuum(path: Path) -> tuple[int, int]:
    """`PRAGMA wal_checkpoint(TRUNCATE)` + `VACUUM`, avec un second checkpoint après coup :
    VACUUM est lui-même une transaction d'écriture, elle peut laisser quelques frames dans
    un WAL fraîchement retronqué — le second passage les évacue pour de bon. No-op propre
    (0, 0) si le fichier n'existe pas encore. Renvoie (taille avant, taille après)."""
    if not path.exists():
        return (0, 0)
    before = _total_size(path)
    conn = sqlite3.connect(str(path))
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.execute("VACUUM")
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.commit()
    finally:
        conn.close()
    after = _total_size(path)
    return before, after


# --- rapport lisible ---------------------------------------------------------------------


def _print_games_report(report: GamesReport) -> None:
    print(
        f"Parties : {report.total} — taille {_human_size(report.size_bytes)} "
        f"(estimé après VACUUM : {_human_size(report.estimated_vacuum_bytes)})"
    )
    print(f"  par statut : {report.by_status or '—'}")
    print(f"  par âge    : {report.by_age_bucket or '—'}")
    print(f"Joueurs : {report.players}")
    print(
        f"Orphelines (owner_id sans joueur) : "
        f"{len(report.orphans_to_delete)} à supprimer, "
        f"{len(report.orphans_to_anonymize)} publiées à anonymiser"
    )


def _print_research_report(report: ResearchReport) -> None:
    print(
        f"Expériences : {report.total_experiments} ({report.total_runs} runs) — "
        f"taille {_human_size(report.size_bytes)}, WAL {_human_size(report.wal_bytes)} "
        f"(estimé après VACUUM : {_human_size(report.estimated_vacuum_bytes)})"
    )
    print(f"  par statut : {report.by_status or '—'}")
    print("  rien n'est purgé côté recherche (seulement checkpoint + VACUUM)")


# --- CLI -----------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--games-db", default="games.db", help="chemin vers games.db")
    parser.add_argument("--research-db", default="research.db", help="chemin vers research.db")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="applique la purge des orphelines + checkpoint/VACUUM (par défaut : rapport seul)",
    )
    args = parser.parse_args(argv)

    games_path = Path(args.games_db)
    research_path = Path(args.research_db)

    try:
        ensure_unlocked(games_path)
        ensure_unlocked(research_path)
    except DatabaseLockedError as exc:
        print(f"[db_maintenance] {exc}", file=sys.stderr)
        return 1

    print("=== games.db ===")
    games_report = scan_games(games_path)
    _print_games_report(games_report)
    if args.apply:
        purge_orphan_games(games_path, games_report)
        before, after = checkpoint_and_vacuum(games_path)
        print(f"  checkpoint + VACUUM : {_human_size(before)} -> {_human_size(after)}")
    else:
        print("  [dry-run] rien n'a été modifié — relance avec --apply pour agir")

    print()
    print("=== research.db ===")
    research_report = scan_research(research_path)
    _print_research_report(research_report)
    if args.apply:
        before, after = checkpoint_and_vacuum(research_path)
        print(f"  checkpoint + VACUUM : {_human_size(before)} -> {_human_size(after)}")
    else:
        print("  [dry-run] rien n'a été modifié — relance avec --apply pour agir")

    return 0


if __name__ == "__main__":
    sys.exit(main())
