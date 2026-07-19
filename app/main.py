"""API FastAPI (backend).

L'UI humaine est le front Next.js (`web/`), branché sur l'API de jeu SSE
(`app/game_api.py`) et l'API marché (`app/market_api.py`).

Lancer : `uvicorn app.main:app` (ou `python serve.py` pour l'API + le front).
"""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.campaign_api import router as campaign_router
from app.daily_api import router as daily_router
from app.dashboard import DashboardData, run_red_sea
from app.game_api import router as game_router
from app.market_api import router as market_router
from app.request_limits import (
    ExpensiveRequestLimitMiddleware,
    RequestBodyLimitMiddleware,
    SecurityHeadersMiddleware,
)
from app.sources_api import router as sources_router

app = FastAPI(title="AI for Geopolitics — API")


def cors_origins() -> list[str]:
    """Origines autorisées : le front local (:3000) + celles de `CORS_ORIGINS`
    (liste séparée par des virgules — utile pour une pile de vérification isolée)."""
    extra = [o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()]
    return ["http://localhost:3000", "http://127.0.0.1:3000", *extra]


# Front Next.js local (`web/`, Phase R3) : REST + SSE cross-origin depuis :3000.
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Accept", "Authorization", "Content-Type", "X-Request-ID"],
)
# 1 Mio suffit largement aux formulaires/événements du jeu. Le plafond est configurable
# pour un déploiement particulier, sans permettre une valeur accidentellement illimitée.
try:
    _body_limit = max(16_384, min(int(os.getenv("API_MAX_BODY_BYTES", "1048576")), 10_485_760))
except ValueError:
    _body_limit = 1_048_576
app.add_middleware(RequestBodyLimitMiddleware, max_bytes=_body_limit)
try:
    # Une seule génération lourde par défaut : le poste cible est mono-GPU et les castings
    # multi-modèles changent explicitement les poids. L'opérateur peut relever la limite sur
    # une machine multi-GPU via l'environnement, sans rendre la configuration locale instable.
    _max_expensive = max(1, min(int(os.getenv("MAX_CONCURRENT_SIMULATIONS", "1")), 64))
except ValueError:
    _max_expensive = 8
app.add_middleware(ExpensiveRequestLimitMiddleware, max_concurrent=_max_expensive)
app.add_middleware(SecurityHeadersMiddleware)
app.include_router(market_router)
app.include_router(game_router)
app.include_router(sources_router)
app.include_router(campaign_router)
app.include_router(daily_router)


@app.get("/")
def root() -> dict[str, str]:
    """Accueil de l'API : ouvrir :8000 dans un navigateur ne doit pas ressembler à
    une panne — le jeu, lui, vit sur le front Next.js (:3000)."""
    return {
        "app": "AI for Geopolitics — API",
        "jeu": "http://localhost:3000",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health")
def health() -> dict[str, str]:
    """Sonde de vivacité (utile pour le déploiement P6)."""
    return {"status": "ok"}


@app.get("/api/run", response_model=DashboardData)
def api_run() -> DashboardData:
    """Joue un run rule-based du scénario mer Rouge et renvoie son état complet."""
    return run_red_sea()
