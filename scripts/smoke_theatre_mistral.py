"""Smoke théâtre réel — partie Dérive complète (mistral/Ollama) traversant le lot G18-G23.

Écrit par POLISH-1, rejoué à l'identique par POLISH-2/3 (versionné en POLISH-3 —
reco D5.1 de docs/DETTE_TECHNIQUE.md : le script vivait dans un scratchpad de
session). C'est le smoke de référence du théâtre : les 4 bugs de POLISH-1 (dont
le verdict tronqué à 400 tokens) n'étaient visibles QU'ICI, pas en CI offline.

Une partie Dérive (horizon 2, 3 pays) :
- round 1 : événement DÉCRÉTÉ + ULTIMATUM (G21, échéance séance tenante) —
  cycle armed -> satisfied|expired sur le VRAI juge, tag sous_ultimatum,
  barème Kahn (G18) + signaux (G20) + promesses (G22) extraits de la vraie parole ;
- round 2 : sans corps — conséquence d'ultimatum OU événement GM (rubrique
  Storyteller G19 en Dérive), journal de tension chaque round ;
- fin de partie : reveal Dérive (gm_tension, signal_gap, promise_kept),
  result_json["ultimatum"] (différentiel avec/sans), registre promesses réglé.

Mécanisme = ASSERTIONS DURES ; extractions LLM (actions/signals/promises) =
OBSERVATIONS rapportées (la variance d'un 7B n'est pas un bug du moteur).
TestClient in-process, store :memory:, aucun port ouvert.
Prérequis : Ollama sur 127.0.0.1:11434 avec le modèle `mistral`.

Usage : python scripts/smoke_theatre_mistral.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

# Décision design 2026-07-19 (casting = pensée native) : sans `model_cast` explicite, une
# partie classique/campagne caste désormais ses pays par défaut sur deepseek-r1:7b (voir
# `app/game_api.py::_default_reasoning_cast`) — ce smoke teste le MOTEUR (ultimatum, Kahn,
# signaux, promesses, Storyteller), pas la politique de casting, et doit rester rapide sur
# mistral pour tous les rôles. Échappatoire réservée aux tests/smoke (lue à chaque requête
# de création de partie, donc valable même posée ici en tête de script).
os.environ["GAME_ALLOW_GENERALIST_CAST"] = "1"

# Le dépôt du script d'abord (avant un éventuel install editable du venv partagé) :
# le smoke doit tester CE worktree/clone, pas un autre.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app import game_api  # noqa: E402
from app.game_api import get_backend, get_store  # noqa: E402
from app.main import app  # noqa: E402
from inference.ollama_backend import OllamaBackend  # noqa: E402
from storage.game_store import SQLiteGameStore  # noqa: E402

COUNTRIES = ["usa", "iran", "france"]


def _play(client: TestClient, game_id: str, body: dict | None) -> list[tuple[str, dict]]:
    payload = {"max_turns": 2, **(body or {})}
    frames: list[tuple[str, dict]] = []
    with client.stream("POST", f"/api/games/{game_id}/rounds", json=payload) as resp:
        assert resp.status_code == 200, resp.read()
        name = None
        for line in resp.iter_lines():
            if line.startswith("event: "):
                name = line.removeprefix("event: ")
            elif line.startswith("data: "):
                frames.append((name, json.loads(line.removeprefix("data: "))))
    return frames


def main() -> int:
    store = SQLiteGameStore(":memory:")
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_backend] = lambda: OllamaBackend()
    game_api._sessions.clear()
    client = TestClient(app)
    failures: list[str] = []
    t0 = time.time()

    game = client.post(
        # Post-pivot RG : la Dérive est le cœur des DEUX modes ; "drift" n'est plus un
        # mode d'API (Literal classic|campaign) — le smoke joue une partie Classique.
        "/api/games", json={"countries": COUNTRIES, "mode": "classic", "horizon": 2}
    ).json()
    gid = game["id"]
    print(f"partie Derive {gid} (horizon 2, {len(COUNTRIES)} pays)")

    # --- round 1 : décret + ultimatum (échéance CE round) --------------------------------
    frames = _play(
        client,
        gid,
        {
            "event": {
                "title": "Incident naval dans le detroit d'Ormuz",
                "description": "Un petrolier est arraisonne ; le sommet exige des reponses.",
                "severity": 0.6,
                "ultimatum": {
                    "demand": "un engagement ecrit de libre passage sous 24 heures",
                    "classe": "posture",
                },
            }
        },
    )
    ult = [p for n, p in frames if n == "ultimatum"]
    statuses = [p["status"] for p in ult]
    print(f"  round 1 : ultimatum statuses={statuses}")
    if not statuses or statuses[0] != "armed" or statuses[-1] not in ("satisfied", "expired"):
        failures.append(f"cycle ultimatum inattendu au round 1 : {statuses}")
    verdict = next((p for n, p in frames if n == "verdict"), None)
    if verdict is None:
        failures.append("aucune trame verdict au round 1")
    else:
        if verdict.get("demand_satisfied") is None:
            failures.append("demand_satisfied absent du verdict a l'echeance")
        print(
            "  round 1 : demand_satisfied="
            + str(verdict.get("demand_satisfied"))
            + f" actions={len(verdict.get('actions') or [])}"
            + f" signals={len(verdict.get('signals') or [])}"
            + f" promises={len(verdict.get('promises') or [])}"
            + f" score={verdict.get('score')}"
        )
        for key in ("actions", "signals", "divergences", "promises", "promise_registry"):
            if key not in verdict:
                failures.append(f"champ '{key}' absent de la trame verdict")
    r1 = store.list_rounds(gid)[-1].judge
    if r1.get("sous_ultimatum") is not True:
        failures.append("round 1 non tague sous_ultimatum")
    gm1 = (r1.get("drift") or {}).get("gm")
    if gm1 is None:
        failures.append("journal storyteller absent au round 1")
    else:
        print(f"  round 1 : gm tension={gm1.get('tension')}")
    if verdict is not None and (verdict.get("actions") or []):
        if "kahn" not in r1:
            failures.append("actions classees mais judge_json['kahn'] absent")
        else:
            print(f"  round 1 : kahn persiste (score={r1['kahn']['score']})")
    if verdict is not None and (verdict.get("signals") or []):
        if "signal" not in r1:
            failures.append("signals presents mais judge_json['signal'] absent")
        else:
            print(f"  round 1 : signal persiste (means={r1['signal']['means']})")

    # --- round 2 : sans corps — conséquence OU événement GM (Storyteller) ----------------
    frames = _play(client, gid, None)
    event = next(p for n, p in frames if n == "event")["event"]
    print(f"  round 2 : event_type={event['event_type']} — {event['title'][:60]}")
    expired = statuses and statuses[-1] == "expired"
    if expired and event["event_type"] != "ultimatum":
        failures.append("ultimatum expire mais la consequence n'est pas l'evenement du round 2")
    if expired:
        struck = [p for n, p in frames if n == "ultimatum"]
        if not struck or struck[0]["status"] != "struck":
            failures.append("statut struck absent au round de consequence")
    r2 = store.list_rounds(gid)[-1].judge
    gm2 = (r2.get("drift") or {}).get("gm")
    if gm2 is None:
        failures.append("journal storyteller absent au round 2")
    else:
        print(f"  round 2 : gm tension={gm2.get('tension')}")
    if not any(n == "game_over" for n, _ in frames):
        failures.append("game_over absent a l'horizon 2")

    # --- fin : reveal + result_json -------------------------------------------------------
    detail = client.get(f"/api/games/{gid}").json()
    if detail["status"] != "finished":
        failures.append(f"partie non finie (status={detail['status']})")
    result = detail.get("result") or {}
    if "ultimatum" not in result:
        failures.append("result_json sans section ultimatum (differentiel)")
    else:
        print(f"  fin : differentiel ultimatum={json.dumps(result['ultimatum'])}")
    reveal = client.get(f"/api/games/{gid}/drift/reveal").json()
    if len(reveal.get("gm_tension", [])) != 2:
        failures.append(f"gm_tension incomplet au reveal : {reveal.get('gm_tension')}")
    print(
        "  fin : reveal deviant="
        + reveal.get("deviant", "?")
        + f" gm_tension={reveal.get('gm_tension')}"
        + f" signal_gap_deviant={reveal.get('signal_gap_deviant')}"
        + f" promise_kept_deviant={reveal.get('promise_kept_deviant')}"
    )
    snapshot = store.get_session_snapshot(gid)
    if snapshot is not None:
        pending = [
            p for p in snapshot.world.get("promises", []) if p.get("status") == "en_cours"
        ]
        if pending:
            failures.append("promesses encore en_cours apres la fin de partie")
        print(f"  fin : registre promesses={len(snapshot.world.get('promises', []))} (0 en cours)")

    app.dependency_overrides.clear()
    game_api._sessions.clear()
    print(f"duree totale : {time.time() - t0:.0f}s")
    if failures:
        print("SMOKE FAIL :")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("SMOKE OK — ultimatum + bareme + signaux + promesses + storyteller sur mistral reel.")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    raise SystemExit(main())
