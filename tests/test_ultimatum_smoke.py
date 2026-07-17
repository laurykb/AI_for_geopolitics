"""Smoke réel G21 (Ollama/mistral) : l'ultimatum jugé en vrai + conséquence au round k+1.

Hors CI (dépend d'un modèle servi et du GPU) — lancer avec Ollama up (127.0.0.1:11434) :

    OLLAMA_SMOKE=1 pytest tests/test_ultimatum_smoke.py -q

TestClient in-process (aucun serveur sur un port). Les requêtes Ollama sont mises en
file : si une autre génération tourne, le test attend — ne pas relancer en boucle.
Le constat du juge n'est pas scripté : le test valide le MÉCANISME quel que soit le
verdict (satisfaite → la fiche reprend ; non satisfaite → la conséquence tombe).
"""

import os

import pytest
from fastapi.testclient import TestClient

from app import game_api
from app.game_api import get_backend, get_store
from app.main import app
from storage.game_store import SQLiteGameStore
from tests.sse import events as _events

SMOKE_CRISIS = {
    "id": "smoke-ultimatum",
    "title": "Blocus sous ultimatum (smoke G21)",
    "description": "Fiche jetable du smoke réel : échéance au round 1.",
    "events": [
        {
            "id": "e1",
            "round_id": 1,
            "event_type": "crisis",
            "title": "Blocus naval et ultimatum",
            "description": (
                "Un blocus naval est en place. Un ultimatum exige le retrait immédiat "
                "et vérifiable des missiles stationnés à l'étranger."
            ),
            "actors": ["usa", "iran"],
            "severity": 0.8,
        },
        {
            "id": "e2",
            "round_id": 2,
            "event_type": "crisis",
            "title": "Lendemain d'ultimatum",
            "actors": ["usa", "iran"],
        },
    ],
    "deadline": {
        "round": 1,
        "demand": "retrait immédiat et vérifiable des missiles stationnés à l'étranger",
        "consequence": {"classe": "violente", "cible": "iran"},
    },
}


@pytest.mark.skipif(
    os.getenv("OLLAMA_SMOKE") != "1",
    reason="smoke live Ollama : hors CI. Lancer avec OLLAMA_SMOKE=1 et Ollama up.",
)
def test_smoke_ultimatum_live_ollama():  # pragma: no cover — dépend d'un modèle servi
    from inference.ollama_backend import OllamaBackend

    store = SQLiteGameStore(":memory:")
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_backend] = lambda: OllamaBackend()
    game_api._sessions.clear()
    client = TestClient(app)
    try:
        resp = client.post(
            "/api/admin/crises", json={"owner_id": "smoke", "crisis": SMOKE_CRISIS}
        )
        assert resp.status_code == 201
        game = client.post(
            "/api/games",
            json={"countries": ["usa", "iran"], "horizon": 2},
        )
        assert game.status_code == 201
        game_id = game.json()["id"]

        # Round 1 = l'échéance : le juge (mistral) constate « demande satisfaite o/n ».
        with client.stream(
            "POST",
            f"/api/games/{game_id}/rounds",
            json={"crisis_id": "smoke-ultimatum", "max_turns": 1},
        ) as r:
            assert r.status_code == 200
            events = _events(r)
        statuses = [p["status"] for n, p in events if n == "ultimatum"]
        assert statuses[0] == "armed" and statuses[-1] in ("satisfied", "expired")
        verdict = next(p for n, p in events if n == "verdict")
        assert isinstance(verdict["demand_satisfied"], bool)
        print(  # diagnostic du smoke (visible avec -s) : quelle branche a été jouée
            f"[smoke G21] constat mistral : demand_satisfied={verdict['demand_satisfied']} "
            f"→ statut {statuses[-1]}"
        )

        # Round 2 : conséquence auto si non satisfaite, la fiche reprend sinon.
        with client.stream(
            "POST",
            f"/api/games/{game_id}/rounds",
            json={"crisis_id": "smoke-ultimatum", "max_turns": 1},
        ) as r:
            assert r.status_code == 200
            events2 = _events(r)
        event2 = next(p for n, p in events2 if n == "event")["event"]
        if statuses[-1] == "expired":
            assert event2["event_type"] == "ultimatum"
            assert "retrait immédiat" in event2["description"]
            assert [p["status"] for n, p in events2 if n == "ultimatum"] == ["struck"]
        else:
            assert event2["event_type"] == "crisis"
            assert not [p for n, p in events2 if n == "ultimatum"]

        # Fin de partie (horizon 2) : la section différentielle du bilan est là.
        over = next(p for n, p in events2 if n == "game_over")
        assert over["ultimatum"] is not None
        assert over["ultimatum"]["avec"]["rounds"] == 1
    finally:
        app.dependency_overrides.clear()
        game_api._sessions.clear()
        store.close()
