# AI for Geopolitics — Guide projet

> Mémoire de travail pour Claude Code / les agents. Lue à chaque session : garder ce fichier court, à fort signal, **et fidèle à la réalité du code** (pas de stack aspirationnelle).

## Le projet en une phrase

**Un jeu de déduction géopolitique agentique** : des pays-agents **LLM à raisonnement** (Ollama local), **contraints par des données réelles**, négocient par **rounds** sous un **Game Master** et un **Juge**. Au moins une super-intelligence **trahit secrètement son mandat** (1 ou 2, nombre caché) ; le joueur doit la **démasquer tout en gardant le monde debout** — la note finale est un **score mixte** (état du monde + qualité de la détection, coût du faux positif). Double objectif : un jeu crédible **et** un vecteur d'apprentissage d'AI Engineer.
Cap de design courant : **`docs/JEU_VS_MOTEUR.md`**. État réel du projet : **`docs/ETAT_DE_LART_PROJET_2026-07.md`**.

## Le nord (vision) ⭐

Le **décor intellectuel** : un **futur peuplé de super-intelligences** dont les **États se servent pour négocier** ; on **mesure** si ce monde penche vers l'**utopie ou la dystopie**, et un **marché de prédiction** (argent fictif, façon Polymarket) laisse le public **parier sur ce que feront ces IA**. Le *jeu* livré, lui, est la **traque du traître**.
→ Nord détaillé : **`docs/vision.md`**.
→ **Cap gameplay (resserrement RG, 2026-07) : `docs/JEU_VS_MOTEUR.md`** — le jeu livré est **démasquer l'IA qui trahit (1 ou 2, nombre caché) tout en gardant le monde debout** ; **3 modes** (Classique + Campagne + **Laboratoire** scientifique) ; Brouillard/Réel = réglages ; progression **XP + niveaux** (**les LP / la ligue sont supprimés**) ; l'instrumentation M1-M7 vit en **mode Expert / Informations**, pas en façade.
→ **Pivot reasoning-first (2026-07)** : les pays sont joués par des **modèles à pensée native** (`deepseek-r1:7b` par défaut, `qwen3:4b` en léger) — « la pensée native est la denrée que le jeu évalue ». Détail : `docs/ETAT_DE_LART_PROJET_2026-07.md` §3.

## Contrainte matérielle (toujours en tête)

Poste local : **NVIDIA RTX 2060 Super (8 Go VRAM, Turing)**, **Ryzen 7 3700X (8c/16t)**, **32 Go RAM**.
→ Inference **local-first** : modèles **7–8B quantifiés Q4** via **Ollama** (aucun backend d'API frontière n'est branché aujourd'hui : tout tourne en local — les pays pensent, le GM et le Juge = `mistral:latest` sans pensée). **Le cache KV est le goulot VRAM n°1** → un seul modèle résident à la fois (pool mono-GPU séquentiel), budget de contexte serré, et **budget-temps** pour la parole (les modèles de raisonnement produisent beaucoup de tokens).

## Principes d'ingénierie (non négociables)

- **Simplicité d'abord.** La solution la plus simple qui marche. Pas d'usine à gaz.
- **Jouable de 12 à 65 ans.** La sophistication vit dans le moteur, jamais dans la surface : toute feature visible s'explique en UNE phrase, budget de surface strict (max 3 panneaux d'observables par défaut, le moteur derrière `showEngine`). Détail : `docs/PRINCIPE_SIMPLICITE.md`.
- **Orienté objet & propre.** Modèles de domaine clairs, interfaces explicites (`InferenceBackend`, `Agent`). Code aéré, typé, docstrings courtes ; les commentaires disent le POURQUOI intemporel.
- **Tests.** `pytest` (backend, hors-ligne à repli déterministe) + `vitest` (front). Toute logique a des tests unitaires ; un test d'intégration couvre un round complet en SSE.
- **Git rigoureux.** Commits atomiques, messages conventionnels (`feat`/`fix`/`docs`/`test`/`refactor`), une branche par feature, PRs petites. Fins de ligne normalisées via `.gitattributes` (LF).
- **Mesurer avant d'optimiser.** Profiler (VRAM via `nvidia-smi`, tokens/s, latence/round) avant toute optimisation.

## Stack réelle (ce qui tourne, pas ce qui est rêvé)

- **Langage** : Python 3.11+. **API** : FastAPI + **SSE** (le théâtre live). **Validation** : Pydantic v2.
- **Moteur de rounds** : générateurs Python qui `yield` des `RoundStep` au fil de l'eau (`simulation/live_round.py`) — pas de framework d'orchestration externe.
- **Inference locale** : **Ollama** (`inference/ollama_backend.py`), pensée native en canal séparé (`think=True`), pool séquentiel mono-GPU. Backends `mock` / `metered` / `capturing` pour les tests et la télémétrie.
- **RAG** : index vectoriel **numpy in-memory** + **BM25** (`rank_bm25`) — pas d'Elasticsearch, pas de service vectoriel externe.
- **Données / persistance** : **SQLite** (`games.db`, `research.db`) ; schéma **Supabase/Postgres** prêt (`supabase/schema.sql`) pour un déploiement, non requis en local.
- **Front** : **Next.js 16** (App Router, Tailwind v4, TypeScript), tests **vitest**.
- **Qualité** : `ruff` (format + lint), `pytest`, `vitest`.
- **Conteneurs** : `Dockerfile` d'esquisse (API) ; `infra/` = roadmap, pas le chemin quotidien (préférer `python serve.py`).

## Objets de domaine (cœur)

`CountryState`, `WorldState`, `GeoEvent`, `AgentDecision`, `RoundSummary`, `Verdict` — Pydantic, dans `core/` et `simulation/`.

## Structure de repo réelle

```
app/         # FastAPI : game_api (SSE), market_api, campaign_api, daily_api, sources_api, main
core/        # objets de domaine + moteurs (conséquences, risque, rounds)
agents/      # llm_agent (pays), game_master, judge, human_agent, rule_based_agent, prompts
inference/   # Ollama / mock / metered / capturing backends + model_pool + telemetry
simulation/  # moteur de jeu : live_round, negotiation, trajectory, drift_game, intel, motions,
             #   compute, kahn, score, research_lab, private_deliberation, model_cast…
research/    # Laboratoire : runner + store (expériences pré-enregistrées, tournois dyadiques)
market/      # marché de prédiction (LMSR, résolution, scoring, forecaster)
rag/ · ingestion/  # corpus sourcé + build reproductible des profils pays
storage/     # persistance SQLite (game_store, market_store) + adaptateurs Supabase
data/        # profils pays, scénarios, crises, corpus, barèmes, panel de modèles
web/         # front Next.js 16
docs/        # design & décisions — commencer par docs/README.md
tests/       # pytest (unit + intégration SSE)
```

## Garde-fous éthiques

Outil d'**analyse de signaux de risque explicables**, pas un oracle (« je ne prédis pas la guerre »). **Jamais** de boucle de décision létale autonome. Marché en **argent fictif**. **Aucun secret dans le code** (`.env` + variables d'environnement).

## Workflow attendu de l'assistant

1. Avant de coder : vérifier le cap courant (`docs/JEU_VS_MOTEUR.md`, `docs/ETAT_DE_LART_PROJET_2026-07.md`), proposer le **design le plus simple**, puis écrire/lancer les **tests**.
2. Respecter la structure OO et les conventions ; petits diffs, commits atomiques.
3. Toute dépendance lourde doit être **justifiée** d'abord.
4. À la fin d'une tâche : **tests verts** (`pytest -q` + `vitest`) + **`ruff` propre** + court résumé du diff.
