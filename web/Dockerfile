# syntax=docker/dockerfile:1
#
# Image du front Next.js 16 (« Théâtre des super-intelligences »).
# ESQUISSE infra (roadmap P6) — pour le dev local quotidien, préférer `python serve.py`.
#
# Build (contexte = web/) :
#   docker build -t theatre-web:dev \
#     --build-arg NEXT_PUBLIC_API_BASE=http://localhost web/
#
# ⚠️ Next.js inline les variables NEXT_PUBLIC_* au moment du `next build`.
# Elles doivent donc être passées en --build-arg ICI (pas seulement via la
# ConfigMap au runtime) : la ConfigMap K8s ne modifiera PAS un bundle déjà compilé.
#
# Multi-stage : deps -> build -> runtime.

# ---------------------------------------------------------------------------
# Stage 1 — deps : installe les dépendances (cache Docker sur le lockfile).
# ---------------------------------------------------------------------------
FROM node:20-slim AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

# ---------------------------------------------------------------------------
# Stage 2 — build : compile le front (next build).
# ---------------------------------------------------------------------------
FROM node:20-slim AS build
WORKDIR /app

# Valeur inlinée dans le bundle client (voir avertissement en tête de fichier).
# Origine seule : les chemins du front portent déjà `/api`.
ARG NEXT_PUBLIC_API_BASE=http://localhost
ENV NEXT_PUBLIC_API_BASE=${NEXT_PUBLIC_API_BASE}
ENV NEXT_TELEMETRY_DISABLED=1

COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

# ---------------------------------------------------------------------------
# Stage 3 — runtime : sert le front compilé (next start).
# ---------------------------------------------------------------------------
# NB : next.config.ts n'active pas `output: "standalone"` (on ne touche pas au
# code applicatif dans cette passe). On copie donc le build complet + node_modules
# et on lance `next start`. Une vraie prod passerait en standalone → image bien
# plus légère (voir infra/README.md « ce qu'une vraie prod ajouterait »).
FROM node:20-slim AS runtime
WORKDIR /app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000

COPY --from=build /app/public ./public
COPY --from=build /app/.next ./.next
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/package.json ./package.json

# Utilisateur non-root fourni par l'image node.
USER node

EXPOSE 3000

# `npm run start` == `next start` (cf. web/package.json).
CMD ["npm", "run", "start"]
