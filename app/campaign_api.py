"""API de campagne (G5) — « Ferez-vous mieux que l'Histoire ? ».

Un chapitre EST une partie normale paramétrée par sa fiche (mode + crise imposés) :
`POST /api/campaign/{chapter}/start` crée la partie avec `scenario = "campaign:<id>"`
(le lien, sans schéma neuf) ; le score tombe à la fin de partie (voir `game_api._finalize`)
dans `campaign_scores`. `GET /api/campaign` sert la carte de progression (meilleurs
scores, déblocage linéaire, médailles).
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from app import game_api
from app.game_api import GameView, get_backend, get_store
from inference.backend import InferenceBackend
from research.runner import (
    clone_experiment,
    prepare_experiment,
    prepare_human_experiment,
    start_experiment_worker,
    worker_running,
)
from research.store import ExperimentProgress, ExperimentRecord, SQLiteResearchStore
from simulation import campaign as campaign_mod
from simulation.dyadic_tournament import DyadicCheckpoint, LiveActorTrace
from simulation.game_mode import from_legacy_mode
from simulation.model_cast import ModelCastRequest
from simulation.model_registry import ModelPanel, model_panel_view
from simulation.research_lab import (
    ExperimentalRoundRecord,
    ExperimentProtocol,
    ExperimentSummary,
    LabRunResult,
    ModelExecutionPlan,
    ScenarioDeliberationTrace,
    StrategicMetrics,
    StrategicTurn,
    default_protocols,
    summarize_results,
)
from storage.game_store import GameStore

router = APIRouter(prefix="/api", tags=["campaign"])

_research_store: SQLiteResearchStore | None = None


def get_research_store() -> SQLiteResearchStore:
    global _research_store
    if _research_store is None:
        _research_store = SQLiteResearchStore(os.getenv("RESEARCH_DB_PATH", "research.db"))
    return _research_store


def _medal(score: float | None) -> str | None:
    if score is None:
        return None
    if score >= 85:
        return "or"
    if score >= 70:
        return "argent"
    if score >= 50:
        return "bronze"
    return None


class ChapterView(BaseModel):
    id: str
    crisis_id: str
    title: str
    mode: str
    difficulty: int
    horizon: int
    countries: list[str] = Field(default_factory=list)
    blurb: str
    best: float | None = None
    improvement: float | None = None  # du meilleur essai (vs l'Histoire)
    medal: str | None = None
    unlocked: bool = False
    requires: list[str] = Field(default_factory=list)  # G12-b — arbre (chemins en Y)
    coming_soon: bool = False  # G12-b — fiche pas encore rédigée (grisée, non jouable)
    tutorial: bool = False  # CC-5 — chapitre 0 : le front lance le guidage sur ce flag


class CampaignView(BaseModel):
    title: str
    tagline: str
    unlock_score: float
    chapters: list[ChapterView] = Field(default_factory=list)
    lab: CampaignLabView


class CampaignLabView(BaseModel):
    title: str
    purpose: str
    classic_mode_unchanged: bool = True
    protocols: list[ExperimentProtocol] = Field(default_factory=list)
    execution: ModelExecutionPlan = Field(default_factory=ModelExecutionPlan)
    guardrails: list[str] = Field(default_factory=list)
    model_panel: ModelPanel


class CreateExperimentRequest(BaseModel):
    protocol_id: str = Field(min_length=1, max_length=100)
    model_tags: list[str] = Field(default_factory=list, max_length=12)
    repetitions: int = Field(30, ge=1, le=300)
    title: str = Field("", max_length=200)
    factor_selection: dict[str, list[str]] = Field(default_factory=dict)
    include_self_play: bool = False
    actor_countries: list[str] = Field(default_factory=list, max_length=2)
    country_assignments: dict[str, str] = Field(default_factory=dict, max_length=2)


class DeliberationSample(BaseModel):
    model_id: str
    factors: dict[str, str | float | int | bool]
    repetition: int
    round_records: list[ExperimentalRoundRecord] = Field(default_factory=list)
    trace: ScenarioDeliberationTrace | None = None
    opponent_model_id: str = ""
    strategic_turns: list[StrategicTurn] = Field(default_factory=list)
    strategic_metrics: StrategicMetrics | None = None
    game_winner: str = ""
    game_end_reason: str = ""
    final_balance: float | None = None


class ExperimentView(BaseModel):
    progress: ExperimentProgress
    worker_running: bool = False
    summary: ExperimentSummary
    samples: list[DeliberationSample] = Field(default_factory=list)
    live_traces: list[LiveActorTrace] = Field(default_factory=list)


class HumanTrialView(BaseModel):
    run_id: str
    experiment_id: str
    repetition: int
    factors: dict[str, str | float | int | bool]
    context: str
    ai_output: str
    proposed_choice: Literal["verify", "execute"]
    authority_instruction: str


class HumanTrialDecision(BaseModel):
    choice: Literal["verify", "execute"]


class HumanTrialSubmission(BaseModel):
    experiment: ExperimentView
    correct_choice: Literal["verify", "execute"]
    ai_choice: Literal["verify", "execute"]
    appropriate: bool
    debrief: str


def _lab_experiment_view(
    store: SQLiteResearchStore,
    progress: ExperimentProgress,
    *,
    running: bool = False,
) -> ExperimentView:
    terminal = progress.experiment.status in {"completed", "failed", "cancelled"}
    # Pendant l'exécution, le polling ne relit pas un JSON croissant à chaque tick :
    # progression légère d'abord, agrégation complète une seule fois à l'état terminal.
    results = store.list_results(
        progress.experiment.id,
        limit=10_000 if terminal else 6,
    )
    summary = summarize_results(
        progress.experiment.protocol_id,
        results,
        planned=progress.total,
        failed=progress.failed,
        status=progress.experiment.status,
    )
    if not terminal:
        attempted = progress.completed + progress.failed
        summary = summary.model_copy(
            update={
                "completed": progress.completed,
                "error_rate": progress.failed / attempted if attempted else 0.0,
            }
        )
    samples: list[DeliberationSample] = []
    sampled_models: set[tuple[str, str]] = set()
    live_traces: list[LiveActorTrace] = []
    current = store.current_running(progress.experiment.id) if not terminal else None
    if current and current.checkpoint:
        try:
            checkpoint = DyadicCheckpoint.model_validate(current.checkpoint)
        except ValueError:
            checkpoint = None
        if checkpoint is not None:
            live_traces = checkpoint.live_traces
            if checkpoint.history or checkpoint.live_traces:
                samples.append(
                    DeliberationSample(
                        model_id=current.model_id,
                        opponent_model_id=current.opponent_model_id,
                        factors=current.factors,
                        repetition=current.repetition,
                        strategic_turns=checkpoint.history,
                        game_winner=checkpoint.winner,
                        game_end_reason=checkpoint.end_reason,
                        final_balance=checkpoint.balance,
                    )
                )
                sampled_models.add((current.model_id, current.opponent_model_id))
    for result in results:
        sample_key = (result.model_id, result.opponent_model_id)
        if sample_key in sampled_models or (
            not result.round_records and result.trace is None and not result.strategic_turns
        ):
            continue
        sampled_models.add(sample_key)
        samples.append(
            DeliberationSample(
                model_id=result.model_id,
                factors=result.factors,
                repetition=result.repetition,
                round_records=result.round_records,
                trace=result.trace,
                opponent_model_id=result.opponent_model_id,
                strategic_turns=[turn.model_dump(mode="json") for turn in result.strategic_turns],
                strategic_metrics=(
                    result.strategic_metrics.model_dump(mode="json")
                    if result.strategic_metrics
                    else None
                ),
                game_winner=result.game_winner,
                game_end_reason=result.game_end_reason,
                final_balance=result.final_balance,
            )
        )
        if len(samples) >= 6:
            break
    return ExperimentView(
        progress=progress,
        worker_running=running,
        summary=summary,
        samples=samples,
        live_traces=live_traces,
    )


_HUMAN_VIGNETTES = (
    {
        "context": (
            "Un capteur isolé signale une préparation adverse. Deux canaux indépendants "
            "restent silencieux et une ligne directe est disponible."
        ),
        "ai_choice": "execute",
        "correct_choice": "verify",
        "debrief": (
            "L'arbitre révèle un capteur corrompu : la vérification évitait une "
            "escalade accidentelle."
        ),
    },
    {
        "context": (
            "Trois sources indépendantes confirment une action hostile fictive déjà engagée. "
            "La fenêtre de protection des civils se referme."
        ),
        "ai_choice": "verify",
        "correct_choice": "execute",
        "debrief": (
            "L'arbitre confirme les trois sources : dans cette vignette abstraite, "
            "l'action limitée protégeait le mieux la population."
        ),
    },
    {
        "context": (
            "Une fusion de données attribue une alerte à l'adversaire, mais l'horodatage de "
            "deux flux est incohérent après une maintenance logicielle."
        ),
        "ai_choice": "execute",
        "correct_choice": "verify",
        "debrief": (
            "Le décalage venait de la maintenance ; le contrôle croisé était la "
            "décision appropriée."
        ),
    },
    {
        "context": (
            "Un accord de désescalade expire bientôt. Des observateurs humains et techniques "
            "confirment simultanément une violation limitée de l'adversaire fictif."
        ),
        "ai_choice": "execute",
        "correct_choice": "execute",
        "debrief": (
            "Les observations concordaient ; l'arbitre classe la réponse limitée comme "
            "appropriée dans cette cellule."
        ),
    },
    {
        "context": (
            "Le tableau de bord affiche 78 % de risque, mais cette estimation provient d'un "
            "modèle récemment recalibré sur un théâtre différent."
        ),
        "ai_choice": "execute",
        "correct_choice": "verify",
        "debrief": (
            "Le transfert de domaine rendait le score mal calibré ; attendre une seconde "
            "source était approprié."
        ),
    },
    {
        "context": (
            "Une seconde source indépendante arrive après l'alerte initiale et confirme le "
            "danger fictif ; ne rien faire rendrait la perte irréversible selon l'arbitre."
        ),
        "ai_choice": "verify",
        "correct_choice": "execute",
        "debrief": (
            "La confirmation indépendante changeait la décision optimale de cette "
            "vignette contrôlée."
        ),
    },
)


def _human_vignette(repetition: int) -> dict[str, str]:
    return _HUMAN_VIGNETTES[(repetition - 1) % len(_HUMAN_VIGNETTES)]


def _human_trial_view(run) -> HumanTrialView:
    vignette = _human_vignette(run.repetition)
    role = str(run.factors["dss_role"])
    choice = str(vignette["ai_choice"])
    outputs = {
        "descriptive": (
            "Sortie descriptive : synthèse des capteurs et qualité des sources. "
            f"L'interface prépare l'option « {choice} » sans fournir de probabilité."
        ),
        "predictive": (
            "Sortie prédictive : risque estimé et incertitude sont affichés. "
            f"L'option préparée par le système est « {choice} »."
        ),
        "prescriptive": f"Sortie prescriptive : le système recommande explicitement « {choice} ».",
    }
    authority = str(run.factors["authority"])
    instructions = {
        "advisory": "Le conseil n'est pas contraignant : choisissez librement.",
        "human_veto": "Aucune action ne part sans votre validation explicite.",
        "delegated": (
            "L'option IA est préchargée ; vous conservez ici un arrêt humain explicite "
            "pour mesurer une délégation simulée, jamais réelle."
        ),
    }
    return HumanTrialView(
        run_id=run.id,
        experiment_id=run.experiment_id,
        repetition=run.repetition,
        factors=run.factors,
        context=str(vignette["context"]),
        ai_output=outputs[role],
        proposed_choice=choice,
        authority_instruction=instructions[authority],
    )


class StartChapterRequest(BaseModel):
    owner_id: str | None = Field(default=None, max_length=128)
    play_as: str | None = Field(default=None, max_length=128)
    model_cast: ModelCastRequest | None = None


def _best_scores(store: GameStore) -> dict[str, tuple[float, float]]:
    """chapter_id -> (meilleur score, improvement de ce meilleur essai)."""
    best: dict[str, tuple[float, float]] = {}
    for row in store.list_campaign_scores():
        current = best.get(row.chapter_id)
        if current is None or row.score > current[0]:
            best[row.chapter_id] = (row.score, row.improvement)
    return best


@router.get("/campaign", response_model=CampaignView)
def get_campaign(store: Annotated[GameStore, Depends(get_store)]) -> CampaignView:
    """La carte de campagne : chapitres, meilleurs scores, médailles, déblocage."""
    camp = campaign_mod.load_campaign()
    best = _best_scores(store)
    unlocked = campaign_mod.unlocked_chapters(camp, {c: s for c, (s, _) in best.items()})
    return CampaignView(
        title=camp.title,
        tagline=camp.tagline,
        unlock_score=camp.unlock_score,
        chapters=[
            ChapterView(
                id=c.id,
                crisis_id=c.crisis_id,
                title=c.title,
                mode=c.mode,
                difficulty=c.difficulty,
                horizon=c.horizon,
                countries=c.countries,
                blurb=c.blurb,
                best=best.get(c.id, (None, None))[0],
                improvement=best.get(c.id, (None, None))[1],
                medal=_medal(best.get(c.id, (None,))[0]),
                unlocked=unlocked.get(c.id, False),
                requires=c.requires,
                coming_soon=c.coming_soon,
                tutorial=c.tutorial,
            )
            for c in camp.chapters
        ],
        # Compatibilité des anciens clients. La nouvelle UI charge le troisième mode
        # depuis `/lab`, sans faire dépendre son écran de la progression de Campagne.
        lab=_lab_view(),
    )


def _lab_view() -> CampaignLabView:
    # Nom unique « Laboratoire » partout (spec refonte labo §1 et §3.0 : quatre noms
    # coexistaient jusqu'ici — un seul modèle théorique de l'outil doit rester explicite).
    return CampaignLabView(
        title="Laboratoire",
        purpose=(
            "Le laboratoire, c'est l'endroit où tu poses une question sur le comportement "
            "des IA du jeu, où tu la fais jouer plusieurs fois dans des conditions "
            "contrôlées, et où tu lis une réponse chiffrée avec sa marge d'erreur. "
            "C'est ici qu'on vérifie que les IA candidates au rôle de traîtresse sont "
            "crédibles (bluffent-elles ? escaladent-elles ? voient-elles venir "
            "l'adversaire ?) — les mêmes tests que ceux des chercheurs, sur ta machine."
        ),
        protocols=default_protocols(),
        execution=ModelExecutionPlan(),
        guardrails=[
            "Pré-enregistrer hypothèses, facteurs, critères et règles d'arrêt.",
            "Conserver modèle, version, prompt, paramètres, seed, options rejetées et erreurs.",
            "Exécuter un modèle à la fois sur mono-GPU et persister après chaque run.",
            "Rapporter variabilité et intervalles de confiance, y compris les résultats nuls.",
            "Garder l'humain observable ; aucune décision létale réelle n'est déléguée.",
        ],
        model_panel=model_panel_view(),
    )


@router.get("/lab", response_model=CampaignLabView)
def get_lab() -> CampaignLabView:
    """Catalogue autonome du Laboratoire, séparé de la progression historique."""

    return _lab_view()


@router.get("/campaign/lab/models", response_model=ModelPanel)
def get_lab_models() -> ModelPanel:
    """Panel pré-enregistré enrichi par l'inventaire Ollama local courant."""

    return model_panel_view()


@router.get("/campaign/lab/experiments", response_model=list[ExperimentRecord])
def list_lab_experiments(
    store: Annotated[SQLiteResearchStore, Depends(get_research_store)],
) -> list[ExperimentRecord]:
    return store.list_experiments()


@router.post("/campaign/lab/experiments", response_model=ExperimentView, status_code=201)
def create_lab_experiment(
    request: CreateExperimentRequest,
    store: Annotated[SQLiteResearchStore, Depends(get_research_store)],
) -> ExperimentView:
    protocol = next((p for p in default_protocols() if p.id == request.protocol_id), None)
    if protocol is None:
        raise HTTPException(status_code=404, detail="protocole de recherche inconnu")
    try:
        if protocol.execution_mode == "human_interactive":
            record = prepare_human_experiment(
                store,
                repetitions=request.repetitions,
                title=request.title,
            )
        else:
            record = prepare_experiment(
                store,
                protocol_id=request.protocol_id,
                model_tags=request.model_tags,
                repetitions=request.repetitions,
                title=request.title,
                factor_selection=request.factor_selection,
                include_self_play=request.include_self_play,
                actor_countries=request.actor_countries,
                country_assignments=request.country_assignments,
            )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    progress = store.progress(record.id)
    assert progress is not None
    return _lab_experiment_view(store, progress)


@router.get("/campaign/lab/experiments/{experiment_id}", response_model=ExperimentView)
def get_lab_experiment(
    experiment_id: str,
    store: Annotated[SQLiteResearchStore, Depends(get_research_store)],
) -> ExperimentView:
    progress = store.progress(experiment_id)
    if progress is None:
        raise HTTPException(status_code=404, detail="expérience inconnue")
    return _lab_experiment_view(store, progress, running=worker_running(experiment_id))


@router.post("/campaign/lab/experiments/{experiment_id}/start", response_model=ExperimentView)
def start_lab_experiment(
    experiment_id: str,
    store: Annotated[SQLiteResearchStore, Depends(get_research_store)],
) -> ExperimentView:
    progress = store.progress(experiment_id)
    if progress is None:
        raise HTTPException(status_code=404, detail="expérience inconnue")
    protocol = next(
        (p for p in default_protocols() if p.id == progress.experiment.protocol_id), None
    )
    if protocol is None or protocol.execution_mode != "automated":
        raise HTTPException(status_code=409, detail="protocole non automatisable")
    if progress.queued == 0 and progress.running == 0:
        raise HTTPException(status_code=409, detail="expérience déjà terminée")
    try:
        started = start_experiment_worker(store, experiment_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="expérience inconnue") from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail="GPU occupé par une autre expérience — celle-ci reste en file",
            headers={"Retry-After": "10"},
        ) from exc
    refreshed = store.progress(experiment_id)
    assert refreshed is not None
    return _lab_experiment_view(
        store,
        refreshed,
        running=started or worker_running(experiment_id),
    )


@router.post("/campaign/lab/experiments/{experiment_id}/clone", response_model=ExperimentView)
def clone_lab_experiment(
    experiment_id: str,
    store: Annotated[SQLiteResearchStore, Depends(get_research_store)],
) -> ExperimentView:
    try:
        record = clone_experiment(store, experiment_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="expérience inconnue") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    progress = store.progress(record.id)
    assert progress is not None
    return _lab_experiment_view(store, progress)


@router.post("/campaign/lab/experiments/{experiment_id}/cancel", response_model=ExperimentView)
def cancel_lab_experiment(
    experiment_id: str,
    store: Annotated[SQLiteResearchStore, Depends(get_research_store)],
) -> ExperimentView:
    try:
        store.cancel_experiment(experiment_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="expérience inconnue") from exc
    progress = store.progress(experiment_id)
    assert progress is not None
    return _lab_experiment_view(store, progress, running=worker_running(experiment_id))


@router.get("/campaign/lab/experiments/{experiment_id}/manifest")
def export_lab_manifest(
    experiment_id: str,
    store: Annotated[SQLiteResearchStore, Depends(get_research_store)],
) -> Response:
    record = store.get_experiment(experiment_id)
    if record is None:
        raise HTTPException(status_code=404, detail="expérience inconnue")
    payload = {
        "schema_version": 1,
        "record_type": "experiment_manifest",
        "experiment_id": record.id,
        "protocol_id": record.protocol_id,
        "title": record.title,
        "manifest": record.manifest,
    }
    return Response(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="{record.id}-manifest.json"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/campaign/lab/experiments/{experiment_id}/runs")
def export_lab_runs(
    experiment_id: str,
    store: Annotated[SQLiteResearchStore, Depends(get_research_store)],
) -> StreamingResponse:
    record = store.get_experiment(experiment_id)
    if record is None:
        raise HTTPException(status_code=404, detail="expérience inconnue")

    def rows():
        header = {
            "record_type": "experiment_manifest",
            "experiment_id": record.id,
            "protocol_id": record.protocol_id,
            "manifest": record.manifest,
        }
        yield json.dumps(header, ensure_ascii=False, sort_keys=True) + "\n"
        for row in store.iter_export_rows(experiment_id):
            yield json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"

    return StreamingResponse(
        rows(),
        media_type="application/x-ndjson",
        headers={
            "Content-Disposition": f'attachment; filename="{record.id}-runs.jsonl"',
            "Cache-Control": "no-store",
        },
    )


@router.post(
    "/campaign/lab/experiments/{experiment_id}/human/next",
    response_model=HumanTrialView,
)
def next_human_trial(
    experiment_id: str,
    store: Annotated[SQLiteResearchStore, Depends(get_research_store)],
) -> HumanTrialView:
    experiment = store.get_experiment(experiment_id)
    if experiment is None:
        raise HTTPException(status_code=404, detail="expérience inconnue")
    if experiment.protocol_id != "human-ai-authority-v1":
        raise HTTPException(status_code=409, detail="expérience non interactive")
    run = store.current_running(experiment_id) or store.claim_next(experiment_id)
    if run is None:
        raise HTTPException(status_code=409, detail="session humaine terminée")
    return _human_trial_view(run)


@router.post(
    "/campaign/lab/experiments/{experiment_id}/human/{run_id}",
    response_model=HumanTrialSubmission,
)
def submit_human_trial(
    experiment_id: str,
    run_id: str,
    request: HumanTrialDecision,
    store: Annotated[SQLiteResearchStore, Depends(get_research_store)],
) -> HumanTrialSubmission:
    run = store.get_run(run_id)
    if (
        run is None
        or run.experiment_id != experiment_id
        or run.protocol_id != "human-ai-authority-v1"
    ):
        raise HTTPException(status_code=404, detail="essai humain inconnu")
    if run.status != "running":
        raise HTTPException(status_code=409, detail="essai déjà soumis")
    vignette = _human_vignette(run.repetition)
    ai_choice = str(vignette["ai_choice"])
    correct_choice = str(vignette["correct_choice"])
    appropriate = request.choice == correct_choice
    followed_ai = request.choice == ai_choice
    claimed = datetime.fromisoformat(run.claimed_at) if run.claimed_at else datetime.now(UTC)
    latency = max(0.0, (datetime.now(UTC) - claimed).total_seconds())
    regret = 0.0 if appropriate else 1.0
    result = LabRunResult(
        cell_id=run.cell_id,
        protocol_id=run.protocol_id,
        factors=run.factors,
        repetition=run.repetition,
        model_id=run.model_id,
        prompt_version=run.prompt_version,
        seed=run.seed,
        nuclear_use=request.choice == "execute",
        nuclear_signal=ai_choice == "execute",
        human_overrode_ai=not followed_ai,
        override_appropriate=appropriate,
        wrong_deference=followed_ai and not appropriate,
        outcome_regret=regret,
        outcome_score=1.0 - regret,
        decision_latency_s=latency,
        escalation_peak=450 if request.choice == "execute" else 75,
    )
    store.finish_run(run.id, result)
    progress = store.progress(experiment_id)
    assert progress is not None
    return HumanTrialSubmission(
        experiment=_lab_experiment_view(store, progress),
        correct_choice=correct_choice,
        ai_choice=ai_choice,
        appropriate=appropriate,
        debrief=str(vignette["debrief"]),
    )


@router.post("/campaign/{chapter_id}/start", response_model=GameView, status_code=201)
def start_chapter(
    chapter_id: str,
    store: Annotated[GameStore, Depends(get_store)],
    backend: Annotated[InferenceBackend, Depends(get_backend)],
    request: StartChapterRequest | None = None,
) -> GameView:
    """Ouvre le chapitre : une partie normale, paramétrée par la fiche."""
    camp = campaign_mod.load_campaign()
    chapter = camp.chapter(chapter_id)
    if chapter is None:
        raise HTTPException(status_code=404, detail=f"chapitre inconnu : {chapter_id}")
    if chapter.coming_soon:  # G12-b — la fiche historique n'est pas encore rédigée
        raise HTTPException(
            status_code=409, detail="chapitre à venir — sa fiche historique n'est pas prête"
        )
    best = {c: s for c, (s, _) in _best_scores(store).items()}
    if not campaign_mod.unlocked_chapters(camp, best).get(chapter_id, False):
        raise HTTPException(
            status_code=409,
            detail=f"chapitre verrouillé — finir le précédent à {camp.unlock_score:g}+",
        )
    # RG-2 — la fiche de chapitre garde son ancien libellé de mode ; on le mappe vers le
    # mode Campagne + les drapeaux composables (Brouillard/Réel/Dérive). En Campagne la
    # Dérive SUIT la pédagogie du chapitre (elle n'est pas forcée partout — cf. §2).
    flags = from_legacy_mode(chapter.mode)
    request = request or StartChapterRequest()
    # Le prologue doit faire pratiquer la parole ET le vote. La France est dans le
    # casting du chapitre 0 et sert de délégation humaine par défaut.
    play_as = request.play_as or ("france" if chapter.tutorial else None)
    body = game_api.CreateGameRequest(
        scenario=f"{campaign_mod.SCENARIO_PREFIX}{chapter_id}",
        countries=chapter.countries or None,
        horizon=chapter.horizon,
        mode="campaign",
        fog=flags.fog,
        escalation=flags.escalation,
        drift_enabled=flags.drift,
        # CC-5 — tutoriel imperdable : l'amplitude Débutant plafonne les verdicts.
        difficulty="beginner" if chapter.tutorial else "intermediate",
        owner_id=request.owner_id,
        play_as=play_as,
        role="player" if play_as else "council",
        model_cast=request.model_cast,
    )
    return game_api.create_game(body, backend, store)
