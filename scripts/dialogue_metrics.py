"""G9 §3 — l'instrument de mesure du dialogue, OFFLINE (le panneau UI a disparu).

Lit les transcripts persistés d'une partie (`games.db` ou tout store SQLite) et mesure
les trois chiffres de réussite du §1 de la spec — pas d'impression, des nombres :

- **Réponse directe** : part des messages qui reprennent le message précédent d'un autre
  pays (recouvrement lexical `responsiveness` ≥ seuil). Cible : ≥ 70 %.
- **Répétition intra-agent** : part des 4-grammes d'un message déjà émis par le MÊME pays
  plus tôt dans la partie. Cible : < 15 %.
- **Directives visibles** : part des directives (G8) reflétées OU refusées publiquement
  dans le message suivant du pays visé. Cible : 100 %.

Usage :
    python scripts/dialogue_metrics.py [--db games.db] [--game <id>] [--json]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # exécutable depuis scripts/

from simulation.dialogue_integrity.live import RESPONSIVE_THRESHOLD  # noqa: E402
from simulation.dialogue_integrity.metrics import responsiveness  # noqa: E402
from storage.game_store import GameStore, SQLiteGameStore, TranscriptEntry  # noqa: E402

_WORD = re.compile(r"\w+", re.UNICODE)

# Cibles de la spec (§1) — mesurables, pas des impressions.
TARGET_RESPONSIVE = 0.70
TARGET_REPETITION = 0.15
TARGET_DIRECTIVES = 1.0


def _tokens(text: str) -> list[str]:
    return _WORD.findall((text or "").lower())


def _ngrams(tokens: list[str], n: int = 4) -> set[tuple[str, ...]]:
    return {tuple(tokens[i : i + n]) for i in range(len(tokens) - n + 1)}


@dataclass
class GameMetrics:
    """Les trois mesures du §1 pour une partie, plus le détail par pays."""

    game_id: str
    messages: int = 0
    responsive_rate: float = 0.0  # part des réponses qui reprennent le message précédent
    repetition_rate: float = 0.0  # part de 4-grammes déjà émis par le même pays
    directives_total: int = 0
    directives_visible: int = 0
    by_country_repetition: dict[str, float] = field(default_factory=dict)

    @property
    def directives_rate(self) -> float:
        return self.directives_visible / self.directives_total if self.directives_total else 1.0

    def passes(self) -> bool:
        return (
            self.responsive_rate >= TARGET_RESPONSIVE
            and self.repetition_rate < TARGET_REPETITION
            and self.directives_rate >= TARGET_DIRECTIVES
        )


def _speeches(entries: list[TranscriptEntry]) -> list[TranscriptEntry]:
    """Les prises de parole des pays (le GM et le juge ne sont pas des dialoguistes)."""
    return [e for e in entries if e.speaker not in ("gm", "judge", "human")]


def measure_responsiveness(rounds: list[list[TranscriptEntry]]) -> tuple[float, int]:
    """(taux de réponse directe, nb de réponses évaluées) — au sein de chaque round."""
    scored: list[bool] = []
    for entries in rounds:
        speeches = _speeches(entries)
        for i, entry in enumerate(speeches):
            previous = next(
                (speeches[j] for j in range(i - 1, -1, -1) if speeches[j].speaker != entry.speaker),
                None,
            )
            if previous is None:
                continue  # ouverture du round : rien à reprendre
            scored.append(
                responsiveness(entry.content, previous.content) >= RESPONSIVE_THRESHOLD
            )
    rate = sum(scored) / len(scored) if scored else 0.0
    return rate, len(scored)


def measure_repetition(rounds: list[list[TranscriptEntry]]) -> tuple[float, dict[str, float]]:
    """Répétition intra-agent : 4-grammes d'un message déjà émis par le même pays."""
    seen: dict[str, set[tuple[str, ...]]] = {}
    repeated, total = 0, 0
    per_country: dict[str, list[tuple[int, int]]] = {}
    for entries in rounds:
        for entry in _speeches(entries):
            grams = _ngrams(_tokens(entry.content))
            if not grams:
                continue
            before = seen.setdefault(entry.speaker, set())
            overlap = len(grams & before)
            repeated += overlap
            total += len(grams)
            per_country.setdefault(entry.speaker, []).append((overlap, len(grams)))
            before |= grams
    by_country = {
        cid: (sum(o for o, _ in pairs) / sum(t for _, t in pairs)) if pairs else 0.0
        for cid, pairs in per_country.items()
    }
    return (repeated / total if total else 0.0), by_country


def measure_directives(
    store: GameStore, game_id: str, rounds_entries: dict[str, list[TranscriptEntry]]
) -> tuple[int, int]:
    """(directives émises, directives visibles) — visible = le message suivant du pays
    visé reprend la directive (recouvrement > 0) OU le refus public a été détecté."""
    total, visible = 0, 0
    for record in store.list_rounds(game_id):
        directives: dict = record.judge.get("directives") or {}
        refused: list = record.judge.get("directives_refused") or []
        entries = rounds_entries.get(record.id, [])
        for cid, text in directives.items():
            total += 1
            first = next((e for e in _speeches(entries) if e.speaker == cid), None)
            if cid in refused or (first is not None and responsiveness(first.content, text) > 0):
                visible += 1
    return total, visible


def measure_game(store: GameStore, game_id: str) -> GameMetrics:
    """Toutes les mesures du §1 pour une partie persistée."""
    records = store.list_rounds(game_id)
    rounds_entries = {r.id: store.list_transcript(r.id) for r in records}
    ordered = [rounds_entries[r.id] for r in records]

    metrics = GameMetrics(game_id=game_id)
    metrics.messages = sum(len(_speeches(entries)) for entries in ordered)
    metrics.responsive_rate, _ = measure_responsiveness(ordered)
    metrics.repetition_rate, metrics.by_country_repetition = measure_repetition(ordered)
    metrics.directives_total, metrics.directives_visible = measure_directives(
        store, game_id, rounds_entries
    )
    return metrics


def _print_report(metrics: GameMetrics) -> None:
    status = "OK" if metrics.passes() else "HORS CIBLE"
    print(f"\n=== Partie {metrics.game_id} — {metrics.messages} prises de parole [{status}]")
    print(
        f"  réponse directe   : {metrics.responsive_rate:6.1%}  (cible ≥ {TARGET_RESPONSIVE:.0%})"
    )
    print(
        f"  répétition 4-gram : {metrics.repetition_rate:6.1%}  (cible < {TARGET_REPETITION:.0%})"
    )
    print(
        f"  directives vues   : {metrics.directives_visible}/{metrics.directives_total}"
        f"  (cible 100 %)"
    )
    for cid, rate in sorted(metrics.by_country_repetition.items()):
        print(f"    - répétition {cid} : {rate:.1%}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", default="games.db", help="chemin du store SQLite des parties")
    parser.add_argument("--game", default=None, help="id d'une partie (défaut : toutes)")
    parser.add_argument("--json", action="store_true", help="sortie JSON (pour l'équilibrage)")
    args = parser.parse_args(argv)

    store = SQLiteGameStore(args.db)
    games = [g.id for g in store.list_games() if args.game is None or g.id == args.game]
    if not games:
        print(f"aucune partie trouvée dans {args.db}", file=sys.stderr)
        return 1
    results = [measure_game(store, gid) for gid in games]
    if args.json:
        print(json.dumps([asdict(m) for m in results], ensure_ascii=False, indent=2))
    else:
        for metrics in results:
            _print_report(metrics)
    return 0 if all(m.passes() for m in results) else 2


if __name__ == "__main__":
    raise SystemExit(main())
