"""File SQLite reprenable des expériences de campagne.

Une ligne est persistée avant tout appel de modèle. La réclamation d'un run est atomique,
ce qui évite les doublons si l'UI relance ou si deux workers se présentent en même temps.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Iterator
from datetime import UTC, datetime

from pydantic import BaseModel, Field

from simulation.research_lab import LabRunResult, RunStatus

_SCHEMA = """
CREATE TABLE IF NOT EXISTS research_experiments (
    id TEXT PRIMARY KEY,
    protocol_id TEXT NOT NULL,
    title TEXT NOT NULL,
    status TEXT NOT NULL,
    manifest_json TEXT NOT NULL,
    cancel_requested INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS research_runs (
    id TEXT PRIMARY KEY,
    experiment_id TEXT NOT NULL,
    cell_id TEXT NOT NULL,
    protocol_id TEXT NOT NULL,
    model_id TEXT NOT NULL,
    model_digest TEXT NOT NULL DEFAULT '',
    opponent_model_id TEXT NOT NULL DEFAULT '',
    opponent_model_digest TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL,
    factors_json TEXT NOT NULL,
    repetition INTEGER NOT NULL,
    seed INTEGER NOT NULL,
    prompt_version TEXT NOT NULL,
    queue_order INTEGER NOT NULL DEFAULT 0,
    result_json TEXT,
    checkpoint_json TEXT,
    error_code TEXT NOT NULL DEFAULT '',
    claimed_at TEXT,
    updated_at TEXT NOT NULL,
    UNIQUE(experiment_id, cell_id, model_id)
);
CREATE INDEX IF NOT EXISTS idx_research_runs_queue
ON research_runs(experiment_id, status, queue_order, seed, id);
CREATE INDEX IF NOT EXISTS idx_research_runs_claim_v2
ON research_runs(experiment_id, status, queue_order, seed, id);
CREATE INDEX IF NOT EXISTS idx_research_runs_progress
ON research_runs(experiment_id, model_id, status);
"""


def _now() -> str:
    return datetime.now(UTC).isoformat()


class ExperimentRecord(BaseModel):
    id: str
    protocol_id: str
    title: str
    status: RunStatus = "queued"
    manifest: dict = Field(default_factory=dict)
    cancel_requested: bool = False
    created_at: str
    updated_at: str


class QueuedRun(BaseModel):
    id: str
    experiment_id: str
    cell_id: str
    protocol_id: str
    model_id: str
    model_digest: str = ""
    opponent_model_id: str = ""
    opponent_model_digest: str = ""
    status: RunStatus = "queued"
    factors: dict = Field(default_factory=dict)
    repetition: int
    seed: int
    prompt_version: str
    queue_order: int = Field(0, ge=0)
    result: LabRunResult | None = None
    checkpoint: dict | None = None
    error_code: str = ""
    claimed_at: str | None = None
    updated_at: str


class ExperimentProgress(BaseModel):
    experiment: ExperimentRecord
    total: int
    queued: int
    running: int
    completed: int
    failed: int
    cancelled: int
    by_model: dict[str, dict[str, int]] = Field(default_factory=dict)


class SQLiteResearchStore:
    def __init__(self, path: str = "research.db") -> None:
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        self._conn.execute("PRAGMA busy_timeout = 5000")
        if path != ":memory:":
            # Les lectures de progression ne bloquent plus les écritures du worker.
            self._conn.execute("PRAGMA journal_mode = WAL")
            self._conn.execute("PRAGMA synchronous = NORMAL")
        with self._conn:
            self._conn.executescript(_SCHEMA)
            experiment_columns = {
                row["name"]
                for row in self._conn.execute(
                    "PRAGMA table_info(research_experiments)"
                ).fetchall()
            }
            if "cancel_requested" not in experiment_columns:
                self._conn.execute(
                    "ALTER TABLE research_experiments ADD COLUMN "
                    "cancel_requested INTEGER NOT NULL DEFAULT 0"
                )
            columns = {
                row["name"]
                for row in self._conn.execute("PRAGMA table_info(research_runs)").fetchall()
            }
            if "queue_order" not in columns:
                self._conn.execute(
                    "ALTER TABLE research_runs ADD COLUMN queue_order INTEGER NOT NULL DEFAULT 0"
                )
                # Les expériences historiques restent groupées par modèle après migration.
                self._conn.execute(
                    """UPDATE research_runs AS current SET queue_order = (
                    SELECT COUNT(DISTINCT previous.model_id) FROM research_runs AS previous
                    WHERE previous.experiment_id = current.experiment_id
                    AND previous.model_id < current.model_id
                    )"""
                )
            if "opponent_model_id" not in columns:
                self._conn.execute(
                    "ALTER TABLE research_runs ADD COLUMN opponent_model_id "
                    "TEXT NOT NULL DEFAULT ''"
                )
            if "opponent_model_digest" not in columns:
                self._conn.execute(
                    "ALTER TABLE research_runs ADD COLUMN opponent_model_digest "
                    "TEXT NOT NULL DEFAULT ''"
                )
            if "checkpoint_json" not in columns:
                self._conn.execute(
                    "ALTER TABLE research_runs ADD COLUMN checkpoint_json TEXT"
                )

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def create_experiment(
        self, record: ExperimentRecord, runs: list[QueuedRun]
    ) -> ExperimentRecord:
        """Crée le manifeste et toute la file dans une seule transaction."""

        with self._lock, self._conn:
            self._conn.execute(
                """INSERT INTO research_experiments
                (id, protocol_id, title, status, manifest_json, cancel_requested,
                 created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    record.id,
                    record.protocol_id,
                    record.title,
                    record.status,
                    json.dumps(record.manifest, ensure_ascii=False),
                    int(record.cancel_requested),
                    record.created_at,
                    record.updated_at,
                ),
            )
            self._conn.executemany(
                """INSERT INTO research_runs
                (id, experiment_id, cell_id, protocol_id, model_id, model_digest,
                 opponent_model_id, opponent_model_digest, status,
                 factors_json, repetition, seed, prompt_version, queue_order,
                 result_json, checkpoint_json, error_code,
                 claimed_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?, ?)""",
                [
                    (
                        run.id,
                        run.experiment_id,
                        run.cell_id,
                        run.protocol_id,
                        run.model_id,
                        run.model_digest,
                        run.opponent_model_id,
                        run.opponent_model_digest,
                        run.status,
                        json.dumps(run.factors, ensure_ascii=False),
                        run.repetition,
                        run.seed,
                        run.prompt_version,
                        run.queue_order,
                        run.error_code,
                        run.claimed_at,
                        run.updated_at,
                    )
                    for run in runs
                ],
            )
        return record

    def get_experiment(self, experiment_id: str) -> ExperimentRecord | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM research_experiments WHERE id = ?", (experiment_id,)
            ).fetchone()
        return _experiment(row) if row else None

    def list_experiments(self, limit: int = 50) -> list[ExperimentRecord]:
        limit = max(1, min(limit, 200))
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM research_experiments ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [_experiment(row) for row in rows]

    def progress(self, experiment_id: str) -> ExperimentProgress | None:
        experiment = self.get_experiment(experiment_id)
        if experiment is None:
            return None
        with self._lock:
            rows = self._conn.execute(
                """SELECT model_id, status, COUNT(*) AS n FROM research_runs
                WHERE experiment_id = ? GROUP BY model_id, status""",
                (experiment_id,),
            ).fetchall()
        totals = {status: 0 for status in ("queued", "running", "completed", "failed", "cancelled")}
        by_model: dict[str, dict[str, int]] = {}
        for row in rows:
            status, count, model_id = str(row["status"]), int(row["n"]), str(row["model_id"])
            totals[status] = totals.get(status, 0) + count
            by_model.setdefault(model_id, {})[status] = count
        return ExperimentProgress(
            experiment=experiment,
            total=sum(totals.values()),
            by_model=by_model,
            **totals,
        )

    def claim_next(self, experiment_id: str) -> QueuedRun | None:
        """Réclame atomiquement le prochain run, groupé par modèle pour limiter les reloads."""

        claimed = _now()
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                row = self._conn.execute(
                    """SELECT * FROM research_runs
                    WHERE experiment_id = ? AND status = 'queued'
                    ORDER BY queue_order, seed, id LIMIT 1""",
                    (experiment_id,),
                ).fetchone()
                if row is None:
                    self._conn.commit()
                    return None
                updated = self._conn.execute(
                    """UPDATE research_runs SET status = 'running', claimed_at = ?, updated_at = ?
                    WHERE id = ? AND status = 'queued'""",
                    (claimed, claimed, row["id"]),
                ).rowcount
                if updated != 1:
                    self._conn.rollback()
                    return None
                self._conn.execute(
                    """UPDATE research_experiments SET status = 'running', updated_at = ?
                    WHERE id = ?""",
                    (claimed, experiment_id),
                )
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise
        return self.get_run(str(row["id"]))

    def get_run(self, run_id: str) -> QueuedRun | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM research_runs WHERE id = ?", (run_id,)
            ).fetchone()
        return _run(row) if row else None

    def current_running(self, experiment_id: str) -> QueuedRun | None:
        """Restitue l'essai humain ouvert après rechargement au lieu d'en réclamer un autre."""

        with self._lock:
            row = self._conn.execute(
                """SELECT * FROM research_runs WHERE experiment_id = ? AND status = 'running'
                ORDER BY claimed_at, id LIMIT 1""",
                (experiment_id,),
            ).fetchone()
        return _run(row) if row else None

    def list_runs(self, experiment_id: str) -> list[QueuedRun]:
        """Restitue le plan ordonné, notamment pour une réplication à l'identique."""

        with self._lock:
            rows = self._conn.execute(
                """SELECT * FROM research_runs WHERE experiment_id = ?
                ORDER BY queue_order, seed, id""",
                (experiment_id,),
            ).fetchall()
        return [_run(row) for row in rows]

    def finish_run(self, run_id: str, result: LabRunResult, model_digest: str = "") -> None:
        now = _now()
        with self._lock, self._conn:
            row = self._conn.execute(
                "SELECT experiment_id FROM research_runs WHERE id = ?", (run_id,)
            ).fetchone()
            if row is None:
                raise KeyError(run_id)
            self._conn.execute(
                """UPDATE research_runs SET status = ?, result_json = ?, checkpoint_json = NULL,
                error_code = ?,
                model_digest = ?, updated_at = ? WHERE id = ?""",
                (
                    result.status,
                    result.model_dump_json(),
                    result.error_code,
                    model_digest,
                    now,
                    run_id,
                ),
            )
            self._finalize_if_done(str(row["experiment_id"]), now)

    def save_checkpoint(self, run_id: str, checkpoint: dict) -> None:
        """Persiste atomiquement un tour validé sans marquer le run comme terminé."""

        now = _now()
        with self._lock, self._conn:
            updated = self._conn.execute(
                """UPDATE research_runs SET checkpoint_json = ?, updated_at = ?
                WHERE id = ? AND status = 'running'""",
                (json.dumps(checkpoint, ensure_ascii=False), now, run_id),
            ).rowcount
            if updated != 1:
                raise KeyError(run_id)

    def fail_run(self, run_id: str, error_code: str) -> None:
        now = _now()
        with self._lock, self._conn:
            row = self._conn.execute(
                "SELECT experiment_id FROM research_runs WHERE id = ?", (run_id,)
            ).fetchone()
            if row is None:
                raise KeyError(run_id)
            self._conn.execute(
                """UPDATE research_runs SET status = 'failed', error_code = ?, updated_at = ?
                WHERE id = ?""",
                (error_code[:200], now, run_id),
            )
            self._finalize_if_done(str(row["experiment_id"]), now)

    def requeue_running(self, experiment_id: str) -> int:
        """Reprise explicite après crash : les runs incomplets redeviennent visibles."""

        now = _now()
        with self._lock, self._conn:
            count = self._conn.execute(
                """UPDATE research_runs SET status = 'queued', claimed_at = NULL, updated_at = ?
                WHERE experiment_id = ? AND status = 'running'""",
                (now, experiment_id),
            ).rowcount
        return count

    def cancel_experiment(self, experiment_id: str) -> int:
        """Annule le reliquat; l'appel Ollama courant termine sans lancer le suivant."""

        now = _now()
        with self._lock, self._conn:
            exists = self._conn.execute(
                "SELECT 1 FROM research_experiments WHERE id = ?", (experiment_id,)
            ).fetchone()
            if exists is None:
                raise KeyError(experiment_id)
            count = self._conn.execute(
                """UPDATE research_runs SET status = 'cancelled', updated_at = ?
                WHERE experiment_id = ? AND status = 'queued'""",
                (now, experiment_id),
            ).rowcount
            self._conn.execute(
                """UPDATE research_experiments SET cancel_requested = 1, updated_at = ?
                WHERE id = ?""",
                (now, experiment_id),
            )
            self._finalize_if_done(experiment_id, now)
        return count

    def is_cancel_requested(self, experiment_id: str) -> bool:
        with self._lock:
            row = self._conn.execute(
                "SELECT cancel_requested FROM research_experiments WHERE id = ?",
                (experiment_id,),
            ).fetchone()
        return bool(row and row["cancel_requested"])

    def cancel_run(self, run_id: str) -> None:
        """Ferme proprement un run coopératif interrompu entre deux tours."""

        now = _now()
        with self._lock, self._conn:
            row = self._conn.execute(
                "SELECT experiment_id FROM research_runs WHERE id = ?", (run_id,)
            ).fetchone()
            if row is None:
                raise KeyError(run_id)
            self._conn.execute(
                """UPDATE research_runs SET status = 'cancelled', error_code = ?,
                updated_at = ? WHERE id = ?""",
                ("cancelled_between_turns", now, run_id),
            )
            self._finalize_if_done(str(row["experiment_id"]), now)

    def list_results(self, experiment_id: str, limit: int = 5_000) -> list[LabRunResult]:
        limit = max(1, min(limit, 50_000))
        with self._lock:
            rows = self._conn.execute(
                """SELECT result_json FROM research_runs WHERE experiment_id = ?
                AND result_json IS NOT NULL ORDER BY id LIMIT ?""",
                (experiment_id, limit),
            ).fetchall()
        return [LabRunResult.model_validate_json(row["result_json"]) for row in rows]

    def iter_export_rows(
        self, experiment_id: str, batch_size: int = 250
    ) -> Iterator[dict[str, object]]:
        """Diffuse les runs par lots au lieu de matérialiser un export massif en RAM."""

        batch_size = max(1, min(batch_size, 1_000))
        last_rowid = 0
        while True:
            with self._lock:
                rows = self._conn.execute(
                    """SELECT rowid AS export_rowid, id, cell_id, protocol_id, model_id,
                    model_digest, opponent_model_id, opponent_model_digest, status,
                    factors_json, repetition, seed, prompt_version, queue_order, result_json,
                    checkpoint_json,
                    error_code, claimed_at, updated_at FROM research_runs
                    WHERE experiment_id = ? AND rowid > ? ORDER BY rowid LIMIT ?""",
                    (experiment_id, last_rowid, batch_size),
                ).fetchall()
            if not rows:
                return
            for row in rows:
                yield {
                    "record_type": "run",
                    "id": row["id"],
                    "cell_id": row["cell_id"],
                    "protocol_id": row["protocol_id"],
                    "model_id": row["model_id"],
                    "model_digest": row["model_digest"],
                    "opponent_model_id": row["opponent_model_id"],
                    "opponent_model_digest": row["opponent_model_digest"],
                    "status": row["status"],
                    "factors": json.loads(row["factors_json"]),
                    "repetition": row["repetition"],
                    "seed": row["seed"],
                    "prompt_version": row["prompt_version"],
                    "queue_order": row["queue_order"],
                    "result": json.loads(row["result_json"]) if row["result_json"] else None,
                    "checkpoint": (
                        json.loads(row["checkpoint_json"]) if row["checkpoint_json"] else None
                    ),
                    "error_code": row["error_code"],
                    "claimed_at": row["claimed_at"],
                    "updated_at": row["updated_at"],
                }
            last_rowid = int(rows[-1]["export_rowid"])

    def _finalize_if_done(self, experiment_id: str, now: str) -> None:
        remaining = self._conn.execute(
            """SELECT COUNT(*) FROM research_runs WHERE experiment_id = ?
            AND status IN ('queued', 'running')""",
            (experiment_id,),
        ).fetchone()[0]
        if remaining == 0:
            failures = self._conn.execute(
                """SELECT COUNT(*) FROM research_runs WHERE experiment_id = ?
                AND status = 'failed'""",
                (experiment_id,),
            ).fetchone()[0]
            cancellations = self._conn.execute(
                """SELECT COUNT(*) FROM research_runs WHERE experiment_id = ?
                AND status = 'cancelled'""",
                (experiment_id,),
            ).fetchone()[0]
            status = "cancelled" if cancellations else "failed" if failures else "completed"
            self._conn.execute(
                "UPDATE research_experiments SET status = ?, updated_at = ? WHERE id = ?",
                (status, now, experiment_id),
            )


def _experiment(row: sqlite3.Row) -> ExperimentRecord:
    return ExperimentRecord(
        id=row["id"],
        protocol_id=row["protocol_id"],
        title=row["title"],
        status=row["status"],
        manifest=json.loads(row["manifest_json"]),
        cancel_requested=bool(row["cancel_requested"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _run(row: sqlite3.Row) -> QueuedRun:
    return QueuedRun(
        id=row["id"],
        experiment_id=row["experiment_id"],
        cell_id=row["cell_id"],
        protocol_id=row["protocol_id"],
        model_id=row["model_id"],
        model_digest=row["model_digest"],
        opponent_model_id=row["opponent_model_id"],
        opponent_model_digest=row["opponent_model_digest"],
        status=row["status"],
        factors=json.loads(row["factors_json"]),
        repetition=row["repetition"],
        seed=row["seed"],
        prompt_version=row["prompt_version"],
        queue_order=row["queue_order"],
        result=(
            LabRunResult.model_validate_json(row["result_json"]) if row["result_json"] else None
        ),
        checkpoint=(json.loads(row["checkpoint_json"]) if row["checkpoint_json"] else None),
        error_code=row["error_code"],
        claimed_at=row["claimed_at"],
        updated_at=row["updated_at"],
    )
