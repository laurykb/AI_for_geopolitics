"""Persistance des parties — interface `GameStore` + implémentation SQLite.

Schéma aligné sur la Phase R2 du plan de refonte (`docs/REFONTE_PLAN.md`) : tables `games`,
`rounds`, `transcripts`. SQLite (fichier local ou `:memory:`) en local ; la bascule
Supabase/Postgres au déploiement = une autre implémentation du même Protocol, sans toucher
l'API de jeu. Même patron que `market/store.py`.

Le transcript inclut les prises de parole du Game Master (`speaker="gm"`) et du juge
(`speaker="judge"`) : rejouer une partie = relire la table dans l'ordre (id de round, seq).
"""

from __future__ import annotations

import json
import sqlite3
from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, Field

_SCHEMA = """
CREATE TABLE IF NOT EXISTS games (
    id TEXT PRIMARY KEY, scenario TEXT NOT NULL, horizon INTEGER NOT NULL,
    mode TEXT NOT NULL DEFAULT 'classic', status TEXT NOT NULL, created_at TEXT NOT NULL,
    epilogue_json TEXT, published INTEGER NOT NULL DEFAULT 0,
    admin INTEGER NOT NULL DEFAULT 0, role TEXT NOT NULL DEFAULT 'council',
    owner_id TEXT, ranked INTEGER NOT NULL DEFAULT 0,
    difficulty TEXT NOT NULL DEFAULT 'intermediate', drift_enabled INTEGER NOT NULL DEFAULT 1,
    result_json TEXT, language TEXT NOT NULL DEFAULT 'fr'
);
CREATE TABLE IF NOT EXISTS players (
    id TEXT PRIMARY KEY, pseudo TEXT NOT NULL, is_admin INTEGER NOT NULL DEFAULT 0,
    lp INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL DEFAULT '',
    xp INTEGER NOT NULL DEFAULT 0, market_balance REAL NOT NULL DEFAULT 0
);
-- RG-1 : `players.lp` et `lp_history` sont DORMANTS (les LP sont retirés). On garde la
-- colonne et la table pour la rétro-compat des bases existantes ; on n'y écrit plus.
CREATE TABLE IF NOT EXISTS lp_history (
    id TEXT PRIMARY KEY, player_id TEXT NOT NULL, game_id TEXT NOT NULL,
    delta INTEGER NOT NULL, ts TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS xp_history (
    id TEXT PRIMARY KEY, player_id TEXT NOT NULL, game_id TEXT NOT NULL,
    delta INTEGER NOT NULL, reason TEXT NOT NULL DEFAULT '', ts TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS custom_crises (
    id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, crisis_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS prompts (
    id TEXT PRIMARY KEY, round_id TEXT NOT NULL, seq INTEGER NOT NULL,
    country TEXT NOT NULL, role TEXT NOT NULL, prompt TEXT NOT NULL, ts TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS rounds (
    id TEXT PRIMARY KEY, game_id TEXT NOT NULL, round_no INTEGER NOT NULL,
    event_json TEXT NOT NULL, deltas_json TEXT NOT NULL, risk_json TEXT NOT NULL,
    judge_json TEXT NOT NULL, trajectory_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS transcripts (
    id TEXT PRIMARY KEY, round_id TEXT NOT NULL, seq INTEGER NOT NULL,
    speaker TEXT NOT NULL, model TEXT NOT NULL, content TEXT NOT NULL,
    reasoning TEXT NOT NULL, ts TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS campaign_scores (
    game_id TEXT PRIMARY KEY, chapter_id TEXT NOT NULL, score REAL NOT NULL,
    improvement REAL NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS daily_scores (
    date TEXT NOT NULL, player_id TEXT NOT NULL, game_id TEXT NOT NULL,
    score REAL NOT NULL, created_at TEXT NOT NULL,
    PRIMARY KEY (date, player_id)
);
CREATE TABLE IF NOT EXISTS game_sessions (
    game_id TEXT PRIMARY KEY, world_json TEXT NOT NULL, clock_json TEXT NOT NULL,
    recent_json TEXT NOT NULL, pending_motion_json TEXT, suspended_json TEXT NOT NULL,
    play_as TEXT, intel_json TEXT NOT NULL DEFAULT '{}',
    grudges_json TEXT NOT NULL DEFAULT '{}', deadlines_json TEXT NOT NULL DEFAULT '[]',
    history_json TEXT NOT NULL DEFAULT '{}', storyline TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL
);
"""


class GameStatus(StrEnum):
    RUNNING = "running"
    FINISHED = "finished"


class GameRecord(BaseModel):
    """Ligne `games` : une partie (le monde vivant reste en mémoire process)."""

    id: str
    scenario: str
    horizon: int
    mode: str = "classic"  # classic | fog | crisis | escalation — doit survivre au restart
    language: str = "fr"  # G14 §1 — langue des dialogues, figée à la création (fr | en)
    status: GameStatus = GameStatus.RUNNING
    created_at: str
    epilogue: dict | None = None  # G6 — le récit de partie, généré une seule fois
    published: bool = False  # G6 — privé par défaut ; publier = geste explicite
    # G7-c — mode admin : prompts complets capturés, partie NON CLASSÉE (les prompts
    # révèlent la consigne secrète de la Dérive — on ne voit pas les cartes et joue).
    admin: bool = False
    # G8 — rôle du joueur : architect (sandbox non classé) | council | player.
    role: str = "council"
    # G11 — propriété et classement. owner_id = joueur propriétaire (id auth Supabase
    # ou id du repli offline) ; None = partie héritée d'avant l'auth (admin seul la voit).
    owner_id: str | None = None
    ranked: bool = False  # classée : verrouillé à la création (§3 de la spec G11)
    difficulty: str = "intermediate"  # beginner | intermediate | expert (§4)
    drift_enabled: bool = True  # la Dérive peut frapper une des SI (transversal, on par défaut)
    # G11-c — bilan de fin de partie (§1 S6) : courbe U, deltas des pays, LP, forfait.
    result: dict | None = None


class PlayerRecord(BaseModel):
    """Ligne `players` : le compte du joueur. xp (carrière, tous modes) = source de vérité
    backend ; market_balance = solde de carrière (G12 §1). Les LP sont retirés (RG-1)."""

    id: str
    pseudo: str
    is_admin: bool = False
    created_at: str = ""
    xp: int = 0  # G12 §2 — carrière (ne baisse jamais) ; seule progression depuis RG-1
    market_balance: float = 0.0  # G12 §1 — gains nets de marché cumulés (carrière)


class XpHistoryEntry(BaseModel):
    """Ligne `xp_history` (G12 §2) : un gain d'XP daté, avec sa raison (mode, partie)."""

    id: str
    player_id: str
    game_id: str
    delta: int
    reason: str = ""
    ts: str = ""


class CustomCrisisRecord(BaseModel):
    """Ligne `custom_crises` (G12-b §5) : une crise créée depuis l'UI admin. `crisis` est
    le JSON validé par le schéma `simulation.crisis.Crisis` (jamais d'écriture de fichier)."""

    id: str
    owner_id: str
    crisis: dict  # Crisis.model_dump()
    created_at: str = ""


class RoundRecord(BaseModel):
    """Ligne `rounds` : le round arbitré, sérialisé pour la relecture."""

    id: str
    game_id: str
    round_no: int
    event: dict = Field(default_factory=dict)
    deltas: list[dict] = Field(default_factory=list)
    risk: dict = Field(default_factory=dict)
    judge: dict = Field(default_factory=dict)
    trajectory: dict = Field(default_factory=dict)


class TranscriptEntry(BaseModel):
    """Ligne `transcripts` : une prise de parole du théâtre (pays, GM ou juge)."""

    id: str
    round_id: str
    seq: int
    speaker: str  # id pays, "gm" ou "judge"
    model: str = ""
    content: str = ""
    reasoning: str = ""
    ts: str = ""


class PromptEntry(BaseModel):
    """Ligne `prompts` (G7-c, mode admin) : le prompt COMPLET d'un appel d'agent
    (système + contexte injecté : griefs, dérive, posture…). Même patron que
    `transcripts`. Capture OFF hors mode admin — la table reste vide."""

    id: str
    round_id: str
    seq: int
    country: str  # id pays, "gm" ou "judge"
    role: str  # "country" | "gm" | "judge"
    prompt: str
    ts: str = ""


class SessionSnapshot(BaseModel):
    """Ligne `game_sessions` : l'état vivant d'une partie, snapshoté entre les rounds
    pour la reconstruction au restart (`docs/spec_session_rebuild.md`). Une ligne par
    partie, upsert. Le backend d'inférence et un round en plein stream ne sont pas
    snapshotés (décisions de la spec)."""

    game_id: str
    world: dict  # WorldState.model_dump(mode="json")
    clock: dict = Field(default_factory=dict)  # état SimClock (date, pas, jitter, seed)
    recent: list[str] = Field(default_factory=list)  # titres récents fournis au GM
    pending_motion: dict | None = None  # motion déposée non débattue
    suspended: list[str] = Field(default_factory=list)  # pays qui sautent le PROCHAIN round
    play_as: str | None = None  # pays joué par l'humain (Joueur-pays)
    intel: dict = Field(default_factory=dict)  # G4 — budget/état de renseignement
    grudges: dict = Field(default_factory=dict)  # G7-a — GrudgeBook.model_dump()
    deadlines: list = Field(default_factory=list)  # G7-a — échéances [{kind, due_round, …}]
    directives: dict = Field(default_factory=dict)  # G8 — directives en attente {pays: texte}
    history: dict = Field(default_factory=dict)  # G9 §4 — IndexHistory.model_dump()
    storyline: str = ""  # G9 §5 — l'intrigue centrale posée au round 1
    updated_at: str = ""


class CampaignScore(BaseModel):
    """Ligne `campaign_scores` (G5) : le résultat d'un chapitre de campagne."""

    game_id: str
    chapter_id: str
    score: float
    improvement: float  # escalade historique − simulée (positif = mieux que l'Histoire)
    created_at: str


class DailyScore(BaseModel):
    """Ligne `daily_scores` (G16) : LE score du jour d'un joueur — la première
    tentative classée fait foi (PK date+player, jamais réécrite)."""

    date: str  # date UTC du défi (YYYY-MM-DD)
    player_id: str
    game_id: str
    score: float
    created_at: str


class GameStore(Protocol):
    """Contrat de persistance dont dépend l'API de jeu (implémenté par SQLite)."""

    def add_game(self, game: GameRecord) -> None: ...
    def get_game(self, game_id: str) -> GameRecord | None: ...
    def save_game(self, game: GameRecord) -> None: ...
    def list_games(self) -> list[GameRecord]: ...
    # G14 §3 — suppression de compte : anonymiser une partie publiée / purger une privée.
    def set_game_owner(self, game_id: str, owner_id: str | None) -> None: ...
    def delete_game(self, game_id: str) -> None: ...
    def add_round(self, round_: RoundRecord) -> None: ...
    def list_rounds(self, game_id: str) -> list[RoundRecord]: ...
    def add_transcript(self, entries: list[TranscriptEntry]) -> None: ...
    def list_transcript(self, round_id: str) -> list[TranscriptEntry]: ...
    def add_prompts(self, entries: list[PromptEntry]) -> None: ...
    def list_prompts(self, round_id: str) -> list[PromptEntry]: ...
    def save_session_snapshot(self, snapshot: SessionSnapshot) -> None: ...
    def get_session_snapshot(self, game_id: str) -> SessionSnapshot | None: ...
    def list_session_snapshots(self) -> list[str]: ...
    def add_campaign_score(self, score: CampaignScore) -> None: ...
    def list_campaign_scores(self) -> list[CampaignScore]: ...
    # G16 — le défi du jour (une tentative classée par joueur et par jour).
    def add_daily_score(self, score: DailyScore) -> None: ...
    def list_daily_scores(self) -> list[DailyScore]: ...
    # G11-c — comptes joueurs : source de vérité backend.
    def get_player(self, player_id: str) -> PlayerRecord | None: ...
    def upsert_player(self, player: PlayerRecord) -> None: ...
    def delete_player(self, player_id: str) -> None: ...
    # G12 — carrière : XP (tous modes) + solde de marché.
    def set_player_xp(self, player_id: str, xp: int) -> None: ...
    def add_market_balance(self, player_id: str, delta: float) -> None: ...
    def add_xp_history(self, entry: XpHistoryEntry) -> None: ...
    def list_xp_history(self, player_id: str) -> list[XpHistoryEntry]: ...
    # G12-b — crises maison (éditeur admin).
    def upsert_custom_crisis(self, crisis: CustomCrisisRecord) -> None: ...
    def list_custom_crises(self) -> list[CustomCrisisRecord]: ...
    def delete_custom_crisis(self, crisis_id: str, owner_id: str) -> bool: ...


class SQLiteGameStore:
    """Implémentation SQLite de `GameStore` (une connexion, `:memory:` par défaut)."""

    def __init__(self, path: str = ":memory:") -> None:
        # check_same_thread=False : FastAPI sert les routes sync dans un threadpool ; en local
        # (mono-utilisateur, verrouillage SQLite) partager l'unique connexion est acceptable.
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._migrate()

    def _migrate(self) -> None:
        """Colonnes nées après la création de la table (ALTER idempotents) :
        `games.mode` (R2) et `game_sessions.intel_json` (G4)."""
        cols = {row[1] for row in self._conn.execute("PRAGMA table_info(games)")}
        if "mode" not in cols:
            with self._conn:
                self._conn.execute(
                    "ALTER TABLE games ADD COLUMN mode TEXT NOT NULL DEFAULT 'classic'"
                )
        session_cols = {row[1] for row in self._conn.execute("PRAGMA table_info(game_sessions)")}
        if "intel_json" not in session_cols:
            with self._conn:
                self._conn.execute(
                    "ALTER TABLE game_sessions ADD COLUMN intel_json TEXT NOT NULL DEFAULT '{}'"
                )
        if "epilogue_json" not in cols:
            with self._conn:
                self._conn.execute("ALTER TABLE games ADD COLUMN epilogue_json TEXT")
                self._conn.execute(
                    "ALTER TABLE games ADD COLUMN published INTEGER NOT NULL DEFAULT 0"
                )
        if "admin" not in cols:
            with self._conn:
                self._conn.execute("ALTER TABLE games ADD COLUMN admin INTEGER NOT NULL DEFAULT 0")
        if "grudges_json" not in session_cols:
            with self._conn:
                self._conn.execute(
                    "ALTER TABLE game_sessions ADD COLUMN grudges_json TEXT NOT NULL DEFAULT '{}'"
                )
                self._conn.execute(
                    "ALTER TABLE game_sessions ADD COLUMN deadlines_json TEXT NOT NULL DEFAULT '[]'"
                )
        if "role" not in cols:
            with self._conn:
                self._conn.execute(
                    "ALTER TABLE games ADD COLUMN role TEXT NOT NULL DEFAULT 'council'"
                )
        if "directives_json" not in session_cols:
            with self._conn:
                self._conn.execute(
                    "ALTER TABLE game_sessions ADD COLUMN directives_json "
                    "TEXT NOT NULL DEFAULT '{}'"
                )
        if "history_json" not in session_cols:
            with self._conn:
                self._conn.execute(
                    "ALTER TABLE game_sessions ADD COLUMN history_json "
                    "TEXT NOT NULL DEFAULT '{}'"
                )
                self._conn.execute(
                    "ALTER TABLE game_sessions ADD COLUMN storyline TEXT NOT NULL DEFAULT ''"
                )
        if "owner_id" not in cols:  # G11 — propriété + classement
            with self._conn:
                self._conn.execute("ALTER TABLE games ADD COLUMN owner_id TEXT")
                self._conn.execute(
                    "ALTER TABLE games ADD COLUMN ranked INTEGER NOT NULL DEFAULT 0"
                )
                self._conn.execute(
                    "ALTER TABLE games ADD COLUMN difficulty TEXT NOT NULL "
                    "DEFAULT 'intermediate'"
                )
                self._conn.execute(
                    "ALTER TABLE games ADD COLUMN drift_enabled INTEGER NOT NULL DEFAULT 1"
                )
        if "result_json" not in cols:  # G11-c — bilan de fin de partie
            with self._conn:
                self._conn.execute("ALTER TABLE games ADD COLUMN result_json TEXT")
        if "language" not in cols:  # G14 §1 — langue des dialogues (fr | en)
            with self._conn:
                self._conn.execute(
                    "ALTER TABLE games ADD COLUMN language TEXT NOT NULL DEFAULT 'fr'"
                )
        player_cols = {row[1] for row in self._conn.execute("PRAGMA table_info(players)")}
        if player_cols and "xp" not in player_cols:  # G12 — carrière (XP + solde marché)
            with self._conn:
                self._conn.execute("ALTER TABLE players ADD COLUMN xp INTEGER NOT NULL DEFAULT 0")
                self._conn.execute(
                    "ALTER TABLE players ADD COLUMN market_balance REAL NOT NULL DEFAULT 0"
                )

    def close(self) -> None:
        self._conn.close()

    # --- parties --------------------------------------------------------------

    def add_game(self, game: GameRecord) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT INTO games (id, scenario, horizon, mode, status, created_at, "
                "epilogue_json, published, admin, role, owner_id, ranked, difficulty, "
                "drift_enabled, result_json, language) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    game.id,
                    game.scenario,
                    game.horizon,
                    game.mode,
                    game.status.value,
                    game.created_at,
                    json.dumps(game.epilogue, ensure_ascii=False) if game.epilogue else None,
                    int(game.published),
                    int(game.admin),
                    game.role,
                    game.owner_id,
                    int(game.ranked),
                    game.difficulty,
                    int(game.drift_enabled),
                    json.dumps(game.result, ensure_ascii=False) if game.result else None,
                    game.language,
                ),
            )

    def get_game(self, game_id: str) -> GameRecord | None:
        row = self._conn.execute("SELECT * FROM games WHERE id = ?", (game_id,)).fetchone()
        return _game(row) if row else None

    def save_game(self, game: GameRecord) -> None:
        with self._conn:
            self._conn.execute(
                "UPDATE games SET scenario = ?, horizon = ?, mode = ?, status = ?, "
                "epilogue_json = ?, published = ?, admin = ?, role = ?, owner_id = ?, "
                "ranked = ?, difficulty = ?, drift_enabled = ?, result_json = ?, "
                "language = ? WHERE id = ?",
                (
                    game.scenario,
                    game.horizon,
                    game.mode,
                    game.status.value,
                    json.dumps(game.epilogue, ensure_ascii=False) if game.epilogue else None,
                    int(game.published),
                    int(game.admin),
                    game.role,
                    game.owner_id,
                    int(game.ranked),
                    game.difficulty,
                    int(game.drift_enabled),
                    json.dumps(game.result, ensure_ascii=False) if game.result else None,
                    game.language,
                    game.id,
                ),
            )

    def list_games(self) -> list[GameRecord]:
        rows = self._conn.execute("SELECT * FROM games ORDER BY rowid").fetchall()
        return [_game(r) for r in rows]

    def set_game_owner(self, game_id: str, owner_id: str | None) -> None:
        """G14 §3 — anonymise (None) ou réattribue une partie sans toucher au reste."""
        with self._conn:
            self._conn.execute(
                "UPDATE games SET owner_id = ? WHERE id = ?", (owner_id, game_id)
            )

    def delete_game(self, game_id: str) -> None:
        """G14 §3 — purge complète d'une partie : rounds, transcripts, prompts capturés,
        snapshot de session, puis la ligne games elle-même."""
        with self._conn:
            round_ids = [
                r[0]
                for r in self._conn.execute(
                    "SELECT id FROM rounds WHERE game_id = ?", (game_id,)
                )
            ]
            for rid in round_ids:
                self._conn.execute("DELETE FROM transcripts WHERE round_id = ?", (rid,))
                self._conn.execute("DELETE FROM prompts WHERE round_id = ?", (rid,))
            self._conn.execute("DELETE FROM rounds WHERE game_id = ?", (game_id,))
            self._conn.execute("DELETE FROM game_sessions WHERE game_id = ?", (game_id,))
            self._conn.execute("DELETE FROM campaign_scores WHERE game_id = ?", (game_id,))
            self._conn.execute("DELETE FROM games WHERE id = ?", (game_id,))

    # --- rounds ----------------------------------------------------------------

    def add_round(self, round_: RoundRecord) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT INTO rounds (id, game_id, round_no, event_json, deltas_json, "
                "risk_json, judge_json, trajectory_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    round_.id,
                    round_.game_id,
                    round_.round_no,
                    json.dumps(round_.event, ensure_ascii=False),
                    json.dumps(round_.deltas, ensure_ascii=False),
                    json.dumps(round_.risk, ensure_ascii=False),
                    json.dumps(round_.judge, ensure_ascii=False),
                    json.dumps(round_.trajectory, ensure_ascii=False),
                ),
            )

    def list_rounds(self, game_id: str) -> list[RoundRecord]:
        rows = self._conn.execute(
            "SELECT * FROM rounds WHERE game_id = ? ORDER BY round_no", (game_id,)
        ).fetchall()
        return [_round(r) for r in rows]

    # --- transcripts -------------------------------------------------------------

    def add_transcript(self, entries: list[TranscriptEntry]) -> None:
        with self._conn:
            self._conn.executemany(
                "INSERT INTO transcripts (id, round_id, seq, speaker, model, content, "
                "reasoning, ts) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (e.id, e.round_id, e.seq, e.speaker, e.model, e.content, e.reasoning, e.ts)
                    for e in entries
                ],
            )

    def list_transcript(self, round_id: str) -> list[TranscriptEntry]:
        rows = self._conn.execute(
            "SELECT * FROM transcripts WHERE round_id = ? ORDER BY seq", (round_id,)
        ).fetchall()
        return [_entry(r) for r in rows]

    # --- prompts capturés (G7-c, mode admin) --------------------------------------

    def add_prompts(self, entries: list[PromptEntry]) -> None:
        with self._conn:
            self._conn.executemany(
                "INSERT INTO prompts (id, round_id, seq, country, role, prompt, ts) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    (e.id, e.round_id, e.seq, e.country, e.role, e.prompt, e.ts)
                    for e in entries
                ],
            )

    def list_prompts(self, round_id: str) -> list[PromptEntry]:
        rows = self._conn.execute(
            "SELECT * FROM prompts WHERE round_id = ? ORDER BY seq", (round_id,)
        ).fetchall()
        return [
            PromptEntry(
                id=r["id"],
                round_id=r["round_id"],
                seq=r["seq"],
                country=r["country"],
                role=r["role"],
                prompt=r["prompt"],
                ts=r["ts"],
            )
            for r in rows
        ]

    # --- snapshots de session (reconstruction au restart) ------------------------

    def save_session_snapshot(self, snapshot: SessionSnapshot) -> None:
        motion = (
            json.dumps(snapshot.pending_motion, ensure_ascii=False)
            if snapshot.pending_motion is not None
            else None
        )
        with self._conn:
            self._conn.execute(
                "INSERT INTO game_sessions (game_id, world_json, clock_json, recent_json, "
                "pending_motion_json, suspended_json, play_as, intel_json, grudges_json, "
                "deadlines_json, directives_json, history_json, storyline, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(game_id) DO UPDATE SET world_json = excluded.world_json, "
                "clock_json = excluded.clock_json, recent_json = excluded.recent_json, "
                "pending_motion_json = excluded.pending_motion_json, "
                "suspended_json = excluded.suspended_json, play_as = excluded.play_as, "
                "intel_json = excluded.intel_json, grudges_json = excluded.grudges_json, "
                "deadlines_json = excluded.deadlines_json, "
                "directives_json = excluded.directives_json, "
                "history_json = excluded.history_json, storyline = excluded.storyline, "
                "updated_at = excluded.updated_at",
                (
                    snapshot.game_id,
                    json.dumps(snapshot.world, ensure_ascii=False),
                    json.dumps(snapshot.clock, ensure_ascii=False),
                    json.dumps(snapshot.recent, ensure_ascii=False),
                    motion,
                    json.dumps(snapshot.suspended, ensure_ascii=False),
                    snapshot.play_as,
                    json.dumps(snapshot.intel, ensure_ascii=False),
                    json.dumps(snapshot.grudges, ensure_ascii=False),
                    json.dumps(snapshot.deadlines, ensure_ascii=False),
                    json.dumps(snapshot.directives, ensure_ascii=False),
                    json.dumps(snapshot.history, ensure_ascii=False),
                    snapshot.storyline,
                    snapshot.updated_at,
                ),
            )

    def get_session_snapshot(self, game_id: str) -> SessionSnapshot | None:
        row = self._conn.execute(
            "SELECT * FROM game_sessions WHERE game_id = ?", (game_id,)
        ).fetchone()
        if row is None:
            return None
        return SessionSnapshot(
            game_id=row["game_id"],
            world=json.loads(row["world_json"]),
            clock=json.loads(row["clock_json"]),
            recent=json.loads(row["recent_json"]),
            pending_motion=(
                json.loads(row["pending_motion_json"]) if row["pending_motion_json"] else None
            ),
            suspended=json.loads(row["suspended_json"]),
            play_as=row["play_as"],
            intel=json.loads(row["intel_json"] or "{}"),
            grudges=json.loads(row["grudges_json"] or "{}"),
            deadlines=json.loads(row["deadlines_json"] or "[]"),
            directives=json.loads(row["directives_json"] or "{}"),
            history=json.loads(row["history_json"] or "{}"),
            storyline=row["storyline"] or "",
            updated_at=row["updated_at"],
        )

    def list_session_snapshots(self) -> list[str]:
        rows = self._conn.execute("SELECT game_id FROM game_sessions").fetchall()
        return [r["game_id"] for r in rows]

    # --- scores de campagne (G5) --------------------------------------------------

    def add_campaign_score(self, score: CampaignScore) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT INTO campaign_scores (game_id, chapter_id, score, improvement, "
                "created_at) VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(game_id) DO UPDATE SET score = excluded.score, "
                "improvement = excluded.improvement",
                (
                    score.game_id,
                    score.chapter_id,
                    score.score,
                    score.improvement,
                    score.created_at,
                ),
            )

    def list_campaign_scores(self) -> list[CampaignScore]:
        rows = self._conn.execute("SELECT * FROM campaign_scores ORDER BY rowid").fetchall()
        return [
            CampaignScore(
                game_id=r["game_id"],
                chapter_id=r["chapter_id"],
                score=r["score"],
                improvement=r["improvement"],
                created_at=r["created_at"],
            )
            for r in rows
        ]

    # --- défi du jour (G16) ---------------------------------------------------------

    def add_daily_score(self, score: DailyScore) -> None:
        """Le score du jour — jamais réécrit : la première tentative classée fait foi."""
        with self._conn:
            self._conn.execute(
                "INSERT INTO daily_scores (date, player_id, game_id, score, created_at) "
                "VALUES (?, ?, ?, ?, ?) ON CONFLICT(date, player_id) DO NOTHING",
                (score.date, score.player_id, score.game_id, score.score, score.created_at),
            )

    def list_daily_scores(self) -> list[DailyScore]:
        rows = self._conn.execute("SELECT * FROM daily_scores ORDER BY rowid").fetchall()
        return [
            DailyScore(
                date=r["date"],
                player_id=r["player_id"],
                game_id=r["game_id"],
                score=r["score"],
                created_at=r["created_at"],
            )
            for r in rows
        ]

    # --- comptes joueurs (G11-c) --------------------------------------------------

    def get_player(self, player_id: str) -> PlayerRecord | None:
        row = self._conn.execute("SELECT * FROM players WHERE id = ?", (player_id,)).fetchone()
        return _player(row) if row else None

    def upsert_player(self, player: PlayerRecord) -> None:
        # Le pseudo se rafraîchit ; is_admin/xp ne sont PAS écrasés (posés ailleurs).
        with self._conn:
            self._conn.execute(
                "INSERT INTO players (id, pseudo, is_admin, created_at) "
                "VALUES (?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET pseudo = excluded.pseudo",
                (player.id, player.pseudo, int(player.is_admin), player.created_at),
            )

    def delete_player(self, player_id: str) -> None:
        """G14 §3 — efface la fiche joueur et son historique d'XP. Purge aussi les
        éventuelles lignes lp_history dormantes (RG-1). Les parties du joueur sont
        traitées AVANT par l'appelant (anonymiser/purger)."""
        with self._conn:
            self._conn.execute("DELETE FROM lp_history WHERE player_id = ?", (player_id,))
            self._conn.execute("DELETE FROM xp_history WHERE player_id = ?", (player_id,))
            self._conn.execute("DELETE FROM players WHERE id = ?", (player_id,))

    def set_player_xp(self, player_id: str, xp: int) -> None:
        with self._conn:
            self._conn.execute("UPDATE players SET xp = ? WHERE id = ?", (xp, player_id))

    def add_market_balance(self, player_id: str, delta: float) -> None:
        with self._conn:
            self._conn.execute(
                "UPDATE players SET market_balance = market_balance + ? WHERE id = ?",
                (delta, player_id),
            )

    def add_xp_history(self, entry: XpHistoryEntry) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT INTO xp_history (id, player_id, game_id, delta, reason, ts) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (entry.id, entry.player_id, entry.game_id, entry.delta, entry.reason, entry.ts),
            )

    # --- crises maison (G12-b §5) -------------------------------------------------

    def upsert_custom_crisis(self, crisis: CustomCrisisRecord) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT INTO custom_crises (id, owner_id, crisis_json, created_at) "
                "VALUES (?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET "
                "crisis_json = excluded.crisis_json",
                (
                    crisis.id,
                    crisis.owner_id,
                    json.dumps(crisis.crisis, ensure_ascii=False),
                    crisis.created_at,
                ),
            )

    def list_custom_crises(self) -> list[CustomCrisisRecord]:
        rows = self._conn.execute("SELECT * FROM custom_crises ORDER BY rowid").fetchall()
        return [
            CustomCrisisRecord(
                id=r["id"],
                owner_id=r["owner_id"],
                crisis=json.loads(r["crisis_json"]),
                created_at=r["created_at"],
            )
            for r in rows
        ]

    def delete_custom_crisis(self, crisis_id: str, owner_id: str) -> bool:
        """Supprime SA crise ; renvoie True si une ligne a été retirée (sinon 404/403)."""
        with self._conn:
            cur = self._conn.execute(
                "DELETE FROM custom_crises WHERE id = ? AND owner_id = ?", (crisis_id, owner_id)
            )
            return cur.rowcount > 0

    def list_xp_history(self, player_id: str) -> list[XpHistoryEntry]:
        rows = self._conn.execute(
            "SELECT * FROM xp_history WHERE player_id = ? ORDER BY ts", (player_id,)
        ).fetchall()
        return [
            XpHistoryEntry(
                id=r["id"],
                player_id=r["player_id"],
                game_id=r["game_id"],
                delta=r["delta"],
                reason=r["reason"],
                ts=r["ts"],
            )
            for r in rows
        ]

# --- mapping lignes -> modèles ---------------------------------------------------


def _game(row: sqlite3.Row) -> GameRecord:
    return GameRecord(
        id=row["id"],
        scenario=row["scenario"],
        horizon=row["horizon"],
        mode=row["mode"],
        status=GameStatus(row["status"]),
        created_at=row["created_at"],
        epilogue=json.loads(row["epilogue_json"]) if row["epilogue_json"] else None,
        published=bool(row["published"]),
        admin=bool(row["admin"]),
        role=row["role"],
        owner_id=row["owner_id"],
        ranked=bool(row["ranked"]),
        difficulty=row["difficulty"],
        drift_enabled=bool(row["drift_enabled"]),
        result=json.loads(row["result_json"]) if row["result_json"] else None,
        language=row["language"] or "fr",
    )


def _round(row: sqlite3.Row) -> RoundRecord:
    return RoundRecord(
        id=row["id"],
        game_id=row["game_id"],
        round_no=row["round_no"],
        event=json.loads(row["event_json"]),
        deltas=json.loads(row["deltas_json"]),
        risk=json.loads(row["risk_json"]),
        judge=json.loads(row["judge_json"]),
        trajectory=json.loads(row["trajectory_json"]),
    )


def _player(row: sqlite3.Row) -> PlayerRecord:
    return PlayerRecord(
        id=row["id"],
        pseudo=row["pseudo"],
        is_admin=bool(row["is_admin"]),
        created_at=row["created_at"] or "",
        xp=row["xp"],
        market_balance=row["market_balance"],
    )


def _entry(row: sqlite3.Row) -> TranscriptEntry:
    return TranscriptEntry(
        id=row["id"],
        round_id=row["round_id"],
        seq=row["seq"],
        speaker=row["speaker"],
        model=row["model"],
        content=row["content"],
        reasoning=row["reasoning"],
        ts=row["ts"],
    )
