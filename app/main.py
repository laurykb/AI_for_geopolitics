"""API FastAPI (backend) — Phase 5.

L'UI humaine est l'app Streamlit (`ui/app.py`). FastAPI reste comme backend/service
(santé + run JSON) pour l'architecture services de P6/P7.

Lancer : `uvicorn app.main:app`.
"""

from __future__ import annotations

from fastapi import FastAPI

from app.dashboard import DashboardData, run_red_sea
from app.market_api import router as market_router

app = FastAPI(title="AI for Geopolitics — API")
app.include_router(market_router)


@app.get("/health")
def health() -> dict[str, str]:
    """Sonde de vivacité (utile pour le déploiement P6)."""
    return {"status": "ok"}


@app.get("/api/run", response_model=DashboardData)
def api_run() -> DashboardData:
    """Joue un run rule-based du scénario mer Rouge et renvoie son état complet."""
    return run_red_sea()
