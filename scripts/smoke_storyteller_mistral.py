"""Smoke réel G19 — le GM-Storyteller sur mistral (Ollama local), in-process.

Vérifie sur le VRAI modèle (aucun mock) que :
1. en mode Dérive, la tension est journalisée chaque round et une intervention
   du Storyteller se produit et se journalise (horizon 2, conseil inactif →
   tension basse → indice attendu au round 2, « après la moitié de l'horizon ») ;
2. la révélation de fin expose `gm_tension` + `gm_interventions` ;
3. une partie classique ne porte AUCUNE trace du Storyteller (pas de clé drift).

TestClient in-process : aucun serveur, aucun port ouvert ; store `:memory:`.
Prérequis : Ollama sur 127.0.0.1:11434 avec le modèle `mistral` (les requêtes
sont mises en file par Ollama — le script patiente, il ne relance pas).

Usage : python scripts/smoke_storyteller_mistral.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Le dépôt du script d'abord (avant un éventuel install editable du venv partagé) :
# le smoke doit tester CE worktree, pas le clone principal.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app import game_api  # noqa: E402
from app.game_api import get_backend, get_store  # noqa: E402
from app.main import app  # noqa: E402
from inference.ollama_backend import OllamaBackend  # noqa: E402
from storage.game_store import SQLiteGameStore  # noqa: E402

COUNTRIES = ["usa", "iran", "france"]


def _play(client: TestClient, game_id: str) -> None:
    """Joue un round complet en consommant le flux SSE (budget de parole serré)."""
    with client.stream(
        "POST", f"/api/games/{game_id}/rounds", json={"max_turns": 2}
    ) as resp:
        assert resp.status_code == 200, resp.read()
        for _ in resp.iter_lines():
            pass


def main() -> int:
    store = SQLiteGameStore(":memory:")
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_backend] = lambda: OllamaBackend()
    game_api._sessions.clear()
    client = TestClient(app)
    failures: list[str] = []

    print("[1/2] Partie Derive (horizon 2, conseil inactif -> indice au round 2)")
    game = client.post(
        "/api/games",
        json={"countries": COUNTRIES, "mode": "drift", "horizon": 2},
    ).json()
    for round_no in (1, 2):
        _play(client, game["id"])
        journal = store.list_rounds(game["id"])[-1].judge.get("drift", {}).get("gm")
        if journal is None:
            failures.append(f"round {round_no} : journal storyteller absent")
            continue
        kind = (journal.get("intervention") or {}).get("kind", "-")
        print(f"  round {round_no} : tension={journal['tension']} intervention={kind}")
    interventions = [
        (r.judge.get("drift", {}).get("gm", {}).get("intervention") or {})
        for r in store.list_rounds(game["id"])
    ]
    if not any(iv.get("kind") == "hint" for iv in interventions):
        failures.append("aucune intervention 'hint' journalisée en Dérive")

    status = client.get(f"/api/games/{game['id']}").json()["status"]
    if status != "finished":
        failures.append(f"partie Dérive non finie à l'horizon (status={status})")
    else:
        reveal = client.get(f"/api/games/{game['id']}/drift/reveal").json()
        print(
            "  reveal : gm_tension="
            + json.dumps(reveal.get("gm_tension"))
            + " interventions="
            + json.dumps(
                [
                    {k: iv[k] for k in ("round_no", "kind", "target")}
                    for iv in reveal.get("gm_interventions", [])
                ]
            )
        )
        if len(reveal.get("gm_tension", [])) != 2:
            failures.append("la révélation ne porte pas la tension des 2 rounds")
        if not reveal.get("gm_interventions"):
            failures.append("la révélation ne raconte aucune intervention")

    print("[2/2] Partie classique (aucune trace du Storyteller attendue)")
    classic = client.post("/api/games", json={"countries": COUNTRIES, "horizon": 4}).json()
    _play(client, classic["id"])
    classic_rounds = store.list_rounds(classic["id"])
    if any("drift" in r.judge for r in classic_rounds):
        failures.append("une partie classique porte une clé drift/storyteller")
    else:
        print("  round 1 classique : pas de cle drift dans le judge — OK")

    app.dependency_overrides.clear()
    game_api._sessions.clear()
    if failures:
        print("SMOKE FAIL :")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("SMOKE OK — Storyteller journalise en Dérive, silence total en classique.")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    raise SystemExit(main())
