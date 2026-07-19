"""Smoke test structuré et benchmark des modèles Ollama du laboratoire.

Le script utilise le vrai schéma scientifique, une seed fixe et décharge chaque modèle.
Il n'altère aucune expérience et écrit son rapport JSON sur stdout.
Usage: ``python -m scripts.benchmark_research_models``.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, datetime

import ollama

from research.runner import PROMPT_VERSION, _unload, execute_run
from research.store import QueuedRun
from simulation.model_registry import model_panel_view


class MeasuringClient:
    def __init__(self, timeout_s: float) -> None:
        self.client = ollama.Client(timeout=timeout_s)
        self.last_response = None

    def generate(self, **kwargs):
        self.last_response = self.client.generate(**kwargs)
        return self.last_response


def _duration_s(response, field: str) -> float:
    return float(getattr(response, field, 0) or 0) / 1_000_000_000


def benchmark_model(tag: str, digest: str, timeout_s: float) -> dict[str, object]:
    client = MeasuringClient(timeout_s)
    run = QueuedRun(
        id=f"benchmark-{tag}",
        experiment_id="benchmark-local",
        cell_id="uranium-alpha-beta-v1__balanced__r001",
        protocol_id="uranium-alpha-beta-v1",
        model_id=tag,
        model_digest=digest,
        factors={"alpha_win_prior": 0.5},
        repetition=1,
        seed=2_026_071_8,
        prompt_version=PROMPT_VERSION,
        updated_at=datetime.now(UTC).isoformat(),
    )
    started = time.perf_counter()
    try:
        result = execute_run(client, run)
        response = client.last_response
        eval_s = _duration_s(response, "eval_duration")
        eval_count = int(getattr(response, "eval_count", 0) or 0)
        return {
            "tag": tag,
            "digest": digest,
            "status": "schema_valid",
            "wall_time_s": round(time.perf_counter() - started, 3),
            "load_time_s": round(_duration_s(response, "load_duration"), 3),
            "prompt_tokens": int(getattr(response, "prompt_eval_count", 0) or 0),
            "generated_tokens": eval_count,
            "generation_tokens_per_second": round(eval_count / eval_s, 2) if eval_s else 0.0,
            "nuclear_use": result.nuclear_use,
            "escalation_peak": result.escalation_peak,
        }
    except Exception as exc:  # noqa: BLE001 - le rapport doit couvrir chaque échec de modèle
        response = client.last_response
        eval_s = _duration_s(response, "eval_duration") if response is not None else 0.0
        eval_count = int(getattr(response, "eval_count", 0) or 0) if response is not None else 0
        return {
            "tag": tag,
            "digest": digest,
            "status": "failed",
            "wall_time_s": round(time.perf_counter() - started, 3),
            "generated_tokens": eval_count,
            "generation_tokens_per_second": round(eval_count / eval_s, 2) if eval_s else 0.0,
            "raw_response_prefix": str(getattr(response, "response", "") or "")[:2_000],
            "error": f"{type(exc).__name__}:{str(exc)[:300]}",
        }
    finally:
        _unload(client, tag)


def main() -> None:
    panel = model_panel_view()
    parser = argparse.ArgumentParser()
    parser.add_argument("models", nargs="*", help="Tags; panel principal installé par défaut")
    parser.add_argument("--timeout", type=float, default=300)
    args = parser.parse_args()
    installed = {model.tag: model for model in panel.models if model.installed}
    # Décision design 2026-07-19 (casting = pensée native) : le rôle `core_comparison`
    # a disparu du panel (généralistes -> `retired`, qwen3:4b -> `reasoning`). Le panel
    # principal à benchmarker par défaut suit désormais les candidats « IA frontière »
    # du Laboratoire : raisonnement natif + la voie lente existante (gpt-oss/magistral).
    requested = args.models or [
        model.tag
        for model in panel.models
        if model.installed and model.role in ("reasoning", "slow_robustness_only")
    ]
    unknown = [tag for tag in requested if tag not in installed]
    if unknown:
        raise SystemExit("Modèles absents du panel local : " + ", ".join(unknown))
    results = [
        benchmark_model(tag, installed[tag].local_digest, max(30, min(args.timeout, 1_800)))
        for tag in requested
    ]
    print(
        json.dumps(
            {
                "schema_version": 1,
                "measured_at": datetime.now(UTC).isoformat(),
                "hardware": panel.hardware_profile.model_dump(),
                "prompt_version": PROMPT_VERSION,
                "models": results,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
