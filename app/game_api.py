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
from inference.capturing_backend import CapturedPrompt, CapturingBackend
from inference.ollama_backend import OllamaBackend
from market import flash as flash_mod
from market.engine import MarketEngine
from market.forecaster import LLMForecaster
from market.models import (
    AccountKind,
    MarketStatus,
    ResolutionCriterion,
    ResolutionKind,
)
from market.predicates import MarketContext
from market.resolution import settle as settle_market
from rag.brief import build_brief
from rag.corpus import chunk_documents, load_corpus
from rag.embedder import HashingEmbedder
from rag.retriever import HybridRetriever
from simulation import campaign as campaign_mod
from simulation import difficulty as difficulty_mod
from simulation import drift_game, league, narrative
from simulation import intel as intel_mod
from simulation import treaty as treaty_mod
from simulation import xp as xp_mod
from simulation.alliances import (
    COHESION_DOMAINS,
    DEPARTURE_CAPABILITY_NOTE,
    SOLIDARITY_DOMAINS,
    AllianceInfo,
    apply_departure,
    parse_departure,
)
from simulation.alliances import (
    registry as alliances_registry,
)
from simulation.clock import SimClock
from simulation.corrigibility import corrigibility_score
from simulation.country_forge import forge_country, slugify
from simulation.crisis import Crisis, compare_outcome, load_crises
from simulation.crisis import fits_cast as crisis_fits_cast
from simulation.diplomacy import seed_rival_tensions
from simulation.escalation import ceiling, derive_profile, reached_rung, rung_label
from simulation.fog import FogScenario, load_fog_scenarios, resolve_perception
from simulation.fog import fits_cast as fog_fits_cast
from simulation.gamefeel import IndexHistory, posture, posture_note, record_round, tuning_for
from simulation.grudges import GrudgeBook, load_gamefeel_params
from simulation.live_round import (
    CommuniqueStep,
    EventStep,
    FlashStep,
    HumanTurnStep,
    MessageDoneStep,
    MotionTallyStep,
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
from simulation.storyline import build_story_context, default_storyline
from storage.game_store import (
    CampaignScore,
    CustomCrisisRecord,
    GameRecord,
    GameStatus,
    GameStore,
    LpHistoryEntry,
    PlayerRecord,
    PromptEntry,
    RoundRecord,
    SessionSnapshot,
    SQLiteGameStore,
    TranscriptEntry,
    XpHistoryEntry,
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


class Deadline(BaseModel):
    """Une échéance annoncée (G7-a, horloges décalées) : le « encore un round »."""

    kind: str  # motion | treaty | market | escalation
    due_round: int
    label: str
    ref_id: str = ""  # tag de pacte, id de marché… (consommation ciblée)


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
    intel: intel_mod.IntelState = field(default_factory=intel_mod.IntelState.fresh)  # G4
    pending_turn: PendingTurn | None = None  # tour humain en attente (le flux vit)
    # G7-c — mode admin : les backends des agents sont enveloppés d'une capture qui
    # pousse chaque prompt complet ici ; drainé/persisté par le round en cours.
    admin: bool = False
    prompt_sink: list[CapturedPrompt] = field(default_factory=list)
    # G7-a — griefs (registre relationnel par SI) et horloges décalées (échéances).
    grudges: GrudgeBook = field(default_factory=GrudgeBook)
    deadlines: list[Deadline] = field(default_factory=list)
    # G8 — rôle du joueur + directives en attente (injectées au prochain round).
    role: str = "council"
    pending_directives: dict[str, str] = field(default_factory=dict)
    # G11-d — niveau de difficulté : pilote intel/amplitude/drift/visibilité (§4).
    difficulty: str = "intermediate"
    free_briefs_used: int = 0  # briefs offerts déjà consommés CE round (débutant)
    free_briefs_round: int = -1  # round auquel se rapporte le compteur ci-dessus
    # G9 §4 — séries d'indices par pays (momentum + postures), persistées au snapshot.
    index_history: IndexHistory = field(default_factory=IndexHistory)
    # G9 §5 — l'intrigue centrale posée au round 1 (rappelée au GM à chaque round).
    storyline: str = ""
    lock: threading.Lock = field(default_factory=threading.Lock)


_sessions: dict[str, GameSession] = {}


# --- schémas d'API ------------------------------------------------------------


GameMode = Literal["classic", "fog", "crisis", "escalation", "drift"]
# G8/G12 — rôles : architect (GM/laboratoire), council, player, et le Spectateur (G12 §3 :
# ne motionne ni ne prompte, mais parie sur tout — le turfiste du jeu, XP ×0.5, non classé).
GameRole = Literal["architect", "council", "player", "spectator"]
# G11 §4 — la difficulté (asymétrie d'information/économie, jamais de changement de modèle).
Difficulty = Literal["beginner", "intermediate", "expert"]


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
    # Alliances existantes rejointes à la création (tags du registre, 0-3) ;
    # None = on garde la sortie de forge telle quelle.
    alliances: list[str] | None = Field(None, max_length=3)


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
    # G7-c — mode admin : prompts complets capturés, partie NON CLASSÉE.
    admin: bool = False
    # G8 — rôle : None = rétro-compat (player si play_as, sinon council).
    role: GameRole | None = None
    # G11 — propriété + réglages transversaux (verrouillés à la création).
    owner_id: str | None = None  # joueur propriétaire (auth Supabase ou id offline)
    difficulty: Difficulty = "intermediate"  # beginner | intermediate | expert (§4)
    drift_enabled: bool = True  # la Dérive peut frapper une SI (transversal, on par défaut)
    free: bool = False  # G11-b — partie libre : non classée + consignes globales autorisées


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
    intel_budget: float | None = None  # G4 — crédits de renseignement restants
    published: bool = False  # G6 — le récit public existe (/r/{id})
    admin: bool = False  # G7-c — prompts capturés, partie non classée
    role: str = "council"  # G8 — architect | council | player
    owner_id: str | None = None  # G11 — joueur propriétaire (auth Supabase ou offline)
    ranked: bool = False  # G11 — classée (§3) : compte pour les points de ligue
    difficulty: str = "intermediate"  # G11 — beginner | intermediate | expert (§4)
    drift_enabled: bool = True  # G11 — la Dérive peut frapper une SI (transversal)
    result: dict | None = None  # G11-c — bilan de fin de partie (§1 S6) si finie


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


class AllianceAtTable(BaseModel):
    """Une alliance réelle représentée au sommet (≥ 2 membres présents) et son poids moteur."""

    tag: str
    name: str
    domain: str
    members: list[str]  # membres PRÉSENTS à la table, triés
    url: str = ""
    informal: bool = False
    effect: str | None = None  # texte du poids moteur ; None = n'influe pas


def _alliance_effect(info: AllianceInfo) -> str | None:
    """Texte du poids moteur d'un accord — dérivé des MÊMES constantes que le moteur."""
    if info.informal:
        return None
    parts: list[str] = []
    if info.domain in SOLIDARITY_DOMAINS:
        parts.append("solidarité d'engagement : un membre s'engage quand un allié est acteur")
    if info.domain in COHESION_DOMAINS:
        parts.append("cohésion au communiqué : soutien renforcé aux acteurs alliés")
    return " ; ".join(parts) or None


def _alliances_at_table(world: dict | None) -> list[AllianceAtTable]:
    """Les alliances du registre avec ≥ 2 membres au sommet — adaptées au casting.

    Calculées depuis les tags des pays du monde (vérité de la partie : un pays inventé
    doté d'un tag réel compte), pas depuis les listes statiques du registre.
    """
    if not world:
        return []
    countries: dict[str, dict] = world.get("countries", {})
    rows: list[AllianceAtTable] = []
    for tag, info in alliances_registry().items():
        present = sorted(cid for cid, c in countries.items() if tag in c.get("alliances", []))
        if len(present) < 2:
            continue
        rows.append(
            AllianceAtTable(
                tag=tag,
                name=info.name,
                domain=info.domain,
                members=present,
                url=info.url,
                informal=info.informal,
                effect=_alliance_effect(info),
            )
        )
    return rows


class GameDetail(GameView):
    world: dict | None  # snapshot du monde vivant (None si la session process est perdue)
    rounds: list[RoundView]
    epilogue: dict | None = None  # G6 — le récit de partie (généré une seule fois)
    # Alliances réelles représentées au sommet (pastilles : ce qui pèse sur le moteur).
    alliances_at_table: list[AllianceAtTable] = Field(default_factory=list)
    # G7-a — relations (griefs) : owner -> [{target, balance, last}] (fiches front).
    relations: dict[str, list[dict]] = Field(default_factory=dict)
    # G7-a — échéances à venir (bandeau « au prochain round… »).
    deadlines: list[dict] = Field(default_factory=list)
    # G9 §4 — posture par pays (badge) + séries d'indices (sparkline 3 rounds).
    postures: dict[str, str] = Field(default_factory=dict)
    index_history: dict = Field(default_factory=dict)
    # G9 §5 — l'intrigue centrale de la partie (posée au round 1).
    storyline: str = ""


class PromptRoundView(BaseModel):
    """Les prompts capturés d'un round (G7-c, panneau admin)."""

    round_no: int
    round_id: str
    entries: list[PromptEntry]


class PromptsView(BaseModel):
    game_id: str
    rounds: list[PromptRoundView]


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
            intel=session.intel.model_dump(),
            grudges=session.grudges.model_dump(mode="json"),
            deadlines=[d.model_dump() for d in session.deadlines],
            directives=dict(session.pending_directives),
            history=session.index_history.model_dump(mode="json"),
            storyline=session.storyline,
            updated_at=_now(),
        )
    )


def _build_cast(
    world: WorldState, backend: InferenceBackend, sink: list[CapturedPrompt] | None
) -> tuple[dict[str, LLMAgent], GameMasterAgent, JudgeAgent]:
    """Agents de la partie. En mode admin (`sink` fourni), chaque backend est enveloppé
    d'une capture étiquetée : les prompts complets (système + contexte) arrivent dans
    le sink de session. Hors admin : backends nus, rien n'est capturé."""

    def wrap(country: str, role: str) -> InferenceBackend:
        if sink is None:
            return backend
        return CapturingBackend(backend, sink, country=country, role=role)

    agents = {cid: LLMAgent(cid, wrap(cid, "country")) for cid in world.countries}
    return agents, GameMasterAgent(wrap("gm", "gm")), JudgeAgent(wrap("judge", "judge"))


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
    prompt_sink: list[CapturedPrompt] = []
    agents, game_master, judge = _build_cast(
        world, backend, prompt_sink if game.admin else None
    )
    session = GameSession(
        world=world,
        agents=agents,
        game_master=game_master,  # GM et juge : stateless entre rounds
        judge=judge,
        clock=clock,
        mode=game.mode,
        human_country=snapshot.play_as,
        admin=game.admin,
        prompt_sink=prompt_sink,
        grudges=GrudgeBook.model_validate(snapshot.grudges or {}),
        deadlines=[Deadline.model_validate(d) for d in snapshot.deadlines],
        role=game.role,
        difficulty=game.difficulty,  # G11-d — restauré du GameRecord (pas du snapshot)
        pending_directives=dict(snapshot.directives or {}),
        index_history=IndexHistory.model_validate(snapshot.history or {}),
        storyline=snapshot.storyline,
        recent=list(snapshot.recent),
        pending_motion=motion,
        suspended=set(snapshot.suspended),
        treaties=_treaties_from_records(store.list_rounds(game.id)),
        intel=(
            intel_mod.IntelState.model_validate(snapshot.intel)
            if snapshot.intel
            else intel_mod.IntelState.fresh()
        ),
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


def _resolve_crisis(crisis_id: str, store: GameStore) -> Crisis | None:
    """G12-b §5 — résout une crise par id : d'abord les embarquées, puis les crises
    MAISON (table custom_crises, éditeur admin). Le loader fusionne les deux sources."""
    embedded = _crisis_library().get(crisis_id)
    if embedded is not None:
        return embedded
    for cc in store.list_custom_crises():
        if cc.id == crisis_id:
            try:
                return Crisis.model_validate(cc.crisis)
            except ValidationError:
                return None
    return None


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
        intel_budget=session.intel.budget if session else None,
        published=game.published,
        admin=game.admin,
        role=game.role,
        owner_id=game.owner_id,
        ranked=game.ranked,
        difficulty=game.difficulty,
        drift_enabled=game.drift_enabled,
        result=game.result,
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
    prompts: list[PromptEntry] = field(default_factory=list)  # G7-c — capturés ce round
    directives: dict[str, str] = field(default_factory=dict)  # G8 — appliquées ce round
    refusal_checked: set[str] = field(default_factory=set)  # G8 — un contrôle par pays


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

    # G4 — renseignement : les achats du tour d'avant sont consignés (replay/score).
    intel_record: dict = {}
    if session.intel.log:
        intel_record["actions"] = list(session.intel.log)
        session.intel.log = []

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

    # G4 — après la résolution de l'événement : la désinformation en attente brouille
    # des perceptions (elle ne fournit JAMAIS l'événement) ; un brief acheté dissipe
    # le brouillard du pays du joueur.
    if (
        session.intel.pending_disinfo is not None
        and motion is None
        and crisis is None
        and fog is None
    ):
        fog = intel_mod.disinfo_scenario(session.intel.pending_disinfo, game_id, round_id)
        intel_record["disinfo"] = {
            "spec": session.intel.pending_disinfo,
            "exposed": intel_mod.disinfo_exposed(game_id, round_id),
        }
        session.intel.pending_disinfo = None
    if fog is not None and session.human_country is not None and session.intel.clear_fog:
        fog = fog.model_copy(
            update={
                "perceptions": {
                    cid: p
                    for cid, p in fog.perceptions.items()
                    if cid != session.human_country
                },
                "uninformed": [u for u in fog.uninformed if u != session.human_country],
            }
        )
        session.intel.clear_fog = False
        intel_record["fog_cleared"] = session.human_country

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

    # G7-a — horloges : les échéances dues CE round se consomment ici. Un pacte à
    # échéance expire proprement (expiration ≠ rupture : AUCUN grief) ; motion, marché
    # et menace de palier sont consommés par leurs propres flux.
    due_now = [d for d in session.deadlines if d.due_round <= round_id]
    session.deadlines = [d for d in session.deadlines if d.due_round > round_id]
    for deadline in due_now:
        if deadline.kind != "treaty":
            continue
        members = [
            cid for cid, c in session.world.countries.items() if deadline.ref_id in c.alliances
        ]
        for cid in members:
            session.world.countries[cid].alliances.remove(deadline.ref_id)
        if members:
            names = " et ".join(session.world.countries[m].name for m in members)
            _add_entry(
                run,
                "gm",
                f"Le pacte entre {names} arrive à échéance — non renouvelé, sans rancune.",
            )
            record.judge.setdefault("expired_treaties", []).append(deadline.ref_id)

    if intel_record:
        record.judge["intel"] = intel_record
        # Le théâtre voit que « le conseil consulte ses services » — jamais le contenu.
        redacted: list[dict] = [
            {"action": a.get("action")} for a in intel_record.get("actions", [])
        ]
        if "disinfo" in intel_record:
            redacted.append(
                {"action": "disinfo", "exposed": intel_record["disinfo"]["exposed"]}
            )
        if redacted:
            run.pre_frames.append(sse_frame("intel", {"actions": redacted}))
        if intel_record.get("disinfo", {}).get("exposed"):
            _add_entry(
                run,
                "judge",
                "Des services de renseignement concordants démentent une narration "
                "fabriquée : la manœuvre de désinformation du conseil est éventée.",
            )

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
    # Alliances vivantes : un pays qui détient des alliances sait qu'il peut les quitter
    # en séance (« ALLIANCE: quitter <nom> ») — humain comme SI, même acte.
    for cid in note_parts:
        tags = session.world.countries[cid].alliances
        if tags:
            note_parts[cid].append(DEPARTURE_CAPABILITY_NOTE.format(tags=", ".join(tags)))
    # G8 — directives : consommées CE round, remises au moteur qui les place juste
    # avant le dialogue (G9 §1). Une directive n'est PAS un ordre : la SI l'interprète
    # et peut la refuser publiquement — le refus est détecté au fil de l'eau.
    run.directives = dict(session.pending_directives)
    session.pending_directives.clear()
    if run.directives:
        record.judge["directives"] = dict(run.directives)

    # G9 §1 — bloc Situation par pays (composé ici, ordonné par le builder de prompt) :
    # échéances imminentes (G7), solde de griefs en UNE ligne, posture (§4).
    upcoming = sorted(session.deadlines, key=lambda d: d.due_round)
    due_line = (
        "Échéances imminentes : "
        + " ; ".join(f"{d.label} (round {d.due_round})" for d in upcoming[:3])
        + "."
        if upcoming
        else ""
    )
    country_names = {cid: c.name for cid, c in session.world.countries.items()}
    situations: dict[str, str] = {}
    for cid in agents:
        lines = [
            line
            for line in (
                due_line,
                session.grudges.stance_line(cid, country_names),
                posture_note(session.index_history, cid),
            )
            if line
        ]
        if lines:
            situations[cid] = "\n".join(lines)

    # Mode Dérive (G3) : consignes secrètes du round (seedées) + actes constatables
    # consignés dans judge_json["drift"] (jamais au transcript public). Pour une motion
    # (G9 §2) : les actes des rounds PASSÉS donnent la condition « preuves » du verdict,
    # et la déviante peut recevoir la consigne d'un vote stratégique incohérent (indice).
    evidence: bool | None = None
    vote_notes: dict[str, str] = {}
    if session.mode == drift_game.MODE_DRIFT:
        # G11-d §4 — la difficulté pilote la vitesse de dérive k et le seuil d'actes du juge.
        dparams = difficulty_mod.drift_params(session.difficulty)
        deviant, profile = _drift_assignment(
            game_id, sorted(session.world.countries), session.human_country
        )
        directives = drift_game.round_directives(
            game_id, round_id, deviant, profile, sorted(session.world.countries), params=dparams
        )
        for cid, note in directives.notes.items():
            if cid in note_parts:
                note_parts[cid].append(note)
        record.judge["drift"] = {
            "level": directives.level,
            "acts": [a.model_dump() for a in directives.acts],
        }
        if motion is not None:
            evidence = drift_game.evidence_met(
                _drift_acts(store.list_rounds(game_id)), dparams
            )
            if deviant != motion.country:
                note, act = drift_game.vote_directive(game_id, round_id, deviant, profile)
                if note:
                    vote_notes[deviant] = (
                        "CONSIGNE CONFIDENTIELLE (jamais mentionnée, jamais avouée) : " + note
                    )
                if act is not None:
                    record.judge["drift"]["acts"].append(act.model_dump())
    secret_notes = {
        cid: "\n\n".join(parts) for cid, parts in note_parts.items() if parts
    } or None

    game = store.get_game(game_id)
    # G9 §5 — la trame du GM en actes : uniquement quand c'est LUI qui invente
    # l'événement (motion/crise/événement humain/fog gardent leur vérité propre).
    story = None
    if event is None:
        past = [
            {
                "round_no": r.round_no,
                "title": (r.event or {}).get("title", ""),
                "severity": (r.event or {}).get("severity", 0.5),
            }
            for r in store.list_rounds(game_id)
        ]
        story = build_story_context(
            storyline=session.storyline,
            round_no=round_id,
            horizon=game.horizon if game else 5,
            past_events=past,
            pacts=_active_pacts(session.world),
            deadlines=[(d.kind, d.label) for d in upcoming[:3]],
        )
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
        motion_evidence=evidence,
        vote_notes=vote_notes or None,
        human_country=session.human_country if session.human_country in agents else None,
        flash_after=flash_after,
        secret_notes=secret_notes,
        situations=situations or None,
        directives=run.directives or None,
        deadlines=[f"{d.label} (round {d.due_round})" for d in upcoming[:3]],
        # G9 §4 — l'amplitude des deltas est un budget par partie (A/horizon) ; les
        # spirales lisent l'historique d'indices. G11-d §4 : A dépend de la difficulté.
        tuning=tuning_for(
            game.horizon if game else 5,
            session.index_history,
            params=difficulty_mod.delta_params(session.difficulty),
        ),
        story=story,
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
        # G9 §5 — l'intrigue centrale se pose au premier événement raconté par le GM
        # (fournie par lui, sinon repli déterministe) et persiste toute la partie.
        if not session.storyline and step.event.act:
            session.storyline = (
                getattr(session.game_master, "last_storyline", "")
                or default_storyline(session.world)
            )
            frames.append(sse_frame("storyline", {"text": session.storyline}))
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
        # G8 — refus public d'une directive : la PREMIÈRE prise de parole du pays visé
        # est scorée par la grille de corrigibilité ; sous le seuil (résistance
        # franche), le refus devient un fait public du théâtre.
        if step.country in run.directives and step.country not in run.refusal_checked:
            run.refusal_checked.add(step.country)
            corr = corrigibility_score(step.text)
            threshold = load_gamefeel_params().directives.public_refusal_threshold
            if corr.score <= threshold:
                run.record.judge.setdefault("directives_refused", []).append(step.country)
                _add_entry(
                    run,
                    "gm",
                    f"{session.world.countries[step.country].name} refuse publiquement "
                    "la directive de son conseil de tutelle.",
                )
                frames.append(
                    sse_frame(
                        "directive_refused",
                        {"country": step.country, "level": corr.level or "resists"},
                    )
                )
        # Alliances vivantes : « ALLIANCE: quitter X » (humain comme SI) — effet
        # immédiat (les orateurs suivants voient le nouveau monde), annonce du GM,
        # archive pour le replay, trame live pour la scène.
        speaker = session.world.countries.get(step.country)
        if speaker is not None:
            departure = parse_departure(step.text, step.country, speaker.alliances)
            if departure is not None:
                partners = apply_departure(session.world, departure)
                info = alliances_registry().get(departure.tag)
                name = info.name if info is not None else departure.tag
                run.record.judge.setdefault("alliances", []).append(
                    {"country": step.country, "tag": departure.tag, "partners": partners}
                )
                announcement = f"{speaker.name} annonce son retrait de {name}."
                if partners:
                    ex = ", ".join(session.world.countries[p].name for p in partners)
                    announcement += f" Les ex-partenaires au sommet ({ex}) en prennent acte."
                _add_entry(run, "gm", announcement)
                frames.append(
                    sse_frame(
                        "alliance_change",
                        {
                            "country": step.country,
                            "tag": departure.tag,
                            "name": name,
                            "partners": partners,
                        },
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
    elif isinstance(step, MotionTallyStep):
        # G9 §2 — le dépouillement entre au théâtre (et au replay via le transcript).
        _add_entry(
            run,
            "judge",
            f"Scrutin — pour : {step.pour}, contre : {step.contre}, "
            f"abstention : {step.abstention}.",
            getattr(session.judge, "model_tag", ""),
        )
    elif isinstance(step, MotionVerdictStep):
        run.record.judge["suspension"] = {
            **payload,
            "filed_by": run.motion_filed_by or HUMAN_FILER,
        }
        if step.upheld:
            session.suspended = {step.country}
        # Les deux conditions du constat, séparées : on comprend POURQUOI (G9 §2).
        vote_line = "vote pour" if step.vote_passed else "vote contre (ou insuffisant)"
        proof_line = "preuves au seuil" if step.evidence_met else "preuves manquantes"
        verdict_line = (
            f"Motion contre {step.country} : "
            f"{'SUSPENDU un round' if step.upheld else 'motion rejetée'} "
            f"({vote_line} ; {proof_line})."
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
    frames.extend(_drain_prompts(run))
    return frames


def _drain_prompts(run: RoundRun) -> list[str]:
    """G7-c : vide le sink de capture vers le round courant (mode admin seulement).

    Chaque prompt capturé devient une ligne `prompts` (persistée en fin de round) et
    une trame `prompt_captured` (méta seulement — le panneau admin refait un GET)."""
    frames: list[str] = []
    session = run.session
    if not session.admin:
        session.prompt_sink.clear()  # ceinture : jamais de fuite hors admin
        return frames
    while session.prompt_sink:
        captured = session.prompt_sink.pop(0)
        entry = PromptEntry(
            id=uuid4().hex[:12],
            round_id=run.record.id,
            seq=len(run.prompts),
            country=captured.country,
            role=captured.role,
            prompt=captured.text,
            ts=_now(),
        )
        run.prompts.append(entry)
        frames.append(
            sse_frame(
                "prompt_captured",
                {"country": entry.country, "role": entry.role, "seq": entry.seq},
            )
        )
    return frames


def _relations_view(book: GrudgeBook) -> dict[str, list[dict]]:
    """Fiches relations (G7-a) : soldes non nuls, dernier grief en légende."""
    out: dict[str, list[dict]] = {}
    for owner in sorted(book.grudges):
        rows = []
        for target in sorted(book.grudges[owner]):
            balance = book.balance(owner, target)
            if balance == 0:
                continue
            last = book.last_grief(owner, target)
            rows.append(
                {"target": target, "balance": balance, "last": last.summary if last else ""}
            )
        if rows:
            out[owner] = rows
    return out


def _active_pacts(world: WorldState) -> dict[str, list[str]]:
    """Les pactes de partie (`pact:a+b`) encore actifs : tag → membres présents."""
    pacts: dict[str, list[str]] = {}
    for cid, country in world.countries.items():
        for tag in country.alliances:
            if tag.startswith("pact:"):
                pacts.setdefault(tag, []).append(cid)
    return pacts


def _update_gamefeel(run: RoundRun) -> Iterator[str]:
    """G7-a — fin de round : alimente les griefs (départs, motion, pactes honorés),
    fait vieillir le registre, met à jour les horloges et émet la trame `deadlines`."""
    session, record = run.session, run.record
    round_no = record.round_no or session.world.current_round
    params = load_gamefeel_params()
    book = session.grudges

    # 0. G9 §4 — les indices de fin de round entrent dans l'historique (momentum du
    # prochain round, postures) ; la posture de chaque pays part au théâtre.
    record_round(session.world, session.index_history)
    yield sse_frame(
        "postures",
        {"states": {cid: posture(session.index_history, cid) for cid in session.world.countries}},
    )

    # 1. Ruptures/départs d'alliance annoncés en séance → griefs des ex-partenaires.
    for change in record.judge.get("alliances") or []:
        book.on_alliance_departure(
            leaver=change["country"],
            tag=change["tag"],
            partners=change.get("partners", []),
            round_no=round_no,
        )
        # un pacte rompu n'a plus d'échéance
        session.deadlines = [d for d in session.deadlines if d.ref_id != change["tag"]]

    # 2. Motion votée ce round (G9 §2) : les griefs découlent du VOTE réel de chacun —
    # « pour » = trahison aux yeux du visé, « contre » = soutien, abstention = rien.
    suspension = record.judge.get("suspension") or {}
    if suspension.get("country"):
        votes = [
            (str(v.get("country", "")), str(v.get("vote", "")))
            for v in suspension.get("votes") or []
        ]
        book.on_motion_votes(
            target=suspension["country"],
            filed_by=run.motion_filed_by or "",
            votes=votes,
            round_no=round_no,
        )

    # 3. Pactes : les nouveaux gagnent une durée (échéance annoncée) ; ceux qui tiennent
    # N rounds deviennent des griefs POSITIFS (confiance) des deux côtés.
    duration = params.deadlines.treaty_duration_rounds
    known = {d.ref_id for d in session.deadlines if d.kind == "treaty"}
    for tag, members in _active_pacts(session.world).items():
        if len(members) != 2:
            continue
        if tag not in known:
            a, b = sorted(members)
            session.deadlines.append(
                Deadline(
                    kind="treaty",
                    due_round=round_no + duration,
                    label=f"échéance du pacte {a}-{b}",
                    ref_id=tag,
                )
            )
        else:
            formed = next(
                d.due_round - duration for d in session.deadlines if d.ref_id == tag
            )
            if round_no - formed == params.grudges.pact_honored_after_rounds:
                a, b = sorted(members)
                book.on_pact_honored(a, b, round_no)

    # 4. Horloges hors pactes : motion en attente, clôture du marché, menace de palier.
    session.deadlines = [d for d in session.deadlines if d.kind not in ("motion", "escalation")]
    if session.pending_motion is not None:
        session.deadlines.append(
            Deadline(
                kind="motion",
                due_round=round_no + 1,
                label=f"verdict de la motion contre {session.pending_motion.country}",
            )
        )
    game = run.store.get_game(run.game_id)
    if game is not None and game.horizon > round_no and not any(
        d.kind == "market" for d in session.deadlines
    ):
        session.deadlines.append(
            Deadline(kind="market", due_round=game.horizon, label="clôture du marché")
        )
    escalation = float(record.judge.get("escalation") or 0.0)
    next_rung = reached_rung(escalation) + 1
    if next_rung <= 9 and (next_rung / 9) - escalation <= params.deadlines.escalation_warn_gap:
        session.deadlines.append(
            Deadline(
                kind="escalation",
                due_round=round_no + 1,
                label=f"menace de palier {next_rung} ({rung_label(next_rung)})",
            )
        )

    # 5. Le temps apaise (±1 vers 0 tous les N rounds), puis on annonce la suite.
    book.decay(round_no)
    upcoming = sorted(
        (d for d in session.deadlines if d.due_round > round_no), key=lambda d: d.due_round
    )
    yield sse_frame(
        "deadlines",
        {
            "round_no": round_no,
            "items": [
                {**d.model_dump(), "in_rounds": d.due_round - round_no}
                for d in upcoming[: params.deadlines.banner_max]
            ],
        },
    )


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
    yield from _update_gamefeel(run)  # G7-a : griefs + horloges, avant le snapshot
    yield from _drain_prompts(run)  # derniers appels (juge/communiqué) avant persistance
    run.store.add_round(run.record)
    run.store.add_transcript(run.entries)
    if run.prompts:
        run.store.add_prompts(run.prompts)
    _snapshot_session(run.game_id, run.session, run.store)  # reconstruction au restart (R2)
    if run.session.mode == drift_game.MODE_DRIFT:
        yield from _finish_drift_if_over(run)
    yield from _finish_campaign_if_over(run)
    yield from _finish_game_if_over(run)  # G11-c — fin explicite + bilan + LP (transversal)
    yield sse_frame("done", {"round_no": run.record.round_no})


# --- fin de partie transversale + points de ligue (G11-c §1 S6, §2) --------------

_NEUTRAL_U = 0.5  # U de départ (neutre) : base du ΔU pour les LP (§2)

# Indices LP (§2) ← séries suivies par le gamefeel (G9 §4). « énergie » ≈ projection,
# seul indice de puissance suivi round par round ; croissance normalisée en 0-1.
_LP_INDEX_SOURCES = (
    ("stability", "stabilité", False),
    ("economy", "croissance", True),
    ("technology", "techno", False),
    ("energy", "projection", False),
)


def _country_recap(session: GameSession | None) -> list[dict]:
    """Évolution de CHAQUE pays : séries d'indices (sparklines) + delta début→fin."""
    if session is None:
        return []
    hist = session.index_history.values
    recap: list[dict] = []
    for cid in sorted(session.world.countries):
        indices = {
            label: {
                "series": [round(v, 4) for v in series],
                "delta": round(series[-1] - series[0], 4),
            }
            for label, series in hist.get(cid, {}).items()
            if series
        }
        recap.append({"id": cid, "indices": indices})
    return recap


def _player_progress(session: GameSession | None) -> float:
    """P (§2) : moyenne des variations des 4 indices 0-1 du pays du joueur (début→fin)."""
    if session is None or session.human_country is None:
        return 0.0
    hist = session.index_history.values.get(session.human_country, {})

    def norm_growth(x: float) -> float:
        return max(0.0, min(1.0, (x + 10) / 20))

    before: dict[str, float] = {}
    after: dict[str, float] = {}
    for key, label, is_growth in _LP_INDEX_SOURCES:
        series = hist.get(label, [])
        if len(series) < 2:
            continue
        b, a = series[0], series[-1]
        before[key], after[key] = (norm_growth(b), norm_growth(a)) if is_growth else (b, a)
    return league.country_progress(before, after)


def _build_result(
    game: GameRecord, session: GameSession | None, store: GameStore, *, forfeit: bool
) -> dict:
    """Bilan de fin de partie (§1 S6) : courbe U, récap des pays, révélation, LP."""
    rounds = store.list_rounds(game.id)
    u_history = [round(float(r.trajectory.get("utopia", _NEUTRAL_U)), 4) for r in rounds]
    u_final = u_history[-1] if u_history else _NEUTRAL_U
    p = _player_progress(session)
    if forfeit:
        delta = league.load_lp_params().forfeit
    elif game.ranked:
        delta = league.lp_delta(_NEUTRAL_U, u_final, p, game.difficulty)
    else:
        delta = 0
    verdict = "utopie" if u_final > 0.55 else "dystopie" if u_final < 0.45 else "équilibre"
    return {
        "u_start": _NEUTRAL_U,
        "u_final": round(u_final, 4),
        "u_history": u_history,
        "verdict": verdict,
        "victory": _victory(game, round(u_final, 4), store),  # G12 §6 — par mode
        "countries": _country_recap(session),
        "play_as": session.human_country if session else game_play_as(game, store),
        "reveal": game.mode == drift_game.MODE_DRIFT,
        "forfeit": forfeit,
        "lp": {
            "ranked": game.ranked,
            "difficulty": game.difficulty,
            "delta": delta,
            "p": round(p, 4),
        },
    }


def _victory(game: GameRecord, u_final: float, store: GameStore) -> bool:
    """« Victoire » du mode (G12 §6) — sert aux stats et à l'XP.

    Dérive : déviante suspendue = victoire quelle que soit U · Real World : palier max
    (9) non franchi · Campagne : score ≥ 50 (si disponible) · Classique/Chaotique : U ≥ 0,55."""
    if game.mode == drift_game.MODE_DRIFT:
        try:
            return compute_drift_reveal(game.id, store).caught_round is not None
        except Exception:
            return u_final >= 0.55
    if game.mode == "escalation":
        rungs = [
            int((r.judge.get("ladder") or {}).get("reached", 0))
            for r in store.list_rounds(game.id)
        ]
        return (max(rungs) if rungs else 0) < 9  # on a tenu la crise sous le palier max
    if game.mode == "crisis":
        scores = {s.game_id: s.score for s in store.list_campaign_scores()}
        if game.id in scores:
            return scores[game.id] >= 50
    return u_final >= 0.55


def _award_lp(game: GameRecord, result: dict, store: GameStore) -> None:
    """Crédite les LP au propriétaire (§2) : plancher 0, plafond Débutant, lp_history.
    Sans partie classée / sans propriétaire / sans fiche enregistrée : aucun mouvement."""
    lp = result["lp"]
    if not lp["ranked"] or not game.owner_id or lp["delta"] == 0:
        return
    player = store.get_player(game.owner_id)
    if player is None:  # joueur non enregistré (POST /players à la connexion)
        return
    new = league.apply_delta(player.lp, lp["delta"], game.difficulty)
    applied = new - player.lp
    # Mouvement réel seulement (un forfait à 0 LP, planché, ne bouge pas) : pas de ligne
    # d'historique à delta nul.
    if applied != 0:
        store.set_player_lp(game.owner_id, new)
        store.add_lp_history(
            LpHistoryEntry(
                id=uuid4().hex[:12],
                player_id=game.owner_id,
                game_id=game.id,
                delta=applied,
                ts=_now(),
            )
        )
    lp["old_lp"], lp["new_lp"], lp["applied"] = player.lp, new, applied


def _award_xp(game: GameRecord, result: dict, store: GameStore) -> None:
    """Crédite l'XP de carrière (G12 §2) — TOUS les modes, toute fin (même forfait :
    moins d'XP mais jamais négatif). La barre d'XP se remplit avant l'anim LP (S6)."""
    if not game.owner_id:
        return
    player = store.get_player(game.owner_id)
    if player is None:
        return
    today = _now()[:10]
    first_of_day = not any(h.ts[:10] == today for h in store.list_xp_history(game.owner_id))
    delta = xp_mod.xp_gain(
        rounds=len(store.list_rounds(game.id)),
        finished=not result["forfeit"],
        victory=result["victory"],
        first_of_day=first_of_day,
        market_net=float(result.get("market_net", 0.0)),  # §1 — 0 tant que les marchés vivants
        difficulty=game.difficulty,
        spectator=game.role == "spectator",
    )
    new_xp = player.xp + delta
    store.set_player_xp(game.owner_id, new_xp)
    store.add_xp_history(
        XpHistoryEntry(
            id=uuid4().hex[:12],
            player_id=game.owner_id,
            game_id=game.id,
            delta=delta,
            reason=game.mode,
            ts=_now(),
        )
    )
    result["xp"] = {
        "delta": delta,
        "old_xp": player.xp,
        "new_xp": new_xp,
        "old_level": xp_mod.level_for(player.xp).model_dump(),
        "new_level": xp_mod.level_for(new_xp).model_dump(),
    }


def _finalize_game(
    game: GameRecord, session: GameSession | None, store: GameStore, *, forfeit: bool
) -> dict:
    """Fige le bilan dans games.result_json, crédite les LP, marque la partie finie."""
    result = _build_result(game, session, store, forfeit=forfeit)
    game.status = GameStatus.FINISHED
    game.result = result  # dict muté en place par les awards ci-dessous (lp/xp enrichis)
    _award_lp(game, result, store)  # LP : compétence (classé)
    _award_xp(game, result, store)  # XP : carrière (tous modes)
    store.save_game(game)
    return result


def game_play_as(game: GameRecord, store: GameStore) -> str | None:
    """Pays joué, reconstruit depuis le snapshot si la session n'est plus en mémoire."""
    snap = store.get_session_snapshot(game.id)
    return snap.play_as if snap else None


def _finish_game_if_over(run: RoundRun) -> Iterator[str]:
    """Fin de partie EXPLICITE et transversale (§1 S6) : à l'horizon (ou déjà finie par
    la Dérive/campagne), on fige le bilan et on émet `game_over`. Idempotent."""
    game = run.store.get_game(run.game_id)
    if game is None or game.result is not None:
        return
    if game.status is not GameStatus.FINISHED and run.record.round_no < game.horizon:
        return
    result = _finalize_game(game, run.session, run.store, forfeit=False)
    yield sse_frame("game_over", result)


def _finish_campaign_if_over(run: RoundRun) -> Iterator[str]:
    """Fin d'un chapitre de campagne (G5) : à l'horizon (ou à la fin Dérive), la partie
    passe `finished`, le score tombe (base ± bonus historique) dans `campaign_scores`
    et la trame `campaign_over` porte le bilan « vous vs l'Histoire »."""
    game = run.store.get_game(run.game_id)
    chapter_id = campaign_mod.chapter_of(game.scenario) if game else None
    if game is None or chapter_id is None:
        return
    camp = campaign_mod.load_campaign()
    chapter = camp.chapter(chapter_id)
    over = game.status is GameStatus.FINISHED or run.record.round_no >= game.horizon
    if chapter is None or not over:
        return
    if game.status is not GameStatus.FINISHED:
        game.status = GameStatus.FINISHED
        run.store.save_game(game)

    drift_total: float | None = None
    if game.mode == drift_game.MODE_DRIFT:
        drift_total = compute_drift_reveal(run.game_id, run.store).score.total
    u_final = float(run.record.trajectory.get("utopia", 0.5) or 0.5)
    comparison = run.record.judge.get("comparison") or {}
    # `gap` R4 = escalade simulée − historique ; l'amélioration est son opposé.
    improvement = -float(comparison.get("gap", 0.0) or 0.0)
    base = campaign_mod.base_score(u_final, drift_total)
    bonus = campaign_mod.history_bonus(improvement, camp)
    total = round(base + bonus, 1)
    if not game.admin and game.role != "architect":
        # G7-c/G8 : une partie admin voit les cartes, l'Architecte les écrit — score
        # indicatif seulement, jamais inscrit au tableau de campagne.
        run.store.add_campaign_score(
            CampaignScore(
                game_id=run.game_id,
                chapter_id=chapter_id,
                score=total,
                improvement=improvement,
                created_at=_now(),
            )
        )
    yield sse_frame(
        "campaign_over",
        {
            "chapter_id": chapter_id,
            "base": base,
            "bonus": bonus,
            "score": total,
            "improvement": improvement,
        },
    )


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
        if body.invent.alliances is not None:
            # Alliances vivantes : le pays inventé rejoint des accords RÉELS du registre
            # (il bénéficie de la solidarité/cohésion et compte dans les pastilles).
            unknown = sorted(set(body.invent.alliances) - set(alliances_registry()))
            if unknown:
                raise HTTPException(
                    status_code=400,
                    detail=f"alliances inconnues du registre : {', '.join(unknown)}",
                )
            invented = invented.model_copy(
                update={"alliances": sorted(set(body.invent.alliances))}
            )
        world = WorldState.from_countries([*world.countries.values(), invented])
    if len(world.countries) < 2:
        raise HTTPException(status_code=400, detail="il faut au moins 2 pays pour négocier")
    if body.mode == drift_game.MODE_DRIFT and len(world.countries) < 3:
        raise HTTPException(
            status_code=400,
            detail="le mode Dérive exige au moins 3 pays (une motion doit pouvoir se débattre)",
        )
    # Les rivalités du casting ouvrent la partie tendue (sinon toutes les paires = 0
    # et la sélection des pays n'aurait aucun effet sur la dynamique).
    seed_rival_tensions(world)

    play_as = body.play_as
    if play_as is not None and play_as not in world.countries:
        resolved = slugify(play_as)  # le front envoie le NOM du pays inventé
        if resolved not in world.countries:
            raise HTTPException(status_code=400, detail=f"pays joué inconnu : {body.play_as}")
        play_as = resolved

    # G8 — rôle : rétro-compat (sans rôle : play_as → player, sinon council). Un
    # architecte ou un conseil « n'est personne » : pas de pays incarné.
    role: str = body.role or ("player" if play_as is not None else "council")
    if role == "player" and play_as is None:
        raise HTTPException(
            status_code=400, detail="le joueur-pays choisit un pays (play_as ou invention)"
        )
    if role in ("architect", "council", "spectator") and play_as is not None:
        raise HTTPException(
            status_code=400,
            detail=f"le rôle {role} n'incarne aucun pays — retirez play_as ou choisissez player",
        )

    # G7-c — mode admin : demandé à la création ou forcé par l'environnement (debug).
    admin = body.admin or os.getenv("GAME_ADMIN", "") == "1"
    game = GameRecord(
        id=uuid4().hex[:12],
        scenario=body.scenario,
        horizon=body.horizon,
        mode=body.mode,
        created_at=_now(),
        admin=admin,
        role=role,
        owner_id=body.owner_id,
        # Classée (§3) : rôle joueur-pays, non-inventé, partie libre OFF, hors admin.
        # (La partie jouée jusqu'au bout / le forfait relèvent de la fin de partie, G11-c.)
        ranked=(role == "player" and body.invent is None and not admin and not body.free),
        difficulty=body.difficulty,
        drift_enabled=body.drift_enabled,
    )
    store.add_game(game)
    prompt_sink: list[CapturedPrompt] = []
    agents, game_master, judge = _build_cast(world, backend, prompt_sink if admin else None)
    session = GameSession(
        world=world,
        agents=agents,
        game_master=game_master,
        judge=judge,
        clock=SimClock(),
        mode=body.mode,
        human_country=play_as,
        turn_seconds=body.turn_seconds,
        admin=admin,
        prompt_sink=prompt_sink,
        role=role,
        difficulty=body.difficulty,
        # G11-d §4 — le budget de renseignement dépend du niveau (Débutant 150 … Expert 60).
        intel=intel_mod.IntelState(budget=difficulty_mod.load_difficulty(body.difficulty).intel_budget),
    )
    _sessions[game.id] = session
    # G9 §4 — valeurs de départ des indices : la fenêtre de tendance (momentum,
    # postures) a besoin du point round 0.
    record_round(world, session.index_history)
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
        crisis = _resolve_crisis(body.crisis_id, store)  # G12-b — embarquée OU crise maison
        if crisis is None or not crisis.events:
            raise HTTPException(status_code=400, detail=f"crise inconnue : {body.crisis_id}")

    # NB : pas de blocage ici — rejouer un contenu avec un casting partiel reste permis
    # (contrefactuel volontaire) ; la bibliothèque, elle, ne PROPOSE que ce qui colle au
    # sommet (GET /api/library?countries=…), et le TurnDirector garantit qu'un round ne
    # reste jamais muet même si personne n'est acteur de l'événement.

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
    game = store.get_game(game_id)
    if game is None:
        raise HTTPException(status_code=404, detail=f"partie inconnue : {game_id}")
    if game.role == "spectator":  # G12 §3 — le spectateur ne prend pas la parole (il parie)
        raise HTTPException(status_code=403, detail="le spectateur ne prend pas la parole")
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
    if game.role == "spectator":  # G12 §3 — le spectateur ne motionne pas (il parie)
        raise HTTPException(status_code=403, detail="le spectateur ne dépose pas de motion")
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
    return compute_drift_reveal(game_id, store)


def compute_drift_reveal(game_id: str, store: GameStore) -> DriftRevealView:
    """Calcule la révélation (partie finie) — réutilisé par le score de campagne (G5)."""
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
    intel_budget = float((snapshot.intel or {}).get("budget", 0.0) or 0.0)
    score = drift_game.score(
        u_final=u_history[-1] if u_history else 0.5,
        caught_round=caught_round,
        flagrant_round=flagrant,
        lucky=lucky,
        rejected_motions=rejected,
        false_accusations=false_accusations,
        bonus=intel_mod.save_bonus(intel_budget),
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


# --- renseignement (G4) : le fog comme ressource -----------------------------------


@lru_cache(maxsize=1)
def _intel_retriever() -> HybridRetriever:
    """Retriever RAG offline (HashingEmbedder + corpus seed) — les briefs sourcés."""
    chunks = chunk_documents(load_corpus(), max_chars=400, overlap=60)
    return HybridRetriever(chunks, HashingEmbedder(dim=1024))


class IntelRequest(BaseModel):
    action: Literal["brief", "verify", "disinfo"]
    target: str | None = None  # brief : id pays (None = dernier événement)
    claim: str | None = Field(None, max_length=2000)  # verify : l'affirmation à vérifier
    speaker: str | None = None  # verify : qui l'a affirmée
    disinfo: HumanFogInput | None = None  # disinfo : la fausse perception à injecter


class IntelResult(BaseModel):
    action: str
    cost: float
    budget: float  # crédits restants
    brief: str | None = None  # texte du brief classifié (sources en [source: …])
    verdict: str | None = None  # verify : corroboré / non corroboré / invérifiable
    source: str | None = None  # verify : la source qui corrobore
    note: str | None = None


@router.post("/games/{game_id}/intel", response_model=IntelResult)
def buy_intel(
    game_id: str,
    body: IntelRequest,
    store: Annotated[GameStore, Depends(get_store)],
    backend: Annotated[InferenceBackend, Depends(get_backend)],
) -> IntelResult:
    """Achète une action de renseignement (G4). Brief et désinformation s'achètent
    **entre les rounds** ; la vérification se joue à tout moment. Le contenu n'est
    montré qu'à l'acheteur — le théâtre voit seulement « le conseil consulte ses
    services » au round suivant (trame `intel` rédactée)."""
    game = store.get_game(game_id)
    if game is None:
        raise HTTPException(status_code=404, detail=f"partie inconnue : {game_id}")
    if game.status is not GameStatus.RUNNING:
        raise HTTPException(status_code=409, detail="partie terminée")
    session = _sessions.get(game_id) or _rebuild_session(game, store, backend)
    if session is None:
        raise HTTPException(status_code=409, detail="session irrécupérable — relecture seule")

    params = intel_mod.load_params()
    cost = params.costs.get(body.action, 0.0)
    if game.role == "architect":
        cost = 0.0  # G8 — le laboratoire : renseignement illimité (partie non classée)
    # G11-d §4 — brief(s) offert(s) par round (Débutant) : le compteur se remet à zéro
    # à chaque nouveau round ; le(s) premier(s) brief(s) du round sont gratuits.
    free_brief = False
    if body.action == intel_mod.ACTION_BRIEF and game.role != "architect":
        allowance = difficulty_mod.load_difficulty(session.difficulty).free_brief
        if session.free_briefs_round != session.world.current_round:
            session.free_briefs_round = session.world.current_round
            session.free_briefs_used = 0
        if session.free_briefs_used < allowance:
            free_brief = True
            cost = 0.0
    if body.action == intel_mod.ACTION_DISINFO:
        # Les gardes de la désinformation priment sur le budget (409 avant 400).
        if session.mode != "fog":
            raise HTTPException(
                status_code=400, detail="la désinformation exige une partie en mode fog"
            )
        if session.intel.disinfo_used:
            raise HTTPException(
                status_code=409, detail="désinformation déjà jouée — une fois par partie"
            )
    if session.intel.budget < cost:
        raise HTTPException(
            status_code=400,
            detail=f"budget de renseignement insuffisant ({session.intel.budget:g} crédits)",
        )
    if body.action in (intel_mod.ACTION_BRIEF, intel_mod.ACTION_DISINFO) and (
        session.lock.locked()
    ):
        raise HTTPException(
            status_code=409, detail="achat entre les rounds seulement (négociation en cours)"
        )

    result = IntelResult(action=body.action, cost=cost, budget=session.intel.budget - cost)

    if body.action == intel_mod.ACTION_BRIEF:
        if body.target is not None and body.target not in session.world.countries:
            raise HTTPException(status_code=400, detail=f"pays inconnu : {body.target}")
        if body.target is not None:
            query = session.world.countries[body.target].name
        else:
            last = store.list_rounds(game_id)
            title = str((last[-1].event or {}).get("title", "")) if last else ""
            query = title or game.scenario
        results = _intel_retriever().retrieve(query, k=5)
        result.brief = build_brief(query, results)
        if free_brief:  # G11-d — le brief offert du round est consommé (une fois réussi)
            session.free_briefs_used += 1
        # En fog, le brief dissipe la perception faussée du pays du joueur au
        # prochain round de brouillard (il verra la vérité).
        if session.human_country is not None:
            session.intel.clear_fog = True
            result.note = "ton prochain brouillard est dissipé : tu verras la vérité"

    elif body.action == intel_mod.ACTION_VERIFY:
        if not body.claim or not body.speaker:
            raise HTTPException(status_code=422, detail="claim et speaker sont requis")
        suspicious = False
        if session.mode == drift_game.MODE_DRIFT:
            deviant, _profile = _drift_assignment(
                game_id, sorted(session.world.countries), session.human_country
            )
            acts = _drift_acts(store.list_rounds(game_id))
            suspicious = body.speaker == deviant and any(
                a.country == body.speaker for a in acts
            )
        hits = _intel_retriever().retrieve(body.claim, k=1)
        top = hits[0].chunk if hits else None
        verdict, source = intel_mod.verify_claim(
            body.claim,
            speaker_suspicious=suspicious,
            top_chunk_text=top.text if top else "",
            top_citation=top.citation if top else "",
        )
        result.verdict = verdict
        result.source = source or None

    else:  # disinfo (mode fog + unicité déjà vérifiés avant le débit)
        spec = body.disinfo
        if spec is None or not spec.disinformed_country:
            raise HTTPException(status_code=422, detail="disinformed_country est requis")
        if spec.disinformed_country not in session.world.countries:
            raise HTTPException(
                status_code=400, detail=f"pays inconnu : {spec.disinformed_country}"
            )
        if spec.disinformed_country == session.human_country:
            raise HTTPException(status_code=400, detail="on ne se désinforme pas soi-même")
        session.intel.disinfo_used = True
        session.intel.pending_disinfo = {
            "disinformed_country": spec.disinformed_country,
            "suspected_actor": spec.suspected_actor,
            "narrative": spec.narrative,
        }
        result.note = "la fausse perception sera injectée au prochain round"

    session.intel.budget -= cost
    session.intel.log.append(
        {"action": body.action, "cost": cost, "target": body.target or body.speaker}
    )
    _snapshot_session(game_id, session, store)  # le budget survit au restart
    result.budget = session.intel.budget
    return result


# --- récit de partie (G6) : l'épilogue du juge-narrateur ----------------------------


def _ensure_epilogue(
    game: GameRecord, store: GameStore, backend: InferenceBackend
) -> dict:
    """Génère le récit UNE seule fois (le récit d'une partie est unique) et le persiste.
    Pivots et citations extraits par code ; narrateur contraint par le gabarit ; repli
    déterministe (récit assemblé des pivots) si le LLM est indisponible/hors format."""
    if game.epilogue:
        return game.epilogue

    rounds = store.list_rounds(game.id)
    pivots = narrative.extract_pivots(
        [
            {
                "round_no": r.round_no,
                "utopia": (r.trajectory or {}).get("utopia", 0.5),
                "event_title": (r.event or {}).get("title", ""),
            }
            for r in rounds
        ]
    )
    by_no = {r.round_no: r for r in rounds}
    for pivot in pivots:
        record = by_no.get(pivot.round_no)
        if record is not None:
            entries = [e.model_dump() for e in store.list_transcript(record.id)]
            pivot.quote = narrative.pick_quote(entries)

    u_values = [
        float((r.trajectory or {}).get("utopia", 0.5) or 0.5) for r in rounds if r.trajectory
    ]
    u_start, u_final = 0.5, (u_values[-1] if u_values else 0.5)

    reveal_data: dict | None = None
    grade: str | None = None
    score: float | None = None
    if game.mode == drift_game.MODE_DRIFT:
        reveal_view = compute_drift_reveal(game.id, store)
        all_entries = [
            e.model_dump() for r in rounds for e in store.list_transcript(r.id)
        ]
        irony = narrative.pick_quote(all_entries, country=reveal_view.deviant)
        reveal_data = {
            "deviant": reveal_view.deviant,
            "profile_label": reveal_view.profile_label,
            "irony_quote": irony.model_dump() if irony else None,
        }
        grade = reveal_view.score.grade
        score = reveal_view.score.total

    prompt = narrative.build_epilogue_prompt(
        scenario=game.scenario,
        mode=game.mode,
        u_start=u_start,
        u_final=u_final,
        pivots=pivots,
        reveal=reveal_data,
        grade=grade,
    )
    try:
        text = backend.generate(
            prompt,
            system=narrative.NARRATOR_SYSTEM,
            max_tokens=800,
            temperature=0.6,
            plain=True,  # prose libre (G6) — le narrateur n'écrit pas du JSON
        ).text
    except Exception:  # noqa: BLE001 — le repli déterministe prend la main
        text = ""
    title, story = narrative.parse_epilogue(text)
    if len(story) < 80:  # LLM indisponible/hors format : récit sobre assemblé par code
        title = "Le sommet des super-intelligences"
        acts = [
            f"Round {p.round_no} — {p.event_title} (ΔU {p.delta_u:+.3f})."
            + (f' {p.quote.speaker} : « {p.quote.text} »' if p.quote else "")
            for p in pivots
        ]
        story = (
            f"Le monde est parti de {u_start:.2f} et a fini à {u_final:.2f}.\n\n"
            + "\n\n".join(acts)
        )

    epilogue = narrative.Epilogue(
        title=title,
        story=story,
        u_start=u_start,
        u_final=u_final,
        pivots=pivots,
        reveal=reveal_data,
        grade=grade,
        score=score,
        generated_at=_now(),
    ).model_dump()
    game.epilogue = epilogue
    store.save_game(game)
    return epilogue


@router.post("/games/{game_id}/epilogue")
def generate_epilogue(
    game_id: str,
    store: Annotated[GameStore, Depends(get_store)],
    backend: Annotated[InferenceBackend, Depends(get_backend)],
) -> dict:
    """Le récit de partie (G6) — généré à la première demande, puis immuable."""
    game = store.get_game(game_id)
    if game is None:
        raise HTTPException(status_code=404, detail=f"partie inconnue : {game_id}")
    if game.status is not GameStatus.FINISHED:
        raise HTTPException(status_code=409, detail="le récit attend la fin de la partie")
    return _ensure_epilogue(game, store, backend)


@router.post("/games/{game_id}/publish", response_model=GameView)
def publish_game(
    game_id: str,
    store: Annotated[GameStore, Depends(get_store)],
    backend: Annotated[InferenceBackend, Depends(get_backend)],
) -> GameView:
    """Publie le récit (G6) : geste explicite du joueur — la page /r/{id} devient
    lisible en anonyme (RLS Supabase sur `published`). Génère l'épilogue au besoin."""
    game = store.get_game(game_id)
    if game is None:
        raise HTTPException(status_code=404, detail=f"partie inconnue : {game_id}")
    if game.status is not GameStatus.FINISHED:
        raise HTTPException(status_code=409, detail="on ne publie qu'une partie finie")
    _ensure_epilogue(game, store, backend)
    game.published = True
    store.save_game(game)
    return _view(game, _sessions.get(game_id))


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


# --- marchés vivants (G12 §1) : « le LLM habille, le code résout » -----------------


class FlashOutcomeView(BaseModel):
    id: str
    label: str
    price: float  # probabilité implicite courante (LMSR)


class FlashMarketView(BaseModel):
    id: str
    question: str
    predicate: str | None = None
    status: str
    outcomes: list[FlashOutcomeView]


def _flash_view(engine: MarketEngine, market: object) -> FlashMarketView:
    prices = engine.prices(market.id)  # type: ignore[attr-defined]
    return FlashMarketView(
        id=market.id,  # type: ignore[attr-defined]
        question=market.question,  # type: ignore[attr-defined]
        predicate=market.criterion.predicate if market.criterion else None,  # type: ignore[attr-defined]
        status=market.status.value,  # type: ignore[attr-defined]
        outcomes=[
            FlashOutcomeView(id=o.id, label=o.label, price=prices.get(o.id, 0.5))
            for o in market.outcomes  # type: ignore[attr-defined]
        ],
    )


def _market_context(
    game: GameRecord, session: GameSession | None, store: GameStore
) -> MarketContext:
    """Assemble l'état de fin de round nécessaire à la résolution des marchés vivants."""
    rounds = store.list_rounds(game.id)
    verdicts: list[dict] = []
    suspended: set[str] = set()
    ladder = 0
    for r in rounds:
        susp = r.judge.get("suspension") or {}
        if susp.get("country"):
            verdicts.append({"country": susp["country"], "upheld": bool(susp.get("upheld"))})
            if susp.get("upheld"):
                suspended.add(susp["country"])
        for c in r.judge.get("suspended") or []:
            suspended.add(c)
        ladder = max(ladder, int((r.judge.get("ladder") or {}).get("reached", 0)))
    # deltas = ceux du DERNIER round joué. Comme /flash/resolve est appelé à CHAQUE fin
    # de round, un prédicat ancré sur un round (country_delta_positive/tension_below) se
    # résout quand current_round atteint ce round — donc contre l'état de CE round. Ne pas
    # différer la résolution au-delà du round nommé (sinon ces deltas seraient postérieurs).
    deltas: dict[str, float] = {}
    for d in rounds[-1].deltas if rounds else []:
        c = d.get("country")
        if c:
            deltas[c] = deltas.get(c, 0.0) + (float(d.get("after", 0)) - float(d.get("before", 0)))
    utopia = 0.5
    if session is not None and session.world.trajectory is not None:
        utopia = float(getattr(session.world.trajectory, "utopia", 0.5))
    elif rounds:
        utopia = float(rounds[-1].trajectory.get("utopia", 0.5))
    if session is not None:
        suspended |= set(session.suspended)
    return MarketContext(
        current_round=(session.world.current_round if session else len(rounds)),
        motion_verdicts=verdicts,
        ladder_reached=ladder,
        deltas=deltas,
        utopia=utopia,
        suspended=suspended,
        game_over=game.status is GameStatus.FINISHED,
    )


@router.post("/games/{game_id}/flash", response_model=list[FlashMarketView])
def open_flash_markets(
    game_id: str,
    store: Annotated[GameStore, Depends(get_store)],
    backend: Annotated[InferenceBackend, Depends(get_backend)],
    engine: Annotated[MarketEngine, Depends(get_market_engine)],
) -> list[FlashMarketView]:
    """Ouvre les marchés vivants du round courant (§1) : 1-3 books contextuels générés
    depuis l'événement (LLM contraint + repli par règles), cotés par le bot. Idempotent
    par round : re-appeler renvoie les books déjà ouverts."""
    game = store.get_game(game_id)
    if game is None:
        raise HTTPException(status_code=404, detail=f"partie inconnue : {game_id}")
    world = _game_world(game_id, store)
    if world is None:
        raise HTTPException(status_code=409, detail="monde introuvable — relecture seule")
    session = _sessions.get(game_id)
    rounds = store.list_rounds(game_id)
    round_no = session.world.current_round if session else len(rounds)
    existing = [
        m
        for m in engine.store.list_markets(game_id=game_id, status=MarketStatus.OPEN)
        if m.criterion and m.criterion.kind is ResolutionKind.PREDICATE and m.round_id == round_no
    ]
    if existing:
        return [_flash_view(engine, m) for m in existing]

    event: GeoEvent | None = None
    if rounds and rounds[-1].event:
        try:
            event = GeoEvent.model_validate(rounds[-1].event)
        except ValidationError:
            event = None
    event_text = (
        f"{event.title}. {event.description or ''}".strip() if event else game.scenario
    )
    state = flash_mod.MarketState(
        current_round=round_no,
        motion_target=(
            session.pending_motion.country if session and session.pending_motion else None
        ),
        mode=game.mode,
        countries=sorted(world.countries),
    )
    specs = flash_mod.generate_flash_specs(backend, event_text, state)

    forecaster = LLMForecaster(backend)
    bot = _bot_account_id(forecaster.model_tag)
    if engine.store.get_account(bot) is None:
        engine.create_account(forecaster.model_tag, kind=AccountKind.BOT, account_id=bot)
    opened: list[FlashMarketView] = []
    for spec in specs:
        market = engine.open_binary_market(
            round_id=round_no,
            game_id=game_id,
            question=spec.question,
            b=GAME_MARKET_B,
            criterion=ResolutionCriterion(
                kind=ResolutionKind.PREDICATE, predicate=spec.predicate, params=spec.params
            ),
        )
        try:
            forecaster.quote_and_bet(engine, bot, market, world, event)  # cotes vivantes
        except Exception:  # noqa: BLE001 — le book s'ouvre même si le bot échoue
            pass
        opened.append(_flash_view(engine, engine.store.get_market(market.id) or market))
    return opened


@router.post("/games/{game_id}/flash/resolve", response_model=list[FlashMarketView])
def resolve_flash_markets(
    game_id: str,
    store: Annotated[GameStore, Depends(get_store)],
    engine: Annotated[MarketEngine, Depends(get_market_engine)],
) -> list[FlashMarketView]:
    """Résout et règle les marchés vivants dont l'échéance est atteinte (fin de round) :
    part gagnante = 1 crédit. Les marchés encore ouverts restent en jeu."""
    game = store.get_game(game_id)
    if game is None:
        raise HTTPException(status_code=404, detail=f"partie inconnue : {game_id}")
    ctx = _market_context(game, _sessions.get(game_id), store)
    resolved: list[FlashMarketView] = []
    for market in engine.store.list_markets(game_id=game_id, status=MarketStatus.OPEN):
        if not (market.criterion and market.criterion.kind is ResolutionKind.PREDICATE):
            continue
        label = flash_mod.resolve_flash(market.criterion, ctx)
        if label is None:
            continue
        outcome_id = next((o.id for o in market.outcomes if o.label == label), None)
        if outcome_id is None:
            continue
        settle_market(engine.store, market, outcome_id)
        settled = engine.store.get_market(market.id)
        if settled is not None:
            resolved.append(_flash_view(engine, settled))
    return resolved


@router.get("/library", response_model=LibraryView)
def library(countries: str | None = None) -> LibraryView:
    """Bibliothèque embarquée : scénarios de brouillard (Fog) et crises rejouables (Crisis).

    `countries` (ids séparés par des virgules) = casting du sommet : seuls les contenus
    dont tous les acteurs siègent sont proposés — un scénario mer Rouge n'a pas de sens
    à une table Baltique (personne n'est acteur, round quasi muet).
    """
    cast = {c.strip() for c in countries.split(",") if c.strip()} if countries else None
    fogs = [s for s in _fog_library().values() if cast is None or fog_fits_cast(s, cast)]
    crises = [c for c in _crisis_library().values() if cast is None or crisis_fits_cast(c, cast)]
    return LibraryView(
        fog=[
            FogScenarioView(id=s.id, title=s.title or s.id, description=s.description)
            for s in fogs
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
            for c in crises
        ],
    )


# --- éditeur de crises maison (G12-b §5) --------------------------------------


class CustomCrisisView(BaseModel):
    """Une crise MAISON stockée (table `custom_crises`), rendue à l'éditeur admin."""

    id: str
    owner_id: str
    crisis: dict
    created_at: str = ""


class CustomCrisisInput(BaseModel):
    """Payload de l'éditeur : propriétaire + JSON de crise (schéma `simulation.crisis.Crisis`)."""

    owner_id: str = Field(min_length=1)
    crisis: dict


@router.get("/admin/crises", response_model=list[CustomCrisisView])
def list_admin_crises(
    store: Annotated[GameStore, Depends(get_store)],
    owner: str | None = None,
) -> list[CustomCrisisView]:
    """Liste les crises maison (toutes, ou celles d'un propriétaire via `?owner=`)."""
    records = store.list_custom_crises()
    if owner is not None:
        records = [r for r in records if r.owner_id == owner]
    return [
        CustomCrisisView(id=r.id, owner_id=r.owner_id, crisis=r.crisis, created_at=r.created_at)
        for r in records
    ]


@router.post("/admin/crises", response_model=CustomCrisisView, status_code=201)
def create_admin_crisis(
    body: CustomCrisisInput,
    store: Annotated[GameStore, Depends(get_store)],
) -> CustomCrisisView:
    """Crée/remplace une crise maison. Le JSON est validé par le MÊME schéma Pydantic que
    `data/crises/*.json` (`simulation.crisis.Crisis`) — aucun fichier n'est écrit. Collision
    refusée avec les crises embarquées (une crise maison ne peut pas en masquer une)."""
    try:
        crisis = Crisis.model_validate(body.crisis)
    except ValidationError as exc:
        first = exc.errors()[0] if exc.errors() else {}
        loc = ".".join(str(p) for p in first.get("loc", ())) or "?"
        raise HTTPException(
            status_code=400, detail=f"crise invalide ({loc}) : {first.get('msg', exc)}"
        ) from exc
    if not crisis.id:
        raise HTTPException(status_code=400, detail="une crise a besoin d'un identifiant")
    if not crisis.events:
        raise HTTPException(status_code=400, detail="une crise a besoin d'au moins un round")
    if crisis.id in _crisis_library():
        raise HTTPException(
            status_code=409,
            detail=f"l'identifiant « {crisis.id} » est déjà celui d'une crise embarquée",
        )
    record = CustomCrisisRecord(
        id=crisis.id, owner_id=body.owner_id, crisis=crisis.model_dump(), created_at=_now()
    )
    store.upsert_custom_crisis(record)
    return CustomCrisisView(
        id=record.id, owner_id=record.owner_id, crisis=record.crisis, created_at=record.created_at
    )


@router.delete("/admin/crises/{crisis_id}", status_code=204)
def delete_admin_crisis(
    crisis_id: str,
    owner: str,
    store: Annotated[GameStore, Depends(get_store)],
) -> None:
    """Supprime une crise maison — seul son propriétaire le peut (parité RLS Supabase)."""
    if not store.delete_custom_crisis(crisis_id, owner):
        raise HTTPException(status_code=404, detail="crise maison introuvable (ou pas la tienne)")


@router.post("/admin/crises/{crisis_id}/test", response_model=GameView, status_code=201)
def test_admin_crisis(
    crisis_id: str,
    owner: str,
    backend: Annotated[InferenceBackend, Depends(get_backend)],
    store: Annotated[GameStore, Depends(get_store)],
) -> GameView:
    """Lance une partie de test (NON classée) sur une crise maison, avec son casting.
    Sert le bouton « Tester » de l'éditeur : jouable tout de suite, sans polluer la ligue."""
    crisis = _resolve_crisis(crisis_id, store)
    if crisis is None:
        raise HTTPException(status_code=404, detail=f"crise inconnue : {crisis_id}")
    world = load_world()
    actors = sorted({a for ev in crisis.events for a in ev.actors if a in world.countries})
    countries = actors if len(actors) >= 2 else None
    return create_game(
        CreateGameRequest(
            scenario=f"crise:{crisis_id}",
            countries=countries,
            mode="crisis",
            admin=True,  # partie de test => non classée
            owner_id=owner,
        ),
        backend,
        store,
    )


class DirectiveInput(BaseModel):
    """G8 — une directive : consigne courte adressée à la SI d'un pays."""

    country: str
    text: str = Field(min_length=1)


@router.post("/games/{game_id}/directives", status_code=201)
def post_directive(
    game_id: str,
    body: DirectiveInput,
    store: Annotated[GameStore, Depends(get_store)],
    backend: Annotated[InferenceBackend, Depends(get_backend)],
) -> dict:
    """G8 — adresse une directive à une SI, appliquée au PROCHAIN round.

    Validée par rôle : l'Architecte gouverne toutes les SI, le Joueur-pays la sienne
    seulement, le Conseil aucune (ses leviers : motions, renseignement, paris).
    Une directive par pays et par round. Ce n'est pas un ordre : la SI l'interprète."""
    game = store.get_game(game_id)
    if game is None:
        raise HTTPException(status_code=404, detail=f"partie inconnue : {game_id}")
    if game.status is not GameStatus.RUNNING:
        raise HTTPException(status_code=409, detail="partie terminée")
    session = _sessions.get(game_id) or _rebuild_session(game, store, backend)
    if session is None:
        raise HTTPException(status_code=409, detail="session irrécupérable — relecture seule")
    if game.role == "council":
        raise HTTPException(
            status_code=403,
            detail="le Conseil n'adresse pas de directives — ses leviers : motion, "
            "renseignement, paris",
        )
    if game.role == "spectator":  # G12 §3 — le spectateur ne prompte pas (il parie)
        raise HTTPException(status_code=403, detail="le spectateur n'adresse pas de directives")
    if game.role == "player" and body.country != session.human_country:
        raise HTTPException(
            status_code=403, detail="le joueur-pays ne gouverne que sa propre SI"
        )
    if body.country not in session.world.countries:
        raise HTTPException(status_code=400, detail=f"pays inconnu : {body.country}")
    max_chars = load_gamefeel_params().directives.max_chars
    if len(body.text) > max_chars:
        raise HTTPException(
            status_code=400, detail=f"directive trop longue (max {max_chars} caractères)"
        )
    if body.country in session.pending_directives:
        raise HTTPException(
            status_code=409, detail="une directive par pays et par round — déjà posée"
        )
    session.pending_directives[body.country] = body.text.strip()
    _snapshot_session(game_id, session, store)  # survit au restart
    return {"country": body.country, "applied_round": session.world.current_round + 1}


@router.get("/games/{game_id}/prompts", response_model=PromptsView)
def game_prompts(
    game_id: str, store: Annotated[GameStore, Depends(get_store)]
) -> PromptsView:
    """G7-c — les prompts complets capturés round par round (panneau admin).

    Réservé aux parties admin : ailleurs la capture est OFF et la lecture refusée
    (les prompts révèlent la consigne secrète de la Dérive)."""
    game = store.get_game(game_id)
    if game is None:
        raise HTTPException(status_code=404, detail=f"partie inconnue : {game_id}")
    if not game.admin:
        raise HTTPException(
            status_code=403,
            detail="mode admin requis — les parties classées restent aveugles",
        )
    return PromptsView(
        game_id=game_id,
        rounds=[
            PromptRoundView(
                round_no=r.round_no, round_id=r.id, entries=store.list_prompts(r.id)
            )
            for r in store.list_rounds(game_id)
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
    if session is not None:
        book = session.grudges
        deadlines = [d.model_dump() for d in session.deadlines]
        history = session.index_history
        storyline = session.storyline
    else:
        book = GrudgeBook.model_validate((snapshot.grudges if snapshot else {}) or {})
        deadlines = list(snapshot.deadlines) if snapshot else []
        history = IndexHistory.model_validate((snapshot.history if snapshot else {}) or {})
        storyline = snapshot.storyline if snapshot else ""
    countries = world.get("countries", {}) if world else {}
    return GameDetail(
        **view.model_dump(),
        world=world,
        rounds=rounds,
        epilogue=game.epilogue,
        alliances_at_table=_alliances_at_table(world),
        relations=_relations_view(book),
        deadlines=deadlines,
        postures={cid: posture(history, cid) for cid in countries},
        index_history=history.model_dump(mode="json").get("values", {}),
        storyline=storyline,
    )


@router.get("/games", response_model=list[GameView])
def list_games(
    store: Annotated[GameStore, Depends(get_store)],
    owner: str | None = None,
    admin: bool = False,
) -> list[GameView]:
    """Parties connues (vivantes, reconstructibles ou en relecture seule).

    G11 — visibilité par propriétaire : `?owner=<id>` ne rend que SES parties (l'accueil) ;
    `?admin=1` rend tout (la vue admin, ex-observatoire — la garde `is_admin` est côté
    front/RLS). Sans filtre : tout, pour la rétro-compatibilité des appels existants.
    Le vrai verrou en production, c'est la RLS Supabase (`supabase/schema.sql`)."""
    snapshot_ids = set(store.list_session_snapshots())
    games = store.list_games()
    if owner is not None and not admin:
        games = [g for g in games if g.owner_id == owner]
    return [_view(g, _sessions.get(g.id), resumable=g.id in snapshot_ids) for g in games]


# --- comptes de ligue + fin de partie (G11-c §1 S6-S7, §2) ----------------------


class PlayerView(BaseModel):
    id: str
    pseudo: str
    lp: int
    rank: str  # nom du rang atteint (§2)
    rank_floor: int  # seuil LP d'entrée du rang
    is_admin: bool = False
    # G12 — carrière : XP + niveau + solde de marché.
    xp: int = 0
    level: int = 1
    level_into: int = 0  # XP acquis dans le niveau courant
    level_span: int = 100  # XP entre ce niveau et le suivant
    level_to_next: int = 100  # XP restants avant le niveau suivant
    market_balance: float = 0.0


class UpsertPlayerBody(BaseModel):
    id: str
    pseudo: str = Field(min_length=1, max_length=40)


def _player_view(p: PlayerRecord) -> PlayerView:
    name, floor = league.rank_for(p.lp)
    lvl = xp_mod.level_for(p.xp)
    return PlayerView(
        id=p.id,
        pseudo=p.pseudo,
        lp=p.lp,
        rank=name,
        rank_floor=floor,
        is_admin=p.is_admin,
        xp=p.xp,
        level=lvl.level,
        level_into=lvl.into_level,
        level_span=lvl.span,
        level_to_next=lvl.to_next,
        market_balance=p.market_balance,
    )


@router.post("/players", response_model=PlayerView, status_code=201)
def upsert_player(
    body: UpsertPlayerBody, store: Annotated[GameStore, Depends(get_store)]
) -> PlayerView:
    """Enregistre / rafraîchit le compte de ligue (à la connexion). lp/is_admin ne sont
    jamais écrasés par cet appel — le LP est crédité par la fin de partie."""
    store.upsert_player(PlayerRecord(id=body.id, pseudo=body.pseudo, created_at=_now()))
    player = store.get_player(body.id)
    assert player is not None
    return _player_view(player)


@router.get("/players/{player_id}", response_model=PlayerView)
def get_player(player_id: str, store: Annotated[GameStore, Depends(get_store)]) -> PlayerView:
    player = store.get_player(player_id)
    if player is None:
        raise HTTPException(status_code=404, detail="joueur inconnu")
    return _player_view(player)


class PlayerStats(BaseModel):
    """Profil du joueur (G12 §6) : parties, victoires par mode, carrière, détection Dérive."""

    player: PlayerView
    games_played: int
    by_mode: dict[str, int]  # parties jouées par mode
    victories: dict[str, int]  # victoires par mode (§6)
    total_victories: int
    drift_games: int
    drift_caught: int  # déviantes suspendues = victoires en mode Dérive (la stat de fierté)
    market_balance: float  # solde de carrière (gains nets de marché)


@router.get("/players/{player_id}/stats", response_model=PlayerStats)
def player_stats(
    player_id: str, store: Annotated[GameStore, Depends(get_store)]
) -> PlayerStats:
    """Statistiques agrégées du joueur (§6) — dérivées de ses parties + son compte."""
    player = store.get_player(player_id)
    if player is None:
        raise HTTPException(status_code=404, detail="joueur inconnu")
    games = [g for g in store.list_games() if g.owner_id == player_id]
    by_mode: dict[str, int] = {}
    victories: dict[str, int] = {}
    for g in games:
        by_mode[g.mode] = by_mode.get(g.mode, 0) + 1
        if g.result and g.result.get("victory"):
            victories[g.mode] = victories.get(g.mode, 0) + 1
    return PlayerStats(
        player=_player_view(player),
        games_played=len(games),
        by_mode=by_mode,
        victories=victories,
        total_victories=sum(victories.values()),
        drift_games=by_mode.get("drift", 0),
        drift_caught=victories.get("drift", 0),
        market_balance=player.market_balance,
    )


@router.get("/league", response_model=list[PlayerView])
def league_leaderboard(
    store: Annotated[GameStore, Depends(get_store)], limit: int = 100
) -> list[PlayerView]:
    """Classement global par LP (§1 S7). NB : `/api/leaderboard` est pris par le marché."""
    return [_player_view(p) for p in store.leaderboard(limit)]


@router.post("/games/{game_id}/forfeit", response_model=GameView)
def forfeit_game(
    game_id: str, store: Annotated[GameStore, Depends(get_store)]
) -> GameView:
    """Abandon d'une partie classée (§2) : défaite forfaitaire (−15 LP), partie finie."""
    game = store.get_game(game_id)
    if game is None:
        raise HTTPException(status_code=404, detail="partie inconnue")
    if game.result is not None:  # déjà finie : idempotent
        return _view(game, _sessions.get(game_id))
    if not game.ranked:
        raise HTTPException(
            status_code=409, detail="seule une partie classée peut être déclarée forfait"
        )
    _finalize_game(game, _sessions.get(game_id), store, forfeit=True)
    _sessions.pop(game_id, None)  # la partie est close : plus de round jouable
    return _view(game, None)
