"""Client PostgREST minimal (Supabase) — httpx, zéro dépendance nouvelle.

Supabase expose Postgres via PostgREST (`{SUPABASE_URL}/rest/v1/{table}`). Les stores
Supabase (jeu et marché) n'ont besoin que de quatre verbes : insert, upsert, update,
select. La clé **service_role** est utilisée côté backend : elle contourne la RLS par
design (cf. `supabase/schema.sql` — écriture réservée au backend).

Le transport httpx est injectable (`httpx.MockTransport` en test → aucun réseau).
"""

from __future__ import annotations

import httpx

_TIMEOUT = 15.0  # secondes — requêtes unitaires courtes, on échoue vite et fort


class PostgrestError(RuntimeError):
    """Réponse non-2xx de PostgREST (le corps de l'erreur est inclus)."""


class PostgrestClient:
    """Accès table par table à PostgREST, avec la clé service_role."""

    def __init__(
        self, url: str, key: str, *, transport: httpx.BaseTransport | None = None
    ) -> None:
        self._http = httpx.Client(
            base_url=url.rstrip("/") + "/rest/v1",
            headers={
                "apikey": key,
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            timeout=_TIMEOUT,
            transport=transport,
        )

    def close(self) -> None:
        self._http.close()

    # --- verbes ---------------------------------------------------------------

    def insert(self, table: str, rows: list[dict]) -> None:
        if not rows:
            return
        self._check(
            self._http.post(f"/{table}", json=rows, headers={"Prefer": "return=minimal"})
        )

    def upsert(self, table: str, row: dict) -> None:
        """Insert-ou-remplace sur la clé primaire (merge-duplicates)."""
        self._check(
            self._http.post(
                f"/{table}",
                json=[row],
                headers={"Prefer": "resolution=merge-duplicates,return=minimal"},
            )
        )

    def update(self, table: str, match: dict[str, object], values: dict) -> None:
        self._check(
            self._http.patch(
                f"/{table}",
                params=_filters(match),
                json=values,
                headers={"Prefer": "return=minimal"},
            )
        )

    def delete(self, table: str, match: dict[str, object]) -> None:
        self._check(self._http.request("DELETE", f"/{table}", params=_filters(match)))

    def select(
        self,
        table: str,
        match: dict[str, object] | None = None,
        *,
        columns: str = "*",
        order: str | None = None,
    ) -> list[dict]:
        params: dict[str, str] = {"select": columns, **_filters(match or {})}
        if order:
            params["order"] = order
        resp = self._http.get(f"/{table}", params=params)
        self._check(resp)
        return resp.json()

    @staticmethod
    def _check(resp: httpx.Response) -> None:
        if resp.status_code >= 400:
            raise PostgrestError(
                f"PostgREST {resp.request.method} {resp.request.url.path} "
                f"-> {resp.status_code} : {resp.text}"
            )


def _filters(match: dict[str, object]) -> dict[str, str]:
    """`{"id": "g1"}` → `{"id": "eq.g1"}` (syntaxe d'opérateur PostgREST)."""
    return {col: f"eq.{value}" for col, value in match.items()}
