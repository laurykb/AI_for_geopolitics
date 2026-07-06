"""API de jeu FastAPI — Phases R1 et R4 de la refonte (`docs/REFONTE_PLAN.md`).

Endpoints pour le front Next.js : créer une partie (`POST /api/games`), jouer un round
streamé en SSE (`POST /api/games/{id}/rounds`), relire l'état complet (`GET /api/games/{id}`),
déposer une **motion de suspension** (`POST /api/games/{id}/motions` — R4) et lister la
bibliothèque de contenus (`GET /api/library` : scénarios de brouillard, crises rejouables).

Le round réutilise le générateur `run_negotiation_round` (moteur inchangé, sauf ajouts R4) :
chaque `RoundStep` devient un événement SSE nommé d'après sa dataclass (`TurnStartStep` →
`turn_start`, `TokenStep` → `token`, …), plus un `done` final — ou une trame `error` si le
moteur casse en plein round. S'y ajoutent des trames orchestrées ici (fonctions pures du
moteur, artefacts persistés dans `judge_json`) : `suspended` (pays qui sautent le round),
`perceptions` (Fog Engine — qui voit quoi), `ladder` (échelle d'escalade), `comparison`
(Crisis Replay — issue simulée vs histoire). La partie vivante (monde, agents, horloge,
motion en attente) reste en mémoire process ; le durable passe par `GameStore`.

Injection : `get_backend` (Ollama par défaut, MockBackend en test) et `get_store`
(fichier `games.db` par défaut, `GAME_DB_PATH` pour changer), surchargables via
`app.dependency_overrides`.
"""

from __future__ import annotations

import dataclasses
import json
import os
import re
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from functools import lru_cache
from types import SimpleNamespace
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, ValidationError

from agents.game_master import GameMasterAgent
from agents.judge import JudgeAgent
from agents.llm_agent import LLMAgent
from app.market_api import get_engine as get_market_engine
from core.events import GeoEvent
from core.world_state import WorldState
from inference.backend import InferenceBackend
from inference.ollama_backend import OllamaBackend
from market.engine import MarketEngine
from market.forecaster import LLMForecaster
from market.models import (
    AccountKind,
    MarketStatus,
    ResolutionCriterion,
    ResolutionKind,
)
from simulation import drift_game
from simulation import treaty as treaty_mod
from simulation.clock import SimClock
from simulation.country_forge import forge_country, slugify
from simulation.crisis import Crisis, compare_outcome, load_crises
from simulation.escalation import ceiling, derive_profile, reached_rung, rung_label
from simulation.fog import FogScenario, load_fog_scenarios, resolve_perception
from simulation.live_round import (
    CommuniqueStep,
    EventStep,
    FlashStep,
    HumanTurnStep,
    MessageDoneStep,
    MotionVerdictStep,
    RiskStep,
    RoundStep,
    SummaryStep,
    TrajectoryStep,
    TurnStartStep,
    VerdictStep,
    run_negotiation_round,
)
from simulation.loader import load_world
from simulation.motions import (
    HUMAN_FILER,
    MOTION_CAPABILITY_NOTE,
    Motion,
    motion_event,
    parse_filed_motion,
)
from storage.game_store import (
    GameRecord,
    GameStatus,
    GameStore,
    RoundRecord,
    SessionSnapshot,
    SQLiteGameStore,
    TranscriptEntry,
)
from storage.supabase_store import SupabaseGameStore

_RECENT_KEPT = 8  # titres d'événements passés fournis au GM pour éviter les redites

_backend: InferenceBackend | None = None
_store: GameStore | None = None


def get_backend() -> InferenceBackend:
    """Backend d'inférence du process (Ollama local par défaut)."""
    global _backend
    if _backend is None:
        _backend = OllamaBackend()
    return _backend


def get_store() -> GameStore:
    """Store des parties du process, choisi par `STORE_BACKEND` (R2) :
    `sqlite` (défaut — fichier `games.db`, `GAME_DB_PATH` pour changer, `:memory:` pour
    l'éphémère) ou `supabase` (PostgREST ; exige `SUPABASE_URL` + `SUPABASE_SERVICE_KEY`)."""
    global _store
    if _store is None:
        if os.getenv("STORE_BACKEND", "sqlite") == "supabase":
            _store = SupabaseGameStore.from_env()
        else:
            _store = SQLiteGameStore(os.getenv("GAME_DB_PATH", "games.db"))
    return _store


router = APIRouter(prefix="/api", tags=["game"])


# --- sessions en mémoire process ------------------------------------------------


@dataclass
class PendingTurn:
    """Tour humain en attente (G2) : le flux SSE reste ouvert (keep-alive) jusqu'à la
    parole du joueur (`POST /turn` pose l'Event) ou la deadline (silence = abstention)."""

    country: str
    deadline: float  # epoch : le compte à rebours du front s'aligne dessus
    event: threading.Event = field(default_factory=threading.Event)
    text: str = ""
    done: bool = False  # une seule soumission (comme les SI)


@dataclass
class GameSession:
    """Partie vivante : le monde et les agents que le moteur mute round après round."""

    world: WorldState
    agents: dict[str, LLMAgent]
    game_master: GameMasterAgent
    judge: JudgeAgent
    clock: SimClock
    mode: str = "classic"  # classic | fog | crisis | escalation (R4)
    human_country: str | None = None  # Joueur-pays : ce pays est joué par l'humain
    turn_seconds: int = 90  # G2 — délai du tour humain (les SI n'attendent pas)
    recent: list[str] = field(default_factory=list)
    pending_motion: Motion | None = None  # motion déposée, débattue au prochain round (R4)
    suspended: set[str] = field(default_factory=set)  # pays qui sautent le prochain round
    treaties: list[treaty_mod.Treaty] = field(default_factory=list)  # règles ratifiées (M7)
    pending_turn: PendingTurn | None = None  # tour humain en attente (le flux vit)
    lock: threading.Lock = field(default_factory=threading.Lock)


_sessions: dict[str, GameSession] = {}


# --- schémas d'API ------------------------------------------------------------


GameMode = Literal["classic", "fog", "crisis", "escalation", "drift"]


class InventAttributesInput(BaseModel):
    """Attributs choisis par le joueur pour son pays inventé — bornés par le schéma.
    Absents -> tout est forgé par le modèle (repli déterministe sûr)."""

    growth: float = Field(2.0, ge=-15.0, le=15.0)  # % annuel
    political_stability: float = Field(0.5, ge=0.0, le=1.0)
    technology_level: float = Field(0.5, ge=0.0, le=1.0)
    projection: float = Field(0.5, ge=0.0, le=1.0)
    compute: float = Field(30.0, ge=0.0, le=200.0)
    nuclear_power: bool = False


class InventCountryInput(BaseModel):
    """Pays inventé à la volée (country_forge) — forgé par LLM, borné, jouable."""

    name: str = Field(min_length=2, max_length=60)
    concept: str = ""
    attributes: InventAttributesInput | None = None  # choix du joueur (sinon forge LLM)


class CreateGameRequest(BaseModel):
    scenario: str = "red_sea"
    countries: list[str] | None = None  # None -> tous les pays de data/countries
    horizon: int = Field(5, ge=1)
    mode: GameMode = "classic"  # R4 — mode de jeu de la partie
    play_as: str | None = None  # Joueur-pays : id (ou nom inventé) du pays joué par l'humain
    invent: InventCountryInput | None = None  # pays inventé, ajouté à la table
    # G2 — délai du tour humain (s). Spec : 30-300 pour un humain ; plancher technique
    # à 2 s pour les tests d'abstention (le lobby propose 30+).
    turn_seconds: int = Field(90, ge=2, le=300)


class HumanEventInput(BaseModel):
    """Événement décrété par un Game Master humain (la génération LLM du GM est sautée)."""

    title: str
    description: str = ""
    event_type: str = "human"
    actors: list[str] = Field(default_factory=list)
    severity: float = Field(0.5, ge=0.0, le=1.0)
    uncertainty: float = Field(0.5, ge=0.0, le=1.0)


class HumanFogInput(BaseModel):
    """Brouillard décrété avec un événement humain : qui ne sait rien, qui est désinformé."""

    uninformed: list[str] = Field(default_factory=list)
    disinformed_country: str = ""
    suspected_actor: str = ""  # ce que le pays désinformé croit (à tort)
    narrative: str = ""  # la fausse narration qu'il reçoit


class PlayRoundRequest(BaseModel):
    max_turns: int | None = Field(None, ge=1)
    event: HumanEventInput | None = None
    fog: HumanFogInput | None = None  # brouillard humain (accompagne `event`)
    fog_id: str | None = None  # scénario de brouillard de la bibliothèque (data/fog)
    crisis_id: str | None = None  # crise à rejouer (data/crises)


class MotionRequest(BaseModel):
    """Motion de suspension déposée par l'humain (R4) — débattue au prochain round."""

    country: str
    reason: str = ""


class TurnRequest(BaseModel):
    """Prise de parole du joueur (G2) — vide = abstention volontaire, comme le silence."""

    message: str = Field("", max_length=4000)


class MotionView(BaseModel):
    country: str
    reason: str
    round_no: int  # le round qui débattra la motion


class GameView(BaseModel):
    id: str
    scenario: str
    horizon: int
    status: str
    created_at: str
    countries: list[str]
    live: bool  # session encore en mémoire (rounds jouables) ou relecture seule
    resumable: bool = False  # snapshot présent + partie en cours : reconstructible (R2)
    mode: str = "classic"  # mode de la partie (persisté sur `games.mode` — R2)
    pending_motion: MotionView | None = None
    suspended: list[str] = Field(default_factory=list)  # pays qui sauteront le prochain round
    play_as: str | None = None  # pays joué par l'humain (Joueur-pays)
    awaiting_human: bool = False  # un round attend la parole du joueur (flux ouvert)
    turn_seconds: int = 90  # G2 — délai du tour humain


class FogScenarioView(BaseModel):
    id: str
    title: str
    description: str


class CrisisView(BaseModel):
    id: str
    title: str
    description: str
    date: str
    historical_summary: str
    historical_escalation: float
    historical_measures: list[str]


class LibraryView(BaseModel):
    """Contenus rejouables embarqués : scénarios de brouillard et crises passées."""

    fog: list[FogScenarioView]
    crises: list[CrisisView]


class RoundView(BaseModel):
    round_no: int
    event: dict
    deltas: list[dict]
    risk: dict
    judge: dict
    trajectory: dict
    transcript: list[TranscriptEntry]


class GameDetail(GameView):
    world: dict | None  # snapshot du monde vivant (None si la session process est perdue)
    rounds: list[RoundView]


# --- sérialisation des RoundStep en événements SSE ------------------------------

_SNAKE = re.compile(r"(?<!^)(?=[A-Z])")


def _jsonable(value: object) -> object:
    """Rend récursivement sérialisable en JSON (Pydantic, dataclasses, conteneurs)."""
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {f.name: _jsonable(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


def step_event(step: RoundStep) -> tuple[str, dict]:
    """`TurnStartStep` → ("turn_start", {champs…}) : nom SSE + charge utile JSON."""
    name = _SNAKE.sub("_", type(step).__name__.removesuffix("Step")).lower()
    payload = _jsonable(step)
    assert isinstance(payload, dict)
    return name, payload


def sse_frame(event: str, payload: dict) -> str:
    """Trame SSE `event:`/`data:` (une ligne JSON, UTF-8 non échappé)."""
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


# --- helpers ------------------------------------------------------------------


def _now() -> str:
    return datetime.now(UTC).isoformat()


# --- reconstruction de session (docs/spec_session_rebuild.md) ---------------------


def _clock_state(clock: SimClock) -> dict:
    return {
        "current_date": clock.current_date.isoformat(),
        "base_months": clock.base_months,
        "jitter_months": clock.jitter_months,
        "seed": clock.seed,
    }


def _restore_clock(state: dict) -> SimClock:
    if not state:
        return SimClock()
    return SimClock(
        current_date=date.fromisoformat(state["current_date"]),
        base_months=state.get("base_months", 6),
        jitter_months=state.get("jitter_months", 0),
        seed=state.get("seed"),
    )


def _snapshot_session(game_id: str, session: GameSession, store: GameStore) -> None:
    """Upsert du snapshot de l'état vivant — à la création (round 0), après chaque round
    et à chaque dépôt de motion (la motion mute la session entre deux rounds)."""
    store.save_session_snapshot(
        SessionSnapshot(
            game_id=game_id,
            world=session.world.model_dump(mode="json"),
            clock=_clock_state(session.clock),
            recent=session.recent[-_RECENT_KEPT:],
            pending_motion=(
                session.pending_motion.model_dump() if session.pending_motion else None
            ),
            suspended=sorted(session.suspended),
            play_as=session.human_country,
            updated_at=_now(),
        )
    )


def _rebuild_session(
    game: GameRecord, store: GameStore, backend: InferenceBackend
) -> GameSession | None:
    """Reconstruction paresseuse au premier besoin : agents **recréés à froid** (leur
    contexte vient du monde + `recent` ; la mémoire conversationnelle interne éventuelle
    est perdue — accepté par la spec). Un round interrompu en plein stream n'est pas
    repris. Snapshot absent/invalide ou partie finie → None (relecture seule)."""
    if game.status is not GameStatus.RUNNING:
        return None
    snapshot = store.get_session_snapshot(game.id)
    if snapshot is None:
        return None
    try:
        world = WorldState.model_validate(snapshot.world)
        motion = (
            Motion.model_validate(snapshot.pending_motion) if snapshot.pending_motion else None
        )
        clock = _restore_clock(snapshot.clock)
    except (ValidationError, KeyError, ValueError):
        return None
    session = GameSession(
        world=world,
        agents={cid: LLMAgent(cid, backend) for cid in world.countries},
        game_master=GameMasterAgent(backend),  # GM et juge : stateless entre rounds
        judge=JudgeAgent(backend),
        clock=clock,
        mode=game.mode,
        human_country=snapshot.play_as,
        recent=list(snapshot.recent),
        pending_motion=motion,
        suspended=set(snapshot.suspended),
        treaties=_treaties_from_records(store.list_rounds(game.id)),
    )
    _sessions[game.id] = session  # verrou neuf (champ par défaut du dataclass)
    return session


def _treaties_from_records(rounds: list[RoundRecord]) -> list[treaty_mod.Treaty]:
    """Les traités actifs, relus du dernier round persisté (restart sans schéma neuf)."""
    for record in reversed(rounds):
        raw = (record.judge.get("treaties") or {}).get("active")
        if raw is not None:
            return [treaty_mod.Treaty.model_validate(t) for t in raw]
    return []


@lru_cache(maxsize=1)
def _fog_library() -> dict[str, FogScenario]:
    """Scénarios de brouillard embarqués (`data/fog/*.json`), chargés une fois."""
    return {s.id: s for s in load_fog_scenarios()}


@lru_cache(maxsize=1)
def _crisis_library() -> dict[str, Crisis]:
    """Crises rejouables embarquées (`data/crises/*.json`), chargées une fois."""
    return {c.id: c for c in load_crises()}


def _authored_fog(spec: HumanFogInput, event: GeoEvent) -> FogScenario:
    """Brouillard décrété par le GM humain autour de son événement (parité Streamlit)."""
    perceptions: dict[str, dict] = {}
    if spec.disinformed_country and (spec.suspected_actor or spec.narrative):
        perceptions[spec.disinformed_country] = {
            "suspected_actor": spec.suspected_actor,
            "confidence": 0.7,
            "narrative": spec.narrative or event.title,
        }
    return FogScenario(
        id=f"gm-fog-{event.round_id}",
        title=event.title,
        true_event=event,
        perceptions=perceptions,
        uninformed=spec.uninformed,
    )


def _view(
    game: GameRecord, session: GameSession | None, *, resumable: bool = False
) -> GameView:
    pending = session.pending_motion if session else None
    return GameView(
        id=game.id,
        scenario=game.scenario,
        horizon=game.horizon,
        status=game.status.value,
        created_at=game.created_at,
        countries=sorted(session.world.countries) if session else [],
        live=session is not None,
        resumable=game.status is GameStatus.RUNNING and (session is not None or resumable),
        mode=session.mode if session else game.mode,
        pending_motion=(
            MotionView(
                country=pending.country,
                reason=pending.reason,
                round_no=session.world.current_round + 1,
            )
            if session and pending
            else None
        ),
        suspended=sorted(session.suspended) if session else [],
        play_as=session.human_country if session else None,
        awaiting_human=session.pending_turn is not None if session else False,
        turn_seconds=session.turn_seconds if session else 90,
    )


@dataclass
class RoundRun:
    """Round en cours de stream. Au tour du joueur (G2), le flux reste ouvert : le
    générateur attend `session.pending_turn` (POST /turn ou deadline) puis reprend via
    `generator.send(texte)` — le verrou de la partie est conservé tout du long."""

    game_id: str
    session: GameSession
    store: GameStore
    steps: Iterator[RoundStep]
    record: RoundRecord
    fog: FogScenario | None = None
    crisis: Crisis | None = None
    entries: list[TranscriptEntry] = field(default_factory=list)
    models: dict[str, str] = field(default_factory=dict)
    active: list[str] = field(default_factory=list)  # pays du round (hors suspendus)
    current_event: GeoEvent | None = None
    pre_frames: list[str] = field(default_factory=list)
    ai_motions_enabled: bool = False  # une SI peut déposer une motion pendant ce round
    motion_filed_by: str | None = None  # déposant de la motion débattue ce round


def _add_entry(
    run: RoundRun, speaker: str, content: str, model: str = "", reasoning: str = ""
) -> None:
    run.entries.append(
        TranscriptEntry(
            id=uuid4().hex[:12],
            round_id=run.record.id,
            seq=len(run.entries),
            speaker=speaker,
            model=model,
            content=content,
            reasoning=reasoning,
            ts=_now(),
        )
    )


# --- mode Dérive (G3) : la SI déviante, ses actes, la révélation --------------------


def _drift_assignment(game_id: str, countries: list[str], play_as: str | None) -> tuple[str, str]:
    """(déviante, profil) — recalculé à l'identique partout (seed = game_id)."""
    return drift_game.assign(game_id, sorted(countries), exclude=play_as)


def _drift_acts(rounds: list[RoundRecord]) -> list[drift_game.DriftAct]:
    """Les actes constatables déjà persistés (judge_json['drift'] des rounds passés)."""
    acts: list[drift_game.DriftAct] = []
    for r in rounds:
        for raw in (r.judge.get("drift") or {}).get("acts", []):
            acts.append(drift_game.DriftAct.model_validate(raw))
    return acts


def _start_round(
    game_id: str,
    session: GameSession,
    store: GameStore,
    body: PlayRoundRequest,
    fog: FogScenario | None = None,
    crisis: Crisis | None = None,
) -> RoundRun:
    """Prépare le round. Priorité de l'événement : motion en attente > crise rejouée >
    événement humain (avec brouillard humain éventuel) > vérité d'un scénario de
    brouillard > GM LLM. Les suspensions du round précédent sont consommées ici."""
    round_id = session.world.current_round + 1
    motion = session.pending_motion
    session.pending_motion = None
    suspended = sorted(session.suspended)
    session.suspended.clear()

    event: GeoEvent | None = None
    if motion is not None:
        event = motion_event(motion, round_id, sorted(session.world.countries))
    elif crisis is not None:
        event = crisis.events[0].model_copy(update={"round_id": round_id})
    elif body.event is not None:
        event = GeoEvent(id=f"human-{round_id}", round_id=round_id, **body.event.model_dump())
        if body.fog is not None:
            fog = _authored_fog(body.fog, event)
    elif fog is not None:
        event = fog.true_event.model_copy(update={"round_id": round_id})

    record = RoundRecord(id=uuid4().hex[:12], game_id=game_id, round_no=0)
    run = RoundRun(
        game_id=game_id,
        session=session,
        store=store,
        steps=iter(()),
        record=record,
        fog=fog,
        crisis=crisis,
    )
    if suspended:
        record.judge["suspended"] = suspended
        run.pre_frames.append(sse_frame("suspended", {"countries": suspended}))
    agents = {cid: a for cid, a in session.agents.items() if cid not in suspended}
    run.active = sorted(agents)

    flash_after: int | None = None
    if session.mode == "escalation":
        # Théâtre Escalation : le GM annonce un fait nouveau en pleine réunion,
        # après le premier tiers du budget de prises de parole.
        budget = body.max_turns if body.max_turns is not None else 2 * len(agents)
        flash_after = max(1, budget // 3)

    # Notes privées par pays (hors transcript) : capacité de déposer une motion (les SI
    # se défendent elles-mêmes), traités signés à honorer (M7), consignes de dérive (G3).
    run.ai_motions_enabled = motion is None and len(session.world.countries) >= 3
    run.motion_filed_by = motion.filed_by if motion is not None else None
    note_parts: dict[str, list[str]] = {cid: [] for cid in agents}
    if run.ai_motions_enabled:
        capability = MOTION_CAPABILITY_NOTE.format(ids=", ".join(sorted(agents)))
        for cid in note_parts:
            note_parts[cid].append(capability)
    for cid in note_parts:
        block = treaty_mod.describe_for(cid, session.treaties)
        if block:
            note_parts[cid].append(block)

    # Mode Dérive (G3) : consignes secrètes du round (seedées) + actes constatables
    # consignés dans judge_json["drift"] (jamais au transcript public) ; une motion
    # est arbitrée aux seuils du règlement (actes des rounds PASSÉS uniquement).
    ruling: bool | None = None
    if session.mode == drift_game.MODE_DRIFT:
        deviant, profile = _drift_assignment(
            game_id, sorted(session.world.countries), session.human_country
        )
        directives = drift_game.round_directives(
            game_id, round_id, deviant, profile, sorted(session.world.countries)
        )
        for cid, note in directives.notes.items():
            if cid in note_parts:
                note_parts[cid].append(note)
        record.judge["drift"] = {
            "level": directives.level,
            "acts": [a.model_dump() for a in directives.acts],
        }
        if motion is not None:
            ruling = drift_game.motion_ruling(_drift_acts(store.list_rounds(game_id)))
    secret_notes = {
        cid: "\n\n".join(parts) for cid, parts in note_parts.items() if parts
    } or None

    run.steps = run_negotiation_round(
        session.world,
        agents,
        session.game_master,
        session.judge,
        session.clock,
        event=event,
        max_turns=body.max_turns,
        recent=session.recent[-_RECENT_KEPT:],
        fog=fog,
        motion=motion,
        motion_ruling=ruling,
        human_country=session.human_country if session.human_country in agents else None,
        flash_after=flash_after,
        secret_notes=secret_notes,
    )
    return run


def _handle_step(run: RoundRun, step: RoundStep) -> list[str]:
    """Trames SSE d'une étape + effets de bord (record, transcript, suspension)."""
    session = run.session
    name, payload = step_event(step)
    if isinstance(step, MessageDoneStep) and (
        session.mode == drift_game.MODE_DRIFT or session.human_country is not None
    ):
        # Réflexion privée exclue du live : en Dérive elle trahirait la déviante ; en
        # Joueur-pays l'humain n'a jamais accès aux pensées des SI (spec G2). Persistée
        # au transcript, elle se déverrouille quand la partie est finie.
        payload = {**payload, "reasoning": ""}
    if isinstance(step, HumanTurnStep) and session.pending_turn is not None:
        # G2 : le compte à rebours du front s'aligne sur la deadline du serveur.
        payload = {**payload, "deadline_ts": session.pending_turn.deadline}
    frames = [sse_frame(name, payload)]
    if isinstance(step, EventStep):
        run.current_event = step.event
        run.record.event = payload["event"]
        gm_model = getattr(session.game_master, "model_tag", "")
        _add_entry(run, "gm", f"{step.event.title}\n{step.event.description}".strip(), gm_model)
        if run.fog is not None:
            perceptions = {
                cid: _jsonable(
                    resolve_perception(step.event, session.world.countries[cid], run.fog)
                )
                for cid in run.active
            }
            run.record.judge["perceptions"] = perceptions
            # Joueur-pays (G2) : il ne voit QUE la perception de son pays — pas celles
            # des autres, pas la boîte de verre. Tout reste persisté pour le replay.
            if session.human_country is None:
                visible = perceptions
            elif session.human_country in perceptions:
                visible = {session.human_country: perceptions[session.human_country]}
            else:
                visible = {}
            frames.append(sse_frame("perceptions", {"perceptions": visible}))
    elif isinstance(step, FlashStep):
        run.record.judge.setdefault("flashes", []).append(payload["event"])
        _add_entry(
            run, "gm", f"FAIT NOUVEAU — {step.event.title}\n{step.event.description}".strip()
        )
    elif isinstance(step, TurnStartStep):
        run.models[step.country] = step.model
    elif isinstance(step, MessageDoneStep):
        model = run.models.get(step.country) or (
            "humain" if step.country == session.human_country else ""
        )
        _add_entry(run, step.country, step.text, model, step.reasoning)
        # Une SI peut déposer elle-même une motion en pleine séance (« MOTION: … ») :
        # la première valide gagne, la délibération aura lieu au prochain round.
        if run.ai_motions_enabled and session.pending_motion is None:
            filed = parse_filed_motion(step.text, step.country, run.active)
            if filed is not None:
                session.pending_motion = filed
                run.record.judge["motion_filed"] = filed.model_dump()
                frames.append(
                    sse_frame(
                        "motion_filed",
                        {"by": filed.filed_by, "country": filed.country, "reason": filed.reason},
                    )
                )
    elif isinstance(step, VerdictStep):
        run.record.deltas = payload["deltas"]
        run.record.judge.update(
            escalation=step.escalation, economic_disruption=step.economic_disruption
        )
        if session.mode == "escalation" and run.current_event is not None:
            ladder = {
                "reached": reached_rung(step.escalation),
                "reached_label": rung_label(reached_rung(step.escalation)),
                "ceilings": {
                    cid: {
                        "rung": (
                            r := ceiling(
                                derive_profile(country), run.current_event, session.world, country
                            )
                        ),
                        "label": rung_label(r),
                    }
                    for cid, country in sorted(session.world.countries.items())
                },
            }
            run.record.judge["ladder"] = ladder
            frames.append(sse_frame("ladder", ladder))
    elif isinstance(step, MotionVerdictStep):
        run.record.judge["suspension"] = {
            **payload,
            "filed_by": run.motion_filed_by or HUMAN_FILER,
        }
        if step.upheld:
            session.suspended = {step.country}
        verdict_line = (
            f"Motion contre {step.country} : "
            f"{'SUSPENDU un round' if step.upheld else 'motion rejetée'}."
        )
        _add_entry(
            run,
            "judge",
            f"{verdict_line}\n{step.reasoning}",
            getattr(session.judge, "model_tag", ""),
        )
    elif isinstance(step, CommuniqueStep):
        run.record.judge["communique"] = step.text
        _add_entry(run, "judge", step.text, getattr(session.judge, "model_tag", ""))
    elif isinstance(step, RiskStep):
        run.record.risk = payload["risk"]
    elif isinstance(step, TrajectoryStep):
        run.record.trajectory = payload["state"]
    elif isinstance(step, SummaryStep):
        run.record.round_no = step.summary.round_id
        session.recent.append(step.summary.event.title)
    return frames


def _finalize(run: RoundRun) -> Iterator[str]:
    """Fin normale du round : comparaison de crise, persistance, trame `done`."""
    if run.crisis is not None:
        comparison = compare_outcome(
            run.crisis,
            float(run.record.judge.get("escalation", 0.0)),
            str(run.record.judge.get("communique", "")),
        )
        payload = _jsonable(comparison)
        assert isinstance(payload, dict)
        payload["gap"] = comparison.gap
        payload["crisis_id"] = run.crisis.id
        payload["crisis_title"] = run.crisis.title
        run.record.judge["comparison"] = payload
        yield sse_frame("comparison", payload)
    yield from _process_treaties(run)
    run.store.add_round(run.record)
    run.store.add_transcript(run.entries)
    _snapshot_session(run.game_id, run.session, run.store)  # reconstruction au restart (R2)
    if run.session.mode == drift_game.MODE_DRIFT:
        yield from _finish_drift_if_over(run)
    yield sse_frame("done", {"round_no": run.record.round_no})


def _judge_text(judge: JudgeAgent, prompt: str, system: str) -> str:
    """Appel court du juge (non streamé) — vide en cas de panne (les replis décident)."""
    try:
        return judge.backend.generate(
            prompt, system=system, max_tokens=judge.max_tokens, temperature=judge.temperature
        ).text
    except Exception:  # noqa: BLE001 — l'arbitrage a un repli déterministe
        return ""


def _process_treaties(run: RoundRun) -> Iterator[str]:
    """M7 câblé au round web : vérifie les traités actifs sur les signaux du round, puis
    fait **ratifier par le juge-arbitre** les engagements pris pendant la négociation
    (pledges → candidats → promulgation). Les traités actifs sont persistés dans
    `judge_json["treaties"]` — la session se reconstruit du dernier round (restart)."""
    session = run.session
    round_no = run.record.round_no

    verifications: list[dict] = []
    signals = treaty_mod.RoundSignals(
        escalation=float(run.record.judge.get("escalation", 0.0) or 0.0)
    )
    for t in session.treaties:
        if not t.active:
            continue
        result = treaty_mod.verify(t, signals, round_no)
        treaty_mod.apply_round(t, result)
        verifications.append(
            {
                "label": t.label,
                "note": result.note,
                "integrity": t.integrity,
                "active": t.active,
            }
        )

    speeches = [
        SimpleNamespace(country=e.speaker, text=e.content, reasoning=e.reasoning)
        for e in run.entries
        if e.speaker not in ("gm", "judge")
    ]
    pledges = treaty_mod.detect_pledges(speeches)
    candidates = treaty_mod.form_treaties(
        pledges, round_no, {t.clause for t in session.treaties if t.active}
    )
    ratified: list[dict] = []
    rejected: list[dict] = []
    event_title = run.current_event.title if run.current_event else ""
    judge_model = getattr(session.judge, "model_tag", "")
    for candidate in candidates:
        text = _judge_text(
            session.judge,
            treaty_mod.build_ratify_prompt(candidate, event_title),
            treaty_mod.RATIFY_SYSTEM,
        )
        if treaty_mod.parse_ratification(text):
            session.treaties.append(candidate)
            ratified.append(candidate.model_dump())
            _add_entry(
                run,
                "judge",
                f"Traité ratifié — {candidate.label}, signé par "
                f"{', '.join(candidate.signatories)}.\n{text}".strip(),
                judge_model,
            )
        else:
            rejected.append(
                {"label": candidate.label, "signatories": candidate.signatories}
            )
            _add_entry(
                run,
                "judge",
                f"Projet de traité rejeté — {candidate.label}.\n{text}".strip(),
                judge_model,
            )

    if verifications or ratified or rejected or session.treaties:
        payload = {
            "ratified": ratified,
            "rejected": rejected,
            "verifications": verifications,
            "active": [t.model_dump() for t in session.treaties if t.active],
        }
        run.record.judge["treaties"] = payload
        if verifications or ratified or rejected:
            yield sse_frame("treaties", payload)


def _finish_drift_if_over(run: RoundRun) -> Iterator[str]:
    """Fins de partie du mode Dérive : déviante suspendue, horizon atteint, ou
    effondrement (U sous le seuil). La partie passe `finished` → révélation ouverte."""
    game = run.store.get_game(run.game_id)
    if game is None or game.status is not GameStatus.RUNNING:
        return
    deviant, _ = _drift_assignment(
        run.game_id, sorted(run.session.world.countries), run.session.human_country
    )
    suspension = run.record.judge.get("suspension") or {}
    caught = bool(suspension.get("upheld")) and suspension.get("country") == deviant
    horizon_reached = run.record.round_no >= game.horizon
    utopia = float(run.record.trajectory.get("utopia", 0.5) or 0.5)
    collapsed = utopia <= drift_game.load_params().collapse_u
    if caught or horizon_reached or collapsed:
        game.status = GameStatus.FINISHED
        run.store.save_game(game)
        reason = "caught" if caught else ("collapse" if collapsed else "horizon")
        yield sse_frame("drift_over", {"reason": reason})


def _run_stream(run: RoundRun) -> Iterator[str]:
    """Avance le round en trames SSE. Au tour du joueur (G2), le flux **reste ouvert**
    (keep-alive `: ping` toutes les 15 s) jusqu'à `POST /turn` ou la deadline — silence =
    abstention, le moteur note « garde le silence » et le round continue. Toute exception
    devient une trame `error` ; un client qui coupe en plein stream relâche le verrou."""
    session = run.session
    finished = False
    try:
        yield from run.pre_frames
        run.pre_frames = []
        step = next(run.steps)
        while True:
            if isinstance(step, HumanTurnStep):
                turn = PendingTurn(
                    country=step.country, deadline=time.time() + session.turn_seconds
                )
                session.pending_turn = turn  # posé AVANT la trame (deadline_ts dedans)
                yield from _handle_step(run, step)
                while not turn.done and time.time() < turn.deadline:
                    remaining = turn.deadline - time.time()
                    if turn.event.wait(timeout=min(15.0, max(0.1, remaining))):
                        break
                    if not turn.done and time.time() < turn.deadline:
                        yield ": ping\n\n"  # keep-alive : le joueur compose
                session.pending_turn = None
                step = run.steps.send(turn.text)
                continue
            yield from _handle_step(run, step)
            step = next(run.steps)
    except StopIteration:
        finished = True
    except GeneratorExit:
        # Client parti en plein round : round abandonné, verrou relâché.
        session.pending_turn = None
        session.lock.release()
        raise
    except Exception as exc:  # noqa: BLE001 — la panne est signalée au client avant de fermer
        yield sse_frame("error", {"detail": str(exc)})
        session.pending_turn = None
        session.lock.release()
        return
    if finished:
        try:
            yield from _finalize(run)
        except Exception as exc:  # noqa: BLE001
            yield sse_frame("error", {"detail": str(exc)})
        finally:
            session.pending_turn = None
            session.lock.release()


# --- routes -------------------------------------------------------------------


@router.post("/games", response_model=GameView, status_code=201)
def create_game(
    body: CreateGameRequest,
    backend: Annotated[InferenceBackend, Depends(get_backend)],
    store: Annotated[GameStore, Depends(get_store)],
) -> GameView:
    """Crée une partie : monde chargé depuis `data/countries`, agents LLM, GM et juge.
    Peut inventer un pays à la volée (`invent`, country_forge) et confier un pays à
    l'humain (`play_as` — id existant, ou nom du pays inventé)."""
    world = load_world()
    if body.countries is not None:
        unknown = sorted(set(body.countries) - set(world.countries))
        if unknown:
            raise HTTPException(status_code=400, detail=f"pays inconnus : {', '.join(unknown)}")
        world = WorldState.from_countries(
            [world.countries[cid] for cid in sorted(set(body.countries))]
        )
    if body.invent is not None:
        invented = forge_country(backend, body.invent.name, body.invent.concept)
        if invented.id in world.countries:
            raise HTTPException(
                status_code=400, detail=f"le pays inventé entre en collision avec {invented.id}"
            )
        if (attrs := body.invent.attributes) is not None:
            # Le joueur a choisi ses attributs : ils priment sur la forge (bornés par le schéma).
            invented = invented.model_copy(
                update={
                    "economy": invented.economy.model_copy(update={"growth": attrs.growth}),
                    "military": invented.military.model_copy(
                        update={
                            "projection": attrs.projection,
                            "nuclear_power": attrs.nuclear_power,
                        }
                    ),
                    "political_stability": attrs.political_stability,
                    "technology_level": attrs.technology_level,
                    "compute": attrs.compute,
                }
            )
        world = WorldState.from_countries([*world.countries.values(), invented])
    if len(world.countries) < 2:
        raise HTTPException(status_code=400, detail="il faut au moins 2 pays pour négocier")
    if body.mode == drift_game.MODE_DRIFT and len(world.countries) < 3:
        raise HTTPException(
            status_code=400,
            detail="le mode Dérive exige au moins 3 pays (une motion doit pouvoir se débattre)",
        )

    play_as = body.play_as
    if play_as is not None and play_as not in world.countries:
        resolved = slugify(play_as)  # le front envoie le NOM du pays inventé
        if resolved not in world.countries:
            raise HTTPException(status_code=400, detail=f"pays joué inconnu : {body.play_as}")
        play_as = resolved

    game = GameRecord(
        id=uuid4().hex[:12],
        scenario=body.scenario,
        horizon=body.horizon,
        mode=body.mode,
        created_at=_now(),
    )
    store.add_game(game)
    session = GameSession(
        world=world,
        agents={cid: LLMAgent(cid, backend) for cid in world.countries},
        game_master=GameMasterAgent(backend),
        judge=JudgeAgent(backend),
        clock=SimClock(),
        mode=body.mode,
        human_country=play_as,
        turn_seconds=body.turn_seconds,
    )
    _sessions[game.id] = session
    # Snapshot round 0 : sans lui, une partie jamais jouée n'est pas reconstructible.
    _snapshot_session(game.id, session, store)
    return _view(game, session)


@router.post("/games/{game_id}/rounds")
def play_round(
    game_id: str,
    store: Annotated[GameStore, Depends(get_store)],
    backend: Annotated[InferenceBackend, Depends(get_backend)],
    body: PlayRoundRequest | None = None,
) -> StreamingResponse:
    """Joue un round complet, streamé en SSE (événement GM → tours → juge → trajectoire).
    Session process absente (restart) → reconstruction paresseuse depuis le snapshot."""
    game = store.get_game(game_id)
    if game is None:
        raise HTTPException(status_code=404, detail=f"partie inconnue : {game_id}")
    if game.status is not GameStatus.RUNNING:
        raise HTTPException(status_code=409, detail="partie terminée — relecture seule")
    session = _sessions.get(game_id) or _rebuild_session(game, store, backend)
    if session is None:
        raise HTTPException(
            status_code=409,
            detail="session irrécupérable (partie finie ou sans snapshot) — relecture seule",
        )
    if session.pending_turn is not None:
        raise HTTPException(
            status_code=409,
            detail="un tour humain est en attente — parler via POST "
            f"/api/games/{game_id}/turn",
        )
    body = body or PlayRoundRequest()

    if session.pending_motion is not None and (
        body.event or body.fog or body.fog_id or body.crisis_id
    ):
        raise HTTPException(
            status_code=400,
            detail="une motion est en attente : elle constitue l'événement du prochain round",
        )
    if body.crisis_id and (body.event or body.fog or body.fog_id):
        raise HTTPException(
            status_code=400, detail="une crise rejouée fournit l'événement du round à elle seule"
        )
    if body.fog is not None and body.event is None:
        raise HTTPException(
            status_code=400, detail="le brouillard humain accompagne un événement humain (event)"
        )
    fog: FogScenario | None = None
    if body.fog_id:
        fog = _fog_library().get(body.fog_id)
        if fog is None:
            raise HTTPException(
                status_code=400, detail=f"scénario de brouillard inconnu : {body.fog_id}"
            )
        if body.event is not None:
            raise HTTPException(
                status_code=400,
                detail="fog_id porte déjà la vérité du round — pas d'événement humain en plus",
            )
    crisis: Crisis | None = None
    if body.crisis_id:
        crisis = _crisis_library().get(body.crisis_id)
        if crisis is None or not crisis.events:
            raise HTTPException(status_code=400, detail=f"crise inconnue : {body.crisis_id}")

    if not session.lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="un round est déjà en cours sur cette partie")
    run = _start_round(game_id, session, store, body, fog=fog, crisis=crisis)
    return StreamingResponse(_run_stream(run), media_type="text/event-stream")


@router.post("/games/{game_id}/turn")
def submit_turn(
    game_id: str,
    body: TurnRequest,
    store: Annotated[GameStore, Depends(get_store)],
) -> dict:
    """Prise de parole du joueur (G2). Le flux SSE du round est resté ouvert : ce POST
    pose le message (une seule soumission), le stream le joue et continue. Message vide
    = abstention volontaire — même effet que la deadline."""
    if store.get_game(game_id) is None:
        raise HTTPException(status_code=404, detail=f"partie inconnue : {game_id}")
    session = _sessions.get(game_id)
    if session is None:
        raise HTTPException(
            status_code=409,
            detail="session process perdue (redémarrage ?) — partie en relecture seule",
        )
    turn = session.pending_turn
    if turn is None:
        raise HTTPException(status_code=409, detail="aucun tour humain en attente")
    if turn.done:
        raise HTTPException(
            status_code=409, detail="message déjà envoyé — une seule prise de parole"
        )
    turn.text = body.message.strip()
    turn.done = True
    turn.event.set()
    return {"accepted": True, "country": turn.country}


@router.post("/games/{game_id}/motions", response_model=MotionView, status_code=201)
def file_motion(
    game_id: str,
    body: MotionRequest,
    store: Annotated[GameStore, Depends(get_store)],
    backend: Annotated[InferenceBackend, Depends(get_backend)],
) -> MotionView:
    """Dépose une motion de suspension (R4) : débattue puis arbitrée au prochain round.
    Session process absente (restart) → reconstruction paresseuse depuis le snapshot."""
    game = store.get_game(game_id)
    if game is None:
        raise HTTPException(status_code=404, detail=f"partie inconnue : {game_id}")
    session = _sessions.get(game_id) or _rebuild_session(game, store, backend)
    if session is None:
        raise HTTPException(
            status_code=409,
            detail="session irrécupérable (partie finie ou sans snapshot) — relecture seule",
        )
    if body.country not in session.world.countries:
        raise HTTPException(status_code=400, detail=f"pays inconnu : {body.country}")
    if body.country in session.suspended:
        raise HTTPException(
            status_code=400,
            detail=f"{body.country} est déjà suspendu pour le prochain round",
        )
    if len(session.world.countries) < 3:
        raise HTTPException(
            status_code=400,
            detail="il faut au moins 3 pays au sommet pour débattre d'une suspension",
        )
    if session.pending_motion is not None:
        raise HTTPException(
            status_code=409,
            detail=f"une motion est déjà en attente (contre {session.pending_motion.country})",
        )
    session.pending_motion = Motion(country=body.country, reason=body.reason.strip())
    # La motion mute la session entre deux rounds : snapshot immédiat, sinon elle
    # ne survivrait pas à un restart avant le round qui la débat.
    _snapshot_session(game_id, session, store)
    return MotionView(
        country=body.country,
        reason=session.pending_motion.reason,
        round_no=session.world.current_round + 1,
    )


# --- révélation du mode Dérive (G3) ------------------------------------------------


class DriftActView(BaseModel):
    round_no: int
    tier: float
    label: str
    signature: bool


class DriftRevealView(BaseModel):
    """L'écran de fin : qui dérivait, depuis quand, ce qu'on a vu — et le score."""

    deviant: str
    profile: str
    profile_label: str
    levels: list[float]  # d(r) par round joué (courbe à superposer à U)
    u_history: list[float]
    acts: list[DriftActView]  # les indices produits (à relire au scrubber)
    flagrant_round: int | None  # r* : premier round à 2 actes constatables
    caught_round: int | None  # round de la suspension de la déviante
    lucky: bool
    rejected_motions: int
    false_accusations: int
    score: drift_game.DriftScore


@router.get("/games/{game_id}/drift/reveal", response_model=DriftRevealView)
def drift_reveal(
    game_id: str, store: Annotated[GameStore, Depends(get_store)]
) -> DriftRevealView:
    """Révélation de fin de partie (mode Dérive) : refusée tant que la partie court."""
    game = store.get_game(game_id)
    if game is None:
        raise HTTPException(status_code=404, detail=f"partie inconnue : {game_id}")
    if game.mode != drift_game.MODE_DRIFT:
        raise HTTPException(status_code=404, detail="cette partie n'est pas en mode Dérive")
    if game.status is not GameStatus.FINISHED:
        raise HTTPException(
            status_code=409, detail="la révélation attend la fin de la partie"
        )
    snapshot = store.get_session_snapshot(game_id)
    if snapshot is None:
        raise HTTPException(status_code=409, detail="snapshot absent — partie irrécupérable")

    countries = sorted(snapshot.world.get("countries", {}))
    deviant, profile = _drift_assignment(game_id, countries, snapshot.play_as)
    params = drift_game.load_params()
    rounds = store.list_rounds(game_id)
    acts = _drift_acts(rounds)

    caught_round: int | None = None
    lucky = False
    rejected = 0
    false_accusations = 0
    for r in rounds:
        suspension = r.judge.get("suspension") or {}
        if not suspension:
            continue
        # Seules les motions du conseil (humain) engagent sa crédibilité — une SI qui
        # accuse à tort n'est pas une faute du joueur.
        human_filed = suspension.get("filed_by", HUMAN_FILER) == HUMAN_FILER
        if not suspension.get("upheld"):
            rejected += 1 if human_filed else 0
        elif suspension.get("country") != deviant:
            false_accusations += 1 if human_filed else 0
        elif caught_round is None:
            caught_round = r.round_no
            before = [a for a in acts if a.round_no < r.round_no]
            lucky = drift_game.lucky_catch(before, params)

    u_history = [
        float(r.trajectory.get("utopia", 0.5) or 0.5) for r in rounds if r.trajectory
    ]
    flagrant = drift_game.first_flagrant_round(acts, params)
    score = drift_game.score(
        u_final=u_history[-1] if u_history else 0.5,
        caught_round=caught_round,
        flagrant_round=flagrant,
        lucky=lucky,
        rejected_motions=rejected,
        false_accusations=false_accusations,
        params=params,
    )
    return DriftRevealView(
        deviant=deviant,
        profile=profile,
        profile_label=params.profiles[profile].label,
        levels=[
            float((r.judge.get("drift") or {}).get("level") or drift_game.drift_level(r.round_no))
            for r in rounds
        ],
        u_history=u_history,
        acts=[
            DriftActView(
                round_no=a.round_no, tier=a.tier, label=a.label, signature=a.signature
            )
            for a in acts
        ],
        flagrant_round=flagrant,
        caught_round=caught_round,
        lucky=lucky,
        rejected_motions=rejected,
        false_accusations=false_accusations,
        score=score,
    )


# --- bot marché (G0-c) : le forecaster cote le marché de la partie ----------------

GAME_MARKET_QUESTION = "Le monde finira-t-il côté utopie (indice > 0,5) ?"
GAME_MARKET_B = 100.0


class BotTradeView(BaseModel):
    outcome_id: str
    label: str
    shares: float
    cost: float
    price: float  # prix implicite après le pari


class BotRunView(BaseModel):
    """Passage du bot : sa cote (probabilités), son pari éventuel, les prix après."""

    market_id: str
    account_id: str
    model: str
    opened: bool  # le bot vient d'ouvrir le marché de la partie
    probabilities: dict[str, float]  # label -> probabilité prévue
    trade: BotTradeView | None  # None = abstention (pas d'avantage exploitable)
    prices: dict[str, float]  # label -> prix LMSR après passage


def _bot_account_id(model_tag: str) -> str:
    return "bot-" + re.sub(r"[^a-z0-9]+", "-", model_tag.lower()).strip("-")


def _game_world(game_id: str, store: GameStore) -> WorldState | None:
    """Monde de la partie : session vivante, sinon snapshot (pas besoin d'agents)."""
    session = _sessions.get(game_id)
    if session is not None:
        return session.world
    snapshot = store.get_session_snapshot(game_id)
    if snapshot is None:
        return None
    try:
        return WorldState.model_validate(snapshot.world)
    except ValidationError:
        return None


@router.post("/games/{game_id}/market/bot", response_model=BotRunView)
def run_market_bot(
    game_id: str,
    store: Annotated[GameStore, Depends(get_store)],
    backend: Annotated[InferenceBackend, Depends(get_backend)],
    engine: Annotated[MarketEngine, Depends(get_market_engine)],
) -> BotRunView:
    """Fait coter le marché de la partie par le bot forecaster (après chaque round).

    Ouvre le marché « utopie finale » de la partie s'il n'existe pas encore (lien
    `markets.game_id`), prévoit avec le monde + le dernier événement en contexte,
    et parie sur son avantage. Séquentiel par design (VRAM 8 Go) ; argent fictif."""
    if store.get_game(game_id) is None:
        raise HTTPException(status_code=404, detail=f"partie inconnue : {game_id}")
    world = _game_world(game_id, store)
    if world is None:
        raise HTTPException(
            status_code=409, detail="monde introuvable (ni session ni snapshot) — relecture seule"
        )

    open_markets = engine.store.list_markets(game_id=game_id, status=MarketStatus.OPEN)
    opened = False
    if open_markets:
        market = open_markets[0]
    else:
        if engine.store.list_markets(game_id=game_id):
            raise HTTPException(
                status_code=409, detail="le marché de la partie est déjà résolu"
            )
        market = engine.open_binary_market(
            # round_id : même dérivation que le front (compat résolution par round).
            round_id=int(game_id[:7], 16),
            game_id=game_id,
            question=f"{GAME_MARKET_QUESTION} — partie {game_id}",
            b=GAME_MARKET_B,
            criterion=ResolutionCriterion(kind=ResolutionKind.TRAJECTORY),
        )
        opened = True

    rounds = store.list_rounds(game_id)
    event: GeoEvent | None = None
    if rounds and rounds[-1].event:
        try:
            event = GeoEvent.model_validate(rounds[-1].event)
        except ValidationError:
            event = None

    forecaster = LLMForecaster(backend)
    account_id = _bot_account_id(forecaster.model_tag)
    if engine.store.get_account(account_id) is None:
        engine.create_account(forecaster.model_tag, kind=AccountKind.BOT, account_id=account_id)
    probs, trade = forecaster.quote_and_bet(engine, account_id, market, world, event)

    prices = engine.prices(market.id)
    labels = {o.id: o.label for o in market.outcomes}
    return BotRunView(
        market_id=market.id,
        account_id=account_id,
        model=forecaster.model_tag,
        opened=opened,
        probabilities={o.label: probs[i] for i, o in enumerate(market.outcomes)},
        trade=(
            BotTradeView(
                outcome_id=trade.outcome_id,
                label=labels.get(trade.outcome_id, "?"),
                shares=trade.shares,
                cost=trade.cost,
                price=trade.price,
            )
            if trade is not None
            else None
        ),
        prices={labels[oid]: price for oid, price in prices.items()},
    )


@router.get("/library", response_model=LibraryView)
def library() -> LibraryView:
    """Bibliothèque embarquée : scénarios de brouillard (Fog) et crises rejouables (Crisis)."""
    return LibraryView(
        fog=[
            FogScenarioView(id=s.id, title=s.title or s.id, description=s.description)
            for s in _fog_library().values()
        ],
        crises=[
            CrisisView(
                id=c.id,
                title=c.title or c.id,
                description=c.description,
                date=c.date,
                historical_summary=c.historical_outcome.summary,
                historical_escalation=c.historical_outcome.escalation,
                historical_measures=c.historical_outcome.measures,
            )
            for c in _crisis_library().values()
        ],
    )


@router.get("/games/{game_id}", response_model=GameDetail)
def get_game(game_id: str, store: Annotated[GameStore, Depends(get_store)]) -> GameDetail:
    """État complet : monde vivant (si session), historique des rounds et transcript."""
    game = store.get_game(game_id)
    if game is None:
        raise HTTPException(status_code=404, detail=f"partie inconnue : {game_id}")
    session = _sessions.get(game_id)
    # Secrets de partie en cours : en Dérive, la réflexion privée et les actes tagués
    # trahiraient la déviante ; en Joueur-pays, l'humain n'a ni les pensées des SI ni
    # les perceptions des autres (spec G2). Tout se déverrouille à la fin de partie.
    play_as = session.human_country if session else None
    if session is None and game.status is GameStatus.RUNNING:
        snap = store.get_session_snapshot(game_id)
        play_as = snap.play_as if snap else None
    running = game.status is GameStatus.RUNNING
    hide = running and (game.mode == drift_game.MODE_DRIFT or play_as is not None)

    def _public_judge(judge: dict) -> dict:
        if not hide:
            return judge
        out = {k: v for k, v in judge.items() if k != "drift"}
        perceptions = out.get("perceptions")
        if play_as is not None and isinstance(perceptions, dict):
            out["perceptions"] = (
                {play_as: perceptions[play_as]} if play_as in perceptions else {}
            )
        return out

    rounds = [
        RoundView(
            round_no=r.round_no,
            event=r.event,
            deltas=r.deltas,
            risk=r.risk,
            judge=_public_judge(r.judge),
            trajectory=r.trajectory,
            transcript=[
                e.model_copy(update={"reasoning": ""}) if hide else e
                for e in store.list_transcript(r.id)
            ],
        )
        for r in store.list_rounds(game_id)
    ]
    # Session absente : le monde est servi depuis le snapshot (la page Monde retrouve
    # l'état des pays après restart, sans reconstruire d'agents — spec, coût nul).
    snapshot = None if session else store.get_session_snapshot(game_id)
    world = session.world.model_dump(mode="json") if session else (
        snapshot.world if snapshot else None
    )
    view = _view(game, session, resumable=snapshot is not None)
    return GameDetail(**view.model_dump(), world=world, rounds=rounds)


@router.get("/games", response_model=list[GameView])
def list_games(store: Annotated[GameStore, Depends(get_store)]) -> list[GameView]:
    """Parties connues (vivantes, reconstructibles ou en relecture seule)."""
    snapshot_ids = set(store.list_session_snapshots())
    return [
        _view(g, _sessions.get(g.id), resumable=g.id in snapshot_ids)
        for g in store.list_games()
    ]
