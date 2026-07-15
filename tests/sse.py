"""Helpers SSE partagés des tests d'API (POLISH-2).

Chaque suite d'API recopiait le même parseur de flux SSE (`_events`) et le même
« jouer un round » (`_play`) — mutualisés ici, une seule définition. Import :
`from tests.sse import events, play` (la racine du repo est sur sys.path via
`pythonpath = ["."]` de pyproject).
"""

import json


def events(resp) -> list[tuple[str, dict]]:
    """Parse un flux SSE en liste (event, payload)."""
    out: list[tuple[str, dict]] = []
    name = None
    for line in resp.iter_lines():
        if line.startswith("event: "):
            name = line.removeprefix("event: ")
        elif line.startswith("data: "):
            out.append((name, json.loads(line.removeprefix("data: "))))
    return out


def play(client, game_id: str, body=None) -> list[tuple[str, dict]]:
    """Joue un round via l'API et rend les trames SSE (statut + content-type vérifiés)."""
    with client.stream("POST", f"/api/games/{game_id}/rounds", json=body) as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        return events(resp)
