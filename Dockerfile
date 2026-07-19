# syntax=docker/dockerfile:1
#
# Image de l'API FastAPI (backend « Théâtre des super-intelligences »).
# ESQUISSE infra (roadmap P6) — pour le dev local quotidien, préférer `python serve.py`.
#
# Build :   docker build -t theatre-api:dev .
# Test   :  docker run --rm -p 8000:8000 theatre-api:dev   (puis GET :8000/health)
#
# Multi-stage : un « builder » installe les dépendances dans un préfixe isolé,
# le « runtime » ne garde que ces paquets + le code → image finale légère.

# ---------------------------------------------------------------------------
# Stage 1 — builder : compile/installe les dépendances Python.
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS builder

WORKDIR /build

# Les deps sont figées dans requirements.txt (miroir de pyproject.toml).
COPY requirements.txt ./

# --prefix=/install : arbre de paquets relogeable, copié tel quel dans le runtime.
# Aucune roue lourde ici (torch/sentence-transformers = extra RAG, hors image de base).
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---------------------------------------------------------------------------
# Stage 2 — runtime : image d'exécution minimale.
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS runtime

# Confort/robustesse Python en conteneur.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dépendances installées au stage builder (relogées sous /usr/local).
COPY --from=builder /install /usr/local

# Code backend. NB : `ingestion/` EST nécessaire au runtime
# (app.main -> app.sources_api -> ingestion.build) ; `data/` = profils pays + scénarios.
COPY app/        ./app/
COPY simulation/ ./simulation/
COPY core/       ./core/
COPY agents/     ./agents/
COPY inference/  ./inference/
COPY rag/        ./rag/
COPY storage/    ./storage/
COPY market/     ./market/
COPY ingestion/  ./ingestion/
COPY data/       ./data/

# Utilisateur non-root (bonne hygiène, même pour une esquisse).
RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

# Le port d'écoute de l'API (voir CMD ci-dessous et le Service K8s).
EXPOSE 8000

# Sonde applicative : /health renvoie {"status": "ok"} (cf. app/main.py).
# K8s pilote ses propres probes ; ce HEALTHCHECK sert au `docker run` nu.
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=2).status==200 else 1)"

# uvicorn sert app.main:app sur toutes les interfaces du conteneur.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
