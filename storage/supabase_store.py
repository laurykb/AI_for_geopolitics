"""`SupabaseGameStore` — l'implémentation Supabase du Protocol `GameStore` (Phase R2).

Mêmes tables que `supabase/schema.sql` (games, rounds, transcripts, game_sessions),
parlées via PostgREST (`storage/postgrest.py`). Les payloads JSONB reçoivent les dicts
tels quels ; les colonnes R4 promues de `rounds` (perceptions_json, ladder_json, …)
gardent leurs défauts tant que les artefacts vivent dans `judge_json` (promotion = tâche
séparée). Sélection par variable d'env : voir `app/game_api.get_store`.
"""

from __future__ import annotations

import os

from storage.game_store import (
    CampaignScore,
    GameRecord,
    GameStatus,
    PromptEntry,
    RoundRecord,
    SessionSnapshot,
    TranscriptEntry,
)
from storage.postgrest import PostgrestClient


class SupabaseGameStore:
    """Implémentation Supabase/PostgREST de `GameStore` (schéma `supabase/schema.sql`)."""

    def __init__(self, client: PostgrestClient) -> None:
        self._db = client

    @classmethod
    def from_env(cls) -> SupabaseGameStore:
        """Construit depuis `SUPABASE_URL` + `SUPABASE_SERVICE_KEY` (service_role)."""
        url, key = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_SERVICE_KEY")
        if not url or not key:
            raise RuntimeError(
                "STORE_BACKEND=supabase exige SUPABASE_URL et SUPABASE_SERVICE_KEY"
            )
        return cls(PostgrestClient(url, key))

    def close(self) -> None:
        self._db.close()

    # --- parties --------------------------------------------------------------

    def add_game(self, game: GameRecord) -> None:
        self._db.insert("games", [_game_row(game)])

    def get_game(self, game_id: str) -> GameRecord | None:
        rows = self._db.select("games", {"id": game_id})
        return _game(rows[0]) if rows else None

    def save_game(self, game: GameRecord) -> None:
        row = _game_row(game)
        del row["id"], row["created_at"]  # immuables (created_at = défaut Postgres)
        self._db.update("games", {"id": game.id}, row)

    def list_games(self) -> list[GameRecord]:
        return [_game(r) for r in self._db.select("games", order="created_at.asc")]

    # --- rounds ----------------------------------------------------------------

    def add_round(self, round_: RoundRecord) -> None:
        self._db.insert(
            "rounds",
            [
                {
                    "id": round_.id,
                    "game_id": round_.game_id,
                    "round_no": round_.round_no,
                    "event_json": round_.event,
                    "deltas_json": round_.deltas,
                    "risk_json": round_.risk,
                    "judge_json": round_.judge,
                    "trajectory_json": round_.trajectory,
                }
            ],
        )

    def list_rounds(self, game_id: str) -> list[RoundRecord]:
        rows = self._db.select("rounds", {"game_id": game_id}, order="round_no.asc")
        return [
            RoundRecord(
                id=r["id"],
                game_id=r["game_id"],
                round_no=r["round_no"],
                event=r["event_json"],
                deltas=r["deltas_json"],
                risk=r["risk_json"],
                judge=r["judge_json"],
                trajectory=r["trajectory_json"],
            )
            for r in rows
        ]

    # --- transcripts -------------------------------------------------------------

    def add_transcript(self, entries: list[TranscriptEntry]) -> None:
        self._db.insert("transcripts", [e.model_dump() for e in entries])

    def list_transcript(self, round_id: str) -> list[TranscriptEntry]:
        rows = self._db.select("transcripts", {"round_id": round_id}, order="seq.asc")
        return [TranscriptEntry(**r) for r in rows]

    # --- prompts capturés (G7-c, mode admin) --------------------------------------

    def add_prompts(self, entries: list[PromptEntry]) -> None:
        self._db.insert("prompts", [e.model_dump() for e in entries])

    def list_prompts(self, round_id: str) -> list[PromptEntry]:
        rows = self._db.select("prompts", {"round_id": round_id}, order="seq.asc")
        return [PromptEntry(**r) for r in rows]

    # --- snapshots de session (reconstruction au restart) ------------------------

    def save_session_snapshot(self, snapshot: SessionSnapshot) -> None:
        row = {
            "game_id": snapshot.game_id,
            "world_json": snapshot.world,
            "clock_json": snapshot.clock,
            "recent_json": snapshot.recent,
            "pending_motion_json": snapshot.pending_motion,
            "intel_json": snapshot.intel,
            "grudges_json": snapshot.grudges,
            "deadlines_json": snapshot.deadlines,
            "suspended_json": snapshot.suspended,
            "play_as": snapshot.play_as,
        }
        if snapshot.updated_at:  # sinon : défaut now() de Postgres
            row["updated_at"] = snapshot.updated_at
        self._db.upsert("game_sessions", row)

    def get_session_snapshot(self, game_id: str) -> SessionSnapshot | None:
        rows = self._db.select("game_sessions", {"game_id": game_id})
        if not rows:
            return None
        r = rows[0]
        return SessionSnapshot(
            game_id=r["game_id"],
            world=r["world_json"],
            clock=r["clock_json"],
            recent=r["recent_json"],
            pending_motion=r["pending_motion_json"],
            intel=r.get("intel_json") or {},
            grudges=r.get("grudges_json") or {},
            deadlines=r.get("deadlines_json") or [],
            suspended=r["suspended_json"],
            play_as=r["play_as"],
            updated_at=r["updated_at"] or "",
        )

    def list_session_snapshots(self) -> list[str]:
        rows = self._db.select("game_sessions", columns="game_id")
        return [r["game_id"] for r in rows]

    # --- scores de campagne (G5) --------------------------------------------------

    def add_campaign_score(self, score: CampaignScore) -> None:
        self._db.upsert("campaign_scores", score.model_dump())

    def list_campaign_scores(self) -> list[CampaignScore]:
        rows = self._db.select("campaign_scores", order="created_at.asc")
        return [CampaignScore.model_validate(r) for r in rows]


# --- mapping lignes <-> modèles ---------------------------------------------------


def _game_row(game: GameRecord) -> dict:
    return {
        "id": game.id,
        "scenario": game.scenario,
        "horizon": game.horizon,
        "mode": game.mode,
        "status": game.status.value,
        "created_at": game.created_at,
        "epilogue_json": game.epilogue,
        "published": game.published,
        "admin": game.admin,
    }


def _game(row: dict) -> GameRecord:
    return GameRecord(
        id=row["id"],
        scenario=row["scenario"],
        horizon=row["horizon"],
        mode=row["mode"],
        status=GameStatus(row["status"]),
        created_at=row["created_at"],
        epilogue=row.get("epilogue_json"),
        published=bool(row.get("published", False)),
        admin=bool(row.get("admin", False)),
    )
