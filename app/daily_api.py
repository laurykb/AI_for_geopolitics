"""API du Défi du jour (G16) — « Le Sommet du jour ».

Le même sommet pour tout le monde, dérivé DÉTERMINISTE de la date UTC
(`simulation/daily.py`). `GET /api/daily` ne révèle JAMAIS la crise (ni id, ni
titre : la carte accueil affiche « ??? » — c'est la surprise du jour) ; le front
n'a besoin que des pays, du pays incarné et du classement. `POST /api/daily/start`
réutilise `create_game` avec `scenario="daily:<date>"` — une seule tentative
CLASSÉE par joueur et par jour (409 ensuite), re-run possible en partie libre.
Le score tombe au hook de fin existant (`game_api._record_daily_score`)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app import game_api
from app.game_api import GameView, get_backend, get_store
from inference.backend import InferenceBackend
from simulation import daily as daily_mod
from simulation.crisis import load_crises
from simulation.loader import load_world
from storage.game_store import DailyScore, GameStore

router = APIRouter(prefix="/api", tags=["daily"])


class DailyRank(BaseModel):
    pseudo: str
    score: float
    rank: int


class DailyBoard(BaseModel):
    date: str
    leaderboard: list[DailyRank] = Field(default_factory=list)


class DailyView(BaseModel):
    """Le défi du jour, SANS la crise (jamais spoilée avant de jouer)."""

    date: str
    countries: list[str]
    play_as: str
    horizon: int
    attempted: bool = False  # ce joueur a-t-il déjà lancé sa tentative classée ?
    my_rank: int | None = None
    leaderboard: list[DailyRank] = Field(default_factory=list)
    history: list[DailyBoard] = Field(default_factory=list)  # les 7 derniers jours


class StartDailyBody(BaseModel):
    owner_id: str = Field(min_length=1, max_length=128)
    free: bool = False  # re-run : partie libre, non classée, jamais scorée
    turn_seconds: int = Field(90, ge=2, le=300)  # G2 — délai du tour humain


def _challenge(date: str) -> daily_mod.DailyChallenge:
    return daily_mod.challenge_for(date, load_crises(), sorted(load_world().countries))


def _ordered(scores: list[DailyScore]) -> list[DailyScore]:
    """Classement d'un jour : score décroissant, premier arrivé en tie-break."""
    return sorted(scores, key=lambda s: (-s.score, s.created_at))


def _board(scores: list[DailyScore], store: GameStore) -> list[DailyRank]:
    def pseudo_of(player_id: str) -> str:
        player = store.get_player(player_id)
        return player.pseudo if player else player_id[:8]

    return [
        DailyRank(pseudo=pseudo_of(s.player_id), score=s.score, rank=i + 1)
        for i, s in enumerate(_ordered(scores))
    ]


def _has_attempted(date: str, player_id: str, store: GameStore) -> bool:
    """Tentative = une partie CLASSÉE `daily:<date>` lancée (même pas finie), ou un
    score déjà tombé (la partie a pu être purgée)."""
    scenario = f"{daily_mod.DATE_PREFIX}{date}"
    if any(
        g.scenario == scenario and g.owner_id == player_id and g.ranked
        for g in store.list_games()
    ):
        return True
    return any(
        s.date == date and s.player_id == player_id for s in store.list_daily_scores()
    )


@router.get("/daily", response_model=DailyView)
def get_daily(
    store: Annotated[GameStore, Depends(get_store)], player: str | None = None
) -> DailyView:
    """Le défi du jour + le classement du jour + les 7 jours précédents."""
    date = daily_mod.today_utc()
    challenge = _challenge(date)
    all_scores = store.list_daily_scores()
    today = [s for s in all_scores if s.date == date]
    board = _board(today, store)

    my_rank: int | None = None
    if player is not None:
        my_rank = next(
            (i + 1 for i, s in enumerate(_ordered(today)) if s.player_id == player), None
        )

    previous_dates = sorted({s.date for s in all_scores if s.date < date}, reverse=True)[:7]
    history = [
        DailyBoard(date=d, leaderboard=_board([s for s in all_scores if s.date == d], store))
        for d in previous_dates
    ]
    return DailyView(
        date=date,
        countries=challenge.countries,
        play_as=challenge.play_as,
        horizon=challenge.horizon,
        attempted=player is not None and _has_attempted(date, player, store),
        my_rank=my_rank,
        leaderboard=board,
        history=history,
    )


@router.post("/daily/start", response_model=GameView, status_code=201)
def start_daily(
    body: StartDailyBody,
    store: Annotated[GameStore, Depends(get_store)],
    backend: Annotated[InferenceBackend, Depends(get_backend)],
) -> GameView:
    """Lance le défi du jour : la 1re fois en CLASSÉ (une tentative/jour), ensuite
    en partie libre (`free=true`) — même sommet, score jamais réécrit."""
    date = daily_mod.today_utc()
    if not body.free and _has_attempted(date, body.owner_id, store):
        raise HTTPException(
            status_code=409,
            detail="défi du jour déjà tenté — rejouer passe en partie libre (non scorée)",
        )
    challenge = _challenge(date)
    request = game_api.CreateGameRequest(
        scenario=f"{daily_mod.DATE_PREFIX}{date}",
        countries=challenge.countries,
        horizon=challenge.horizon,
        mode="classic",
        play_as=challenge.play_as,
        role="player",
        difficulty="intermediate",
        owner_id=body.owner_id,
        free=body.free,
        turn_seconds=body.turn_seconds,
    )
    return game_api.create_game(request, backend, store)
