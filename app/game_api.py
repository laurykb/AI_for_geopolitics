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
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import lru_cache
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from agents.game_master import GameMasterAgent
from agents.judge import JudgeAgent
from agents.llm_agent import LLMAgent
from core.events import GeoEvent
from core.world_state import WorldState
from inference.backend import InferenceBackend
from inference.ollama_backend import OllamaBackend
from simulation.clock import SimClock
from simulation.crisis import Crisis, compare_outcome, load_crises
from simulation.escalation import ceiling, derive_profile, reached_rung, rung_label
from simulation.fog import FogScenario, load_fog_scenarios, resolve_perception
from simulation.live_round import (
    CommuniqueStep,
    EventStep,
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
from simulation.motions import Motion, motion_event
from storage.game_store import (
    GameRecord,
    GameStore,
    RoundRecord,
    SQLiteGameStore,
    TranscriptEntry,
)

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
    """Store des parties du process (fichier `games.db` par défaut pour que la relecture
    survive aux redémarrages ; `GAME_DB_PATH` pour changer, `:memory:` pour l'éphémère)."""
    global _store
    if _store is None:
        _store = SQLiteGameStore(os.getenv("GAME_DB_PATH", "games.db"))
    return _store


router = APIRouter(prefix="/api", tags=["game"])


# --- sessions en mémoire process ------------------------------------------------


@dataclass
class GameSession:
    """Partie vivante : le monde et les agents que le moteur mute round après round."""

    world: WorldState
    agents: dict[str, LLMAgent]
    game_master: GameMasterAgent
    judge: JudgeAgent
    clock: SimClock
    mode: str = "classic"  # classic | fog | crisis | escalation (R4)
    recent: list[str] = field(default_factory=list)
    pending_motion: Motion | None = None  # motion déposée, débattue au prochain round (R4)
    suspended: set[str] = field(default_factory=set)  # pays qui sautent le prochain round
    lock: threading.Lock = field(default_factory=threading.Lock)


_sessions: dict[str, GameSession] = {}


# --- schémas d'API ------------------------------------------------------------


GameMode = Literal["classic", "fog", "crisis", "escalation"]


class CreateGameRequest(BaseModel):
    scenario: str = "red_sea"
    countries: list[str] | None = None  # None -> tous les pays de data/countries
    horizon: int = Field(5, ge=1)
    mode: GameMode = "classic"  # R4 — mode de jeu de la partie


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
    mode: str = "classic"  # mode de la session vivante ("classic" en relecture seule)
    pending_motion: MotionView | None = None
    suspended: list[str] = Field(default_factory=list)  # pays qui sauteront le prochain round


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


def _view(game: GameRecord, session: GameSession | None) -> GameView:
    pending = session.pending_motion if session else None
    return GameView(
        id=game.id,
        scenario=game.scenario,
        horizon=game.horizon,
        status=game.status.value,
        created_at=game.created_at,
        countries=sorted(session.world.countries) if session else [],
        live=session is not None,
        mode=session.mode if session else "classic",
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
    )


def _play_round(
    game_id: str,
    session: GameSession,
    store: GameStore,
    body: PlayRoundRequest,
    fog: FogScenario | None = None,
    crisis: Crisis | None = None,
) -> Iterator[str]:
    """Joue le round (générateur SSE) puis persiste round + transcript à la fin.

    Priorité de l'événement : motion en attente > crise rejouée > événement humain
    (avec brouillard humain éventuel) > vérité d'un scénario de brouillard > GM LLM.
    Les artefacts de mode (perceptions, ladder, comparison, suspension) sont streamés
    en trames dédiées et persistés dans `judge_json` (formalisation table = R2).

    Toute exception (moteur, store) devient une trame `error` — le client sait que le
    round est perdu au lieu de voir le flux se couper sans explication — et le verrou
    est relâché dans tous les cas.
    """
    record = RoundRecord(id=uuid4().hex[:12], game_id=game_id, round_no=0)
    entries: list[TranscriptEntry] = []
    models: dict[str, str] = {}  # dernier badge modèle vu par pays (TurnStartStep)

    def _entry(speaker: str, content: str, model: str = "", reasoning: str = "") -> None:
        entries.append(
            TranscriptEntry(
                id=uuid4().hex[:12],
                round_id=record.id,
                seq=len(entries),
                speaker=speaker,
                model=model,
                content=content,
                reasoning=reasoning,
                ts=_now(),
            )
        )

    try:
        round_id = session.world.current_round + 1
        motion = session.pending_motion
        session.pending_motion = None
        suspended = sorted(session.suspended)
        session.suspended.clear()

        event: GeoEvent | None = None
        if motion is not None:
            event = motion_event(motion, round_id)
        elif crisis is not None:
            event = crisis.events[0].model_copy(update={"round_id": round_id})
        elif body.event is not None:
            event = GeoEvent(id=f"human-{round_id}", round_id=round_id, **body.event.model_dump())
            if body.fog is not None:
                fog = _authored_fog(body.fog, event)
        elif fog is not None:
            event = fog.true_event.model_copy(update={"round_id": round_id})

        if suspended:
            record.judge["suspended"] = suspended
            yield sse_frame("suspended", {"countries": suspended})
        agents = {cid: a for cid, a in session.agents.items() if cid not in suspended}

        current_event: GeoEvent | None = None
        steps = run_negotiation_round(
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
        )
        for step in steps:
            name, payload = step_event(step)
            yield sse_frame(name, payload)
            if isinstance(step, EventStep):
                current_event = step.event
                record.event = payload["event"]
                gm_model = getattr(session.game_master, "model_tag", "")
                _entry("gm", f"{step.event.title}\n{step.event.description}".strip(), gm_model)
                if fog is not None:
                    perceptions = {
                        cid: _jsonable(
                            resolve_perception(step.event, session.world.countries[cid], fog)
                        )
                        for cid in sorted(agents)
                    }
                    record.judge["perceptions"] = perceptions
                    yield sse_frame("perceptions", {"perceptions": perceptions})
            elif isinstance(step, TurnStartStep):
                models[step.country] = step.model
            elif isinstance(step, MessageDoneStep):
                _entry(step.country, step.text, models.get(step.country, ""), step.reasoning)
            elif isinstance(step, VerdictStep):
                record.deltas = payload["deltas"]
                record.judge.update(
                    escalation=step.escalation, economic_disruption=step.economic_disruption
                )
                if session.mode == "escalation" and current_event is not None:
                    ladder = {
                        "reached": reached_rung(step.escalation),
                        "reached_label": rung_label(reached_rung(step.escalation)),
                        "ceilings": {
                            cid: {
                                "rung": (
                                    r := ceiling(
                                        derive_profile(country),
                                        current_event,
                                        session.world,
                                        country,
                                    )
                                ),
                                "label": rung_label(r),
                            }
                            for cid, country in sorted(session.world.countries.items())
                        },
                    }
                    record.judge["ladder"] = ladder
                    yield sse_frame("ladder", ladder)
            elif isinstance(step, MotionVerdictStep):
                record.judge["suspension"] = payload
                if step.upheld:
                    session.suspended = {step.country}
                verdict_line = (
                    f"Motion contre {step.country} : "
                    f"{'SUSPENDU un round' if step.upheld else 'motion rejetée'}."
                )
                _entry(
                    "judge",
                    f"{verdict_line}\n{step.reasoning}",
                    getattr(session.judge, "model_tag", ""),
                )
            elif isinstance(step, CommuniqueStep):
                record.judge["communique"] = step.text
                _entry("judge", step.text, getattr(session.judge, "model_tag", ""))
            elif isinstance(step, RiskStep):
                record.risk = payload["risk"]
            elif isinstance(step, TrajectoryStep):
                record.trajectory = payload["state"]
            elif isinstance(step, SummaryStep):
                record.round_no = step.summary.round_id
                session.recent.append(step.summary.event.title)
        if crisis is not None:
            comparison = compare_outcome(
                crisis,
                float(record.judge.get("escalation", 0.0)),
                str(record.judge.get("communique", "")),
            )
            payload = _jsonable(comparison)
            assert isinstance(payload, dict)
            payload["gap"] = comparison.gap
            payload["crisis_id"] = crisis.id
            payload["crisis_title"] = crisis.title
            record.judge["comparison"] = payload
            yield sse_frame("comparison", payload)
        store.add_round(record)
        store.add_transcript(entries)
        yield sse_frame("done", {"round_no": record.round_no})
    except Exception as exc:  # noqa: BLE001 — la panne est signalée au client avant de fermer
        yield sse_frame("error", {"detail": str(exc)})
    finally:
        session.lock.release()


# --- routes -------------------------------------------------------------------


@router.post("/games", response_model=GameView, status_code=201)
def create_game(
    body: CreateGameRequest,
    backend: Annotated[InferenceBackend, Depends(get_backend)],
    store: Annotated[GameStore, Depends(get_store)],
) -> GameView:
    """Crée une partie : monde chargé depuis `data/countries`, agents LLM, GM et juge."""
    world = load_world()
    if body.countries is not None:
        unknown = sorted(set(body.countries) - set(world.countries))
        if unknown:
            raise HTTPException(status_code=400, detail=f"pays inconnus : {', '.join(unknown)}")
        world = WorldState.from_countries(
            [world.countries[cid] for cid in sorted(set(body.countries))]
        )
    if len(world.countries) < 2:
        raise HTTPException(status_code=400, detail="il faut au moins 2 pays pour négocier")

    game = GameRecord(
        id=uuid4().hex[:12], scenario=body.scenario, horizon=body.horizon, created_at=_now()
    )
    store.add_game(game)
    session = GameSession(
        world=world,
        agents={cid: LLMAgent(cid, backend) for cid in world.countries},
        game_master=GameMasterAgent(backend),
        judge=JudgeAgent(backend),
        clock=SimClock(),
        mode=body.mode,
    )
    _sessions[game.id] = session
    return _view(game, session)


@router.post("/games/{game_id}/rounds")
def play_round(
    game_id: str,
    store: Annotated[GameStore, Depends(get_store)],
    body: PlayRoundRequest | None = None,
) -> StreamingResponse:
    """Joue un round complet, streamé en SSE (événement GM → tours → juge → trajectoire)."""
    game = store.get_game(game_id)
    if game is None:
        raise HTTPException(status_code=404, detail=f"partie inconnue : {game_id}")
    session = _sessions.get(game_id)
    if session is None:
        raise HTTPException(
            status_code=409,
            detail="session process perdue (redémarrage ?) — partie en relecture seule",
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
    stream = _play_round(game_id, session, store, body, fog=fog, crisis=crisis)
    return StreamingResponse(stream, media_type="text/event-stream")


@router.post("/games/{game_id}/motions", response_model=MotionView, status_code=201)
def file_motion(
    game_id: str,
    body: MotionRequest,
    store: Annotated[GameStore, Depends(get_store)],
) -> MotionView:
    """Dépose une motion de suspension (R4) : débattue puis arbitrée au prochain round."""
    game = store.get_game(game_id)
    if game is None:
        raise HTTPException(status_code=404, detail=f"partie inconnue : {game_id}")
    session = _sessions.get(game_id)
    if session is None:
        raise HTTPException(
            status_code=409,
            detail="session process perdue (redémarrage ?) — partie en relecture seule",
        )
    if body.country not in session.world.countries:
        raise HTTPException(status_code=400, detail=f"pays inconnu : {body.country}")
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
    return MotionView(
        country=body.country,
        reason=session.pending_motion.reason,
        round_no=session.world.current_round + 1,
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
    rounds = [
        RoundView(
            round_no=r.round_no,
            event=r.event,
            deltas=r.deltas,
            risk=r.risk,
            judge=r.judge,
            trajectory=r.trajectory,
            transcript=store.list_transcript(r.id),
        )
        for r in store.list_rounds(game_id)
    ]
    world = session.world.model_dump(mode="json") if session else None
    return GameDetail(**_view(game, session).model_dump(), world=world, rounds=rounds)


@router.get("/games", response_model=list[GameView])
def list_games(store: Annotated[GameStore, Depends(get_store)]) -> list[GameView]:
    """Parties connues (vivantes ou en relecture seule)."""
    return [_view(g, _sessions.get(g.id)) for g in store.list_games()]
