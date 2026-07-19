"""Profile reproductible de la file scientifique à sa taille maximale.

Usage: ``python -m scripts.profile_research_scaling --runs 10000``.
Le rapport JSON est écrit sur stdout; la base temporaire est automatiquement supprimée.
"""

from __future__ import annotations

import argparse
import json
import statistics
import tempfile
import time
import tracemalloc
from datetime import UTC, datetime
from pathlib import Path

from research.store import ExperimentRecord, QueuedRun, SQLiteResearchStore


def _elapsed_ms(start: float) -> float:
    return (time.perf_counter() - start) * 1_000


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round((len(ordered) - 1) * fraction))]


def profile(run_count: int, polls: int) -> dict[str, object]:
    now = datetime.now(UTC).isoformat()
    with tempfile.TemporaryDirectory(prefix="geopolitics-research-profile-") as directory:
        path = Path(directory) / "profile.db"
        store = SQLiteResearchStore(str(path))
        record = ExperimentRecord(
            id="exp-scaling-profile",
            protocol_id="scaling-profile-v1",
            title="Scaling profile",
            manifest={"planned_runs": run_count},
            created_at=now,
            updated_at=now,
        )
        runs = [
            QueuedRun(
                id=f"profile-{index:05d}",
                experiment_id=record.id,
                cell_id=f"cell-{index:05d}",
                protocol_id=record.protocol_id,
                model_id=f"model-{index // max(1, run_count // 4)}",
                model_digest="profile",
                factors={"condition": index % 14},
                repetition=index % 300 + 1,
                seed=index,
                prompt_version="profile-v1",
                queue_order=index // max(1, run_count // 4),
                updated_at=now,
            )
            for index in range(run_count)
        ]

        tracemalloc.start()
        started = time.perf_counter()
        store.create_experiment(record, runs)
        create_ms = _elapsed_ms(started)
        _, create_peak = tracemalloc.get_traced_memory()
        tracemalloc.reset_peak()

        progress_latencies = []
        for _ in range(polls):
            started = time.perf_counter()
            progress = store.progress(record.id)
            progress_latencies.append(_elapsed_ms(started))
        assert progress is not None and progress.total == run_count

        started = time.perf_counter()
        exported = sum(1 for _ in store.iter_export_rows(record.id))
        export_ms = _elapsed_ms(started)
        _, export_peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        db_bytes = path.stat().st_size
        store.close()
        return {
            "schema_version": 1,
            "run_count": run_count,
            "poll_samples": polls,
            "create_ms": round(create_ms, 2),
            "create_runs_per_second": round(run_count / (create_ms / 1_000), 1),
            "progress_ms_median": round(statistics.median(progress_latencies), 3),
            "progress_ms_p95": round(_percentile(progress_latencies, 0.95), 3),
            "export_ms": round(export_ms, 2),
            "export_rows_per_second": round(exported / (export_ms / 1_000), 1),
            "create_peak_memory_mib": round(create_peak / 1_048_576, 2),
            "export_peak_memory_mib": round(export_peak / 1_048_576, 2),
            "database_mib": round(db_bytes / 1_048_576, 2),
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=10_000)
    parser.add_argument("--polls", type=int, default=100)
    args = parser.parse_args()
    runs = max(1, min(args.runs, 50_000))
    polls = max(1, min(args.polls, 1_000))
    print(json.dumps(profile(runs, polls), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
