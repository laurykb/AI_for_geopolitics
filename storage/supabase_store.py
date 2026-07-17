"""`SupabaseGameStore` — l'implémentation Supabase du Protocol `GameStore` (Phase R2).

Mêmes tables que `supabase/schema.sql` (games, rounds, transcripts, game_sessions),
parlées via PostgREST (`storage/postgrest.py`). Les payloads JSONB reçoivent les dicts
tels quels ; les colonnes R4 promues de `rounds` (perceptions_json, ladder_json, …)
gardent leurs défauts tant que les artefacts vivent dans `judge_json` (promotion = tâche
séparée). Sélection par variable d'env : voir `app/game_api.get_store`.
"""

from __future__ import annotations

import os

from simulation.game_mode import normalize_stored
from storage.game_store import (
    CampaignScore,
    CustomCrisisRecord,
    DailyScore,
    GameRecord,
    GameStatus,
    PlayerRecord,
    PromptEntry,
    RoundRecord,
    SessionSnapshot,
    TranscriptEntry,
    XpHistoryEntry,
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
        # Tie-break déterministe (id) : deux parties créées à la même microseconde
        # gardent un ordre stable, comme le rowid côté SQLite.
        return [_game(r) for r in self._db.select("games", order="created_at.asc,id.asc")]

    def set_game_owner(self, game_id: str, owner_id: str | None) -> None:
        """G14 §3 — anonymise (None) ou réattribue une partie sans toucher au reste."""
        self._db.update("games", {"id": game_id}, {"owner_id": owner_id})

    def delete_game(self, game_id: str) -> None:
        """G14 §3 — purge complète d'une partie (rounds, transcripts, prompts, snapshot)."""
        rounds = self._db.select("rounds", {"game_id": game_id}, columns="id")
        for r in rounds:
            self._db.delete("transcripts", {"round_id": r["id"]})
            self._db.delete("prompts", {"round_id": r["id"]})
        self._db.delete("rounds", {"game_id": game_id})
        self._db.delete("game_sessions", {"game_id": game_id})
        self._db.delete("campaign_scores", {"game_id": game_id})
        self._db.delete("games", {"id": game_id})

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
            "directives_json": snapshot.directives,
            "history_json": snapshot.history,
            "storyline": snapshot.storyline,
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
            directives=r.get("directives_json") or {},
            history=r.get("history_json") or {},
            storyline=r.get("storyline") or "",
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

    # --- défi du jour (G16) ---------------------------------------------------------

    def add_daily_score(self, score: DailyScore) -> None:
        # Jamais réécrit (la 1re tentative fait foi) : insert ignoré si la PK existe.
        if any(
            r["player_id"] == score.player_id
            for r in self._db.select("daily_scores", {"date": score.date})
        ):
            return
        self._db.insert("daily_scores", [score.model_dump()])

    def list_daily_scores(self) -> list[DailyScore]:
        rows = self._db.select("daily_scores", order="created_at.asc")
        return [DailyScore.model_validate(r) for r in rows]

    # --- comptes joueurs (G11-c) --------------------------------------------------

    def get_player(self, player_id: str) -> PlayerRecord | None:
        rows = self._db.select("players", {"id": player_id})
        return _player(rows[0]) if rows else None

    def upsert_player(self, player: PlayerRecord) -> None:
        # N'écrit QUE id + pseudo : is_admin/xp gardent leurs valeurs en base (posés par
        # le service_role / la fin de partie), jamais écrasés par une reconnexion.
        self._db.upsert("players", {"id": player.id, "pseudo": player.pseudo})

    def delete_player(self, player_id: str) -> None:
        """G14 §3 — efface la fiche joueur et son historique d'XP. Purge aussi les lignes
        lp_history dormantes (RG-1). NB : l'utilisateur auth.users de Supabase n'est PAS
        supprimé ici (API admin GoTrue, hors du périmètre PostgREST) — une reconnexion
        recréerait une fiche vierge."""
        self._db.delete("lp_history", {"player_id": player_id})
        self._db.delete("xp_history", {"player_id": player_id})
        self._db.delete("players", {"id": player_id})

    def set_player_xp(self, player_id: str, xp: int) -> None:
        self._db.update("players", {"id": player_id}, {"xp": xp})

    def add_market_balance(self, player_id: str, delta: float) -> None:
        # PostgREST n'incrémente pas en place : lecture-modification-écriture (service_role).
        player = self.get_player(player_id)
        if player is None:
            return
        self._db.update(
            "players", {"id": player_id}, {"market_balance": player.market_balance + delta}
        )

    def add_xp_history(self, entry: XpHistoryEntry) -> None:
        self._db.insert("xp_history", [entry.model_dump()])

    def list_xp_history(self, player_id: str) -> list[XpHistoryEntry]:
        rows = self._db.select("xp_history", {"player_id": player_id}, order="ts.asc")
        return [XpHistoryEntry.model_validate(r) for r in rows]

    # --- crises maison (G12-b §5) -------------------------------------------------

    def upsert_custom_crisis(self, crisis: CustomCrisisRecord) -> None:
        self._db.upsert(
            "custom_crises",
            {
                "id": crisis.id,
                "owner_id": crisis.owner_id,
                "crisis_json": crisis.crisis,
                "created_at": crisis.created_at or None,
            },
        )

    def list_custom_crises(self) -> list[CustomCrisisRecord]:
        rows = self._db.select("custom_crises", order="created_at.asc")
        return [
            CustomCrisisRecord(
                id=r["id"],
                owner_id=r["owner_id"],
                crisis=r["crisis_json"],
                created_at=str(r.get("created_at") or ""),
            )
            for r in rows
        ]

    def delete_custom_crisis(self, crisis_id: str, owner_id: str) -> bool:
        rows = self._db.select("custom_crises", {"id": crisis_id})
        if not any(r.get("owner_id") == owner_id for r in rows):
            return False
        self._db.delete("custom_crises", {"id": crisis_id, "owner_id": owner_id})
        return True

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
        "role": game.role,
        "owner_id": game.owner_id,
        "ranked": game.ranked,
        "difficulty": game.difficulty,
        "drift_enabled": game.drift_enabled,
        "result_json": game.result,
        "language": game.language,
        "fog": game.fog,
        "escalation": game.escalation,
    }


def _game(row: dict) -> GameRecord:
    # RG-2 — même lecture tolérante que le store SQLite (anciens libellés de mode mappés).
    flags = normalize_stored(
        row["mode"],
        fog=bool(row.get("fog", False)),
        escalation=bool(row.get("escalation", False)),
        drift_enabled=bool(row.get("drift_enabled", True)),
        scenario=row["scenario"],
    )
    return GameRecord(
        id=row["id"],
        scenario=row["scenario"],
        horizon=row["horizon"],
        mode=flags.mode,
        fog=flags.fog,
        escalation=flags.escalation,
        status=GameStatus(row["status"]),
        created_at=row["created_at"],
        epilogue=row.get("epilogue_json"),
        published=bool(row.get("published", False)),
        admin=bool(row.get("admin", False)),
        role=row.get("role") or "council",
        owner_id=row.get("owner_id"),
        ranked=bool(row.get("ranked", False)),
        difficulty=row.get("difficulty") or "intermediate",
        drift_enabled=flags.drift,
        result=row.get("result_json"),
        language=row.get("language") or "fr",
    )


def _player(row: dict) -> PlayerRecord:
    return PlayerRecord(
        id=row["id"],
        pseudo=row["pseudo"],
        is_admin=bool(row.get("is_admin", False)),
        created_at=str(row.get("created_at") or ""),
        xp=int(row.get("xp", 0)),
        market_balance=float(row.get("market_balance", 0.0)),
    )
