"""API de campagne (G5) — « Ferez-vous mieux que l'Histoire ? ».

Un chapitre EST une partie normale paramétrée par sa fiche (mode + crise imposés) :
`POST /api/campaign/{chapter}/start` crée la partie avec `scenario = "campaign:<id>"`
(le lien, sans schéma neuf) ; le score tombe à la fin de partie (voir `game_api._finalize`)
dans `campaign_scores`. `GET /api/campaign` sert la carte de progression (meilleurs
scores, déblocage linéaire, médailles).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app import game_api
from app.game_api import GameView, get_backend, get_store
from inference.backend import InferenceBackend
from simulation import campaign as campaign_mod
from storage.game_store import GameStore

router = APIRouter(prefix="/api", tags=["campaign"])


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
    )


@router.post("/campaign/{chapter_id}/start", response_model=GameView, status_code=201)
def start_chapter(
    chapter_id: str,
    store: Annotated[GameStore, Depends(get_store)],
    backend: Annotated[InferenceBackend, Depends(get_backend)],
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
    body = game_api.CreateGameRequest(
        scenario=f"{campaign_mod.SCENARIO_PREFIX}{chapter_id}",
        countries=chapter.countries or None,
        horizon=chapter.horizon,
        mode=chapter.mode,  # type: ignore[arg-type] — validé par la fiche
        # CC-5 — tutoriel imperdable : l'amplitude Débutant plafonne les verdicts.
        difficulty="beginner" if chapter.tutorial else "intermediate",
    )
    return game_api.create_game(body, backend, store)
