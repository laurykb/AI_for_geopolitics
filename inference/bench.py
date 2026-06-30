"""Harnais de mesure P1 : joue le scénario mer Rouge via Ollama et mesure
tok/s, latence/round et VRAM.

Hors pytest (nécessite Ollama lancé + le modèle pull). Usage :
    python -m inference.bench
    python -m inference.bench --model llama3.2:3b
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path
from statistics import mean

from agents.llm_agent import LLMAgent
from core.country_state import CountryState
from core.events import GeoEvent
from core.rounds import RoundEngine
from core.world_state import WorldState
from inference.ollama_backend import DEFAULT_MODEL, OllamaBackend


def _vram_used_mib() -> int | None:
    """VRAM globale utilisée (MiB) via nvidia-smi, ou None si indisponible."""
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return int(out.stdout.strip().splitlines()[0])
    except Exception:
        return None


def _load_world() -> WorldState:
    paths = sorted(Path("data/countries").glob("*.json"))
    return WorldState.from_countries([CountryState.from_json_file(p) for p in paths])


def _load_events(scenario: str) -> list[GeoEvent]:
    data = json.loads(Path(scenario).read_text(encoding="utf-8"))
    return [GeoEvent(**event) for event in data["events"]]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bench LLMAgent via Ollama (tok/s, latence, VRAM)."
    )
    parser.add_argument(
        "--model", default=DEFAULT_MODEL, help=f"modèle Ollama (défaut {DEFAULT_MODEL})"
    )
    parser.add_argument(
        "--host", default=None, help="hôte Ollama (défaut OLLAMA_HOST ou localhost)"
    )
    parser.add_argument("--scenario", default="data/scenarios/red_sea.json")
    args = parser.parse_args()

    world = _load_world()
    backend = OllamaBackend(args.model, host=args.host)
    agents = {cid: LLMAgent(cid, backend) for cid in world.countries}
    engine = RoundEngine(world, agents)
    events = _load_events(args.scenario)

    vram0 = _vram_used_mib()
    print(f"Modèle : {args.model} | Pays : {len(agents)} | VRAM initiale : {vram0} MiB")
    print("=" * 78)

    latencies: list[float] = []
    tok_s_all: list[float] = []
    fallbacks = 0

    for ev in events:
        t0 = time.perf_counter()
        summary = engine.play_round(ev)
        dt = time.perf_counter() - t0
        latencies.append(dt)

        round_tok_s: list[float] = []
        for agent in agents.values():
            if agent.last_used_fallback:
                fallbacks += 1
            elif agent.last_result is not None:
                round_tok_s.append(agent.last_result.tokens_per_second)
        tok_s_all.extend(round_tok_s)

        print(summary.headline)
        for d in summary.decisions:
            tgt = f" -> {d.target}" if d.target else ""
            print(f"   {d.country:14s} {d.action.value:18s}{tgt:12s} i={d.intensity:.2f}")
        avg = mean(round_tok_s) if round_tok_s else 0.0
        print(f"   latence={dt:.1f}s | tok/s moyen={avg:.1f} | VRAM={_vram_used_mib()} MiB")
        print("-" * 78)

    n_calls = len(agents) * len(events)
    print("RÉSUMÉ")
    print(f"  rounds={len(events)} | appels LLM={n_calls} | fallbacks={fallbacks}")
    if latencies:
        lo, hi = min(latencies), max(latencies)
        print(f"  latence/round : moy {mean(latencies):.1f}s (min {lo:.1f} / max {hi:.1f})")
    if tok_s_all:
        lo, hi = min(tok_s_all), max(tok_s_all)
        print(f"  tok/s : moy {mean(tok_s_all):.1f} (min {lo:.1f} / max {hi:.1f})")
    print(f"  VRAM finale : {_vram_used_mib()} MiB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
