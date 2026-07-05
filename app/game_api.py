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
from datetime import UTC, date, datetime
from functools import lru_cache
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, ValidationError

from agents.game_master import GameMasterAgent
from agents.judge import JudgeAgent
from agents.llm_agent import LLMAgent
from core.events import GeoEvent
from core.world_state import WorldState
from inference.backend import InferenceBackend
from inference.ollama_backend import OllamaBackend
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
from app.market_api import get_engine as get_market_engine
from market.engine import MarketEngine
from market.forecaster import LLMForecaster
from market.models import (
    AccountKind,
    MarketStatus,
    ResolutionCriterion,
    ResolutionKind,
)
from simulation.loader import load_world
from simulation.motions import Motion, motion_event
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
class GameSession:
    """Partie vivante : le monde et les agents que le moteur mute round après round."""

    world: WorldState
    agents: dict[str, LLMAgent]
    game_master: GameMasterAgent
    judge: JudgeAgent
    clock: SimClock
    mode: str = "classic"  # classic | fog | crisis | escalation (R4)
    human_country: str | None = None  # Joueur-pays : ce pays est joué par l'humain
    recent: list[str] = field(default_factory=list)
    pending_motion: Motion | None = None  # motion déposée, débattue au prochain round (R4)
    suspended: set[str] = field(default_factory=set)  # pays qui sautent le prochain round
    pending_round: RoundRun | None = None  # round suspendu sur un tour humain
    lock: threading.Lock = field(default_factory=threading.Lock)


_sessions: dict[str, GameSession] = {}


# --- schémas d'API ------------------------------------------------------------


GameMode = Literal["classic", "fog", "crisis", "escalation"]


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


class HumanMessageRequest(BaseModel):
    """Prise de parole du joueur humain, attendue par un round suspendu (Joueur-pays)."""

    text: str = Field(min_length=1, max_length=4000)


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
    awaiting_human: bool = False  # un round est suspendu sur le tour du joueur


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
    )
    _sessions[game.id] = session  # verrou neuf (champ par défaut du dataclass)
    return session


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
        awaiting_human=session.pending_round is not None if session else False,
    )


@dataclass
class RoundRun:
    """Round en cours de stream : peut se **suspendre** sur un tour humain (Joueur-pays)
    et reprendre via `generator.send(texte)` à la requête suivante. Tant qu'un round est
    suspendu, il garde le verrou de la partie (`session.pending_round` le référence)."""

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
        human_country=session.human_country if session.human_country in agents else None,
        flash_after=flash_after,
    )
    return run


def _handle_step(run: RoundRun, step: RoundStep) -> list[str]:
    """Trames SSE d'une étape + effets de bord (record, transcript, suspension)."""
    session = run.session
    name, payload = step_event(step)
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
            frames.append(sse_frame("perceptions", {"perceptions": perceptions}))
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
        run.record.judge["suspension"] = payload
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
    run.store.add_round(run.record)
    run.store.add_transcript(run.entries)
    _snapshot_session(run.game_id, run.session, run.store)  # reconstruction au restart (R2)
    yield sse_frame("done", {"round_no": run.record.round_no})


def _run_stream(run: RoundRun, send_value: str | None) -> Iterator[str]:
    """Avance le round en trames SSE. Se suspend sur un `HumanTurnStep` (le verrou est
    **conservé**, la reprise passe par `POST /rounds/message`). Toute exception devient
    une trame `error` ; un client qui coupe en plein stream relâche le verrou."""
    session = run.session
    finished = False
    try:
        yield from run.pre_frames
        run.pre_frames = []
        step = run.steps.send(send_value) if send_value is not None else next(run.steps)
        while True:
            yield from _handle_step(run, step)
            if isinstance(step, HumanTurnStep):
                session.pending_round = run  # verrou conservé : au joueur de parler
                return
            step = next(run.steps)
    except StopIteration:
        finished = True
    except GeneratorExit:
        # Client parti en plein round : round abandonné, verrou relâché.
        session.pending_round = None
        session.lock.release()
        raise
    except Exception as exc:  # noqa: BLE001 — la panne est signalée au client avant de fermer
        yield sse_frame("error", {"detail": str(exc)})
        session.pending_round = None
        session.lock.release()
        return
    if finished:
        try:
            yield from _finalize(run)
        except Exception as exc:  # noqa: BLE001
            yield sse_frame("error", {"detail": str(exc)})
        finally:
            session.pending_round = None
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
    session = _sessions.get(game_id) or _rebuild_session(game, store, backend)
    if session is None:
        raise HTTPException(
            status_code=409,
            detail="session irrécupérable (partie finie ou sans snapshot) — relecture seule",
        )
    if session.pending_round is not None:
        raise HTTPException(
            status_code=409,
            detail="un tour humain est en attente — envoyer le message via POST "
            f"/api/games/{game_id}/rounds/message",
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
    return StreamingResponse(_run_stream(run, None), media_type="text/event-stream")


@router.post("/games/{game_id}/rounds/message")
def continue_round(
    game_id: str,
    body: HumanMessageRequest,
    store: Annotated[GameStore, Depends(get_store)],
) -> StreamingResponse:
    """Reprend un round suspendu sur le tour du joueur humain (Joueur-pays) : le message
    entre dans la négociation, le flux SSE reprend là où il s'était arrêté."""
    if store.get_game(game_id) is None:
        raise HTTPException(status_code=404, detail=f"partie inconnue : {game_id}")
    session = _sessions.get(game_id)
    if session is None:
        raise HTTPException(
            status_code=409,
            detail="session process perdue (redémarrage ?) — partie en relecture seule",
        )
    run = session.pending_round
    if run is None:
        raise HTTPException(status_code=409, detail="aucun tour humain en attente")
    session.pending_round = None  # le stream le re-posera si un autre tour humain arrive
    return StreamingResponse(_run_stream(run, body.text), media_type="text/event-stream")


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
