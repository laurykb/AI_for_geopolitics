"""Fixtures partagées — mini-PostgREST en mémoire pour tester les stores Supabase offline.

`fake_postgrest` rejoue la sémantique PostgREST utilisée par `storage/postgrest.py`
(insert, upsert merge-duplicates, update/patch filtré, select eq+order) sur des tables
dict en mémoire, via `httpx.MockTransport` : aucun réseau, aucun Supabase requis.
"""

from __future__ import annotations

import json
from urllib.parse import parse_qsl, urlparse

import httpx
import pytest

from storage.postgrest import PostgrestClient

# Clés primaires des tables du schéma (upsert merge-duplicates + update par filtre).
_PRIMARY_KEYS = {
    "games": ("id",),
    "players": ("id",),
    "lp_history": ("id",),
    "xp_history": ("id",),
    "custom_crises": ("id",),
    "rounds": ("id",),
    "transcripts": ("id",),
    "game_sessions": ("game_id",),
    "campaign_scores": ("game_id",),
    "market_accounts": ("id",),
    "markets": ("id",),
    "market_outcomes": ("id",),
    "market_positions": ("account_id", "outcome_id"),
    "market_trades": ("id",),
    "prompts": ("id",),
}


class FakePostgrest:
    """Tables en mémoire + journal des requêtes (inspectable dans les tests)."""

    def __init__(self) -> None:
        self.tables: dict[str, list[dict]] = {}
        self.requests: list[httpx.Request] = []

    def client(self, url: str = "https://fake.supabase.co", key: str = "svc") -> PostgrestClient:
        return PostgrestClient(url, key, transport=httpx.MockTransport(self._handle))

    # --- sémantique PostgREST minimale ------------------------------------------

    def _handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        table = urlparse(str(request.url)).path.removeprefix("/rest/v1/")
        params = dict(parse_qsl(urlparse(str(request.url)).query))
        rows = self.tables.setdefault(table, [])

        if request.method == "POST":
            payload = json.loads(request.content)
            merge = "merge-duplicates" in request.headers.get("Prefer", "")
            for new in payload:
                if merge:
                    key = _PRIMARY_KEYS[table]
                    rows[:] = [r for r in rows if not all(r[k] == new[k] for k in key)]
                rows.append(new)
            return httpx.Response(201)

        if request.method == "PATCH":
            values = json.loads(request.content)
            for row in rows:
                if _matches(row, params):
                    row.update(values)
            return httpx.Response(204)

        if request.method == "DELETE":
            rows[:] = [r for r in rows if not _matches(r, params)]
            return httpx.Response(204)

        if request.method == "GET":
            found = [r for r in rows if _matches(r, params)]
            if order := params.get("order"):
                col, _, direction = order.partition(".")
                # NULL-safe comme Postgres (NULLs en fin en asc) : jamais None < None.
                found.sort(
                    key=lambda r: (True,) if r.get(col) is None else (False, r[col]),
                    reverse=direction == "desc",
                )
            columns = params.get("select", "*")
            if columns != "*":
                wanted = columns.split(",")
                found = [{k: r[k] for k in wanted} for r in found]
            return httpx.Response(200, json=found)

        return httpx.Response(405)


def _matches(row: dict, params: dict[str, str]) -> bool:
    for col, expr in params.items():
        if col in ("select", "order"):
            continue
        assert expr.startswith("eq."), f"opérateur non simulé : {expr}"
        if str(row.get(col)) != expr.removeprefix("eq."):
            return False
    return True


@pytest.fixture
def fake_postgrest() -> FakePostgrest:
    return FakePostgrest()
