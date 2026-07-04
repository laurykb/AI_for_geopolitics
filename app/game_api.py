"""API de jeu FastAPI — Phase R1 de la refonte (`docs/REFONTE_PLAN.md`).

Trois endpoints pour le front Next.js : créer une partie (`POST /api/games`), jouer un round
streamé en SSE (`POST /api/games/{id}/rounds`) et relire l'état complet (`GET /api/games/{id}`).

Le round réutilise le générateur `run_negotiation_round` (moteur inchangé) : chaque `RoundStep`
devient un événement SSE nommé d'après sa dataclass (`TurnStartStep` → `turn_start`,
`TokenStep` → `token`, …), plus un `done` final — ou une trame `error` si le moteur casse
en plein round. La partie vivante (monde, agents, horloge) reste en mémoire process ; le
durable (partie, rounds, transcript) passe par `GameStore` (SQLite en local, Supabase/Postgres
plus tard — Phase R2).

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
from typing import Annotated
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
from simulation.live_round import (
    CommuniqueStep,
    EventStep,
    MessageDoneStep,
    RiskStep,
    RoundStep,
    SummaryStep,
    TrajectoryStep,
    TurnStartStep,
    VerdictStep,
    run_negotiation_round,
)
from simulation.loader import load_world
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
    recent: list[str] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)


_sessions: dict[str, GameSession] = {}


# --- schémas d'API ------------------------------------------------------------


class CreateGameRequest(BaseModel):
    scenario: str = "red_sea"
    countries: list[str] | None = None  # None -> tous les pays de data/countries
    horizon: int = Field(5, ge=1)


class HumanEventInput(BaseModel):
    """Événement décrété par un Game Master humain (la génération LLM du GM est sautée)."""

    title: str
    description: str = ""
    event_type: str = "human"
    actors: list[str] = Field(default_factory=list)
    severity: float = Field(0.5, ge=0.0, le=1.0)
    uncertainty: float = Field(0.5, ge=0.0, le=1.0)


class PlayRoundRequest(BaseModel):
    max_turns: int | None = Field(None, ge=1)
    event: HumanEventInput | None = None


class GameView(BaseModel):
    id: str
    scenario: str
    horizon: int
    status: str
    created_at: str
    countries: list[str]
    live: bool  # session encore en mémoire (rounds jouables) ou relecture seule


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


def _view(game: GameRecord, session: GameSession | None) -> GameView:
    return GameView(
        id=game.id,
        scenario=game.scenario,
        horizon=game.horizon,
        status=game.status.value,
        created_at=game.created_at,
        countries=sorted(session.world.countries) if session else [],
        live=session is not None,
    )


def _play_round(
    game_id: str, session: GameSession, store: GameStore, body: PlayRoundRequest
) -> Iterator[str]:
    """Joue le round (générateur SSE) puis persiste round + transcript à la fin.

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
        event: GeoEvent | None = None
        if body.event is not None:
            round_id = session.world.current_round + 1
            event = GeoEvent(id=f"human-{round_id}", round_id=round_id, **body.event.model_dump())
        steps = run_negotiation_round(
            session.world,
            session.agents,
            session.game_master,
            session.judge,
            session.clock,
            event=event,
            max_turns=body.max_turns,
            recent=session.recent[-_RECENT_KEPT:],
        )
        for step in steps:
            name, payload = step_event(step)
            yield sse_frame(name, payload)
            if isinstance(step, EventStep):
                record.event = payload["event"]
                gm_model = getattr(session.game_master, "model_tag", "")
                _entry("gm", f"{step.event.title}\n{step.event.description}".strip(), gm_model)
            elif isinstance(step, TurnStartStep):
                models[step.country] = step.model
            elif isinstance(step, MessageDoneStep):
                _entry(step.country, step.text, models.get(step.country, ""), step.reasoning)
            elif isinstance(step, VerdictStep):
                record.deltas = payload["deltas"]
                record.judge.update(
                    escalation=step.escalation, economic_disruption=step.economic_disruption
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
    if not session.lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="un round est déjà en cours sur cette partie")
    stream = _play_round(game_id, session, store, body or PlayRoundRequest())
    return StreamingResponse(stream, media_type="text/event-stream")


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
