"""Application FastAPI : dashboard de simulation géopolitique (lecture seule, Phase 5).

Lancer : `uvicorn app.main:app` puis ouvrir http://127.0.0.1:8000/.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.charts import risk_bars_svg, risk_legend, tension_heatmap_svg
from app.dashboard import run_red_sea

_HERE = Path(__file__).parent

app = FastAPI(title="AI for Geopolitics — Dashboard")
templates = Jinja2Templates(directory=str(_HERE / "templates"))
app.mount("/static", StaticFiles(directory=str(_HERE / "static")), name="static")


@app.get("/health")
def health() -> dict[str, str]:
    """Sonde de vivacité (utile pour le déploiement P6)."""
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request) -> HTMLResponse:
    """Joue le scénario mer Rouge et rend le dashboard complet."""
    data = run_red_sea()
    context = {
        "data": data,
        "heatmap_svg": tension_heatmap_svg(data.tensions, data.country_ids),
        "risk_svg": risk_bars_svg(data.summaries),
        "risk_legend": risk_legend(),
    }
    return templates.TemplateResponse(request=request, name="dashboard.html", context=context)
