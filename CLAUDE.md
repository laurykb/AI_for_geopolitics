# AI for Geopolitics — Guide projet

> Mémoire de travail pour Claude Code. Lue à chaque session : garder ce fichier court et à fort signal.

## Le projet en une phrase

Simulation géopolitique **agentique** : des pays-agents LLM, **contraints par des données réelles**, réagissent par **rounds** sous la supervision d'un **Game Master** ; **RAG sourcé** + **moteur de risque explicable**. Double objectif : un système crédible **et** un vecteur d'apprentissage d'AI Engineer.
Référence complète : `AI_for_Geopolitics_Etat_de_lart.pdf` (état de l'art & positionnement).

## Le nord (vision) ⭐

Au fond, le projet met en scène un **futur peuplé de super-intelligences** (plus intelligentes que les humains) dont les **États se servent pour négocier** à la plus haute instance ; on **mesure** si ce monde penche vers l'**utopie ou la dystopie**, et un **marché de prédiction** (argent fictif, façon Polymarket) laisse le public **parier sur ce que feront ces IA** — *prédire une super-intelligence* est le cœur intellectuel.
→ Nord détaillé : **`docs/vision.md`**. Feuille de route des mécaniques (ancrage réel + découpage Cowork/Claude Code) : **`docs/roadmap_features.md`**.

## Contrainte matérielle (toujours en tête)

Poste local : **NVIDIA RTX 2060 Super (8 Go VRAM, Turing)**, **Ryzen 7 3700X (8c/16t)**, **32 Go RAM**.
→ Inference **local-first hybride** : modèle **7–8B quantifié Q4** en local via un service Python ; **API frontière** (Claude/GPT) pour le Game Master, les rounds difficiles et le juge d'évaluation. **Le cache KV est le goulot VRAM n°1** → budget de contexte serré (résumés, top-k 3–5, sorties JSON capées).

## Principes d'ingénierie (non négociables)

- **Simplicité d'abord.** La solution la plus simple qui marche. Pas d'usine à gaz. N'ajouter une brique lourde (Kafka, Elasticsearch, Kubernetes) que si un besoin réel la justifie.
- **Orienté objet & propre.** Modèles de domaine clairs, interfaces explicites (`InferenceBackend`, `Agent`, `Retriever`). Code aéré, typé (type hints), docstrings courtes.
- **Tests.** `pytest`. Toute logique (moteur de conséquences, parsing JSON, round engine) a des tests unitaires ; un test d'intégration couvre un round complet.
- **Git rigoureux.** Commits atomiques, messages conventionnels (`feat`/`fix`/`docs`/`test`/`refactor`), une branche par feature, PRs petites.
- **Mesurer avant d'optimiser.** Profiler (VRAM via `nvidia-smi`, tokens/s, latence/round) avant toute optimisation.

## Stack (décisions par défaut)

- **Langage** : Python 3.11+. **API** : FastAPI. **Validation** : Pydantic v2.
- **Orchestration agents** : LangGraph (le graphe d'états = moteur de rounds, machine `BASE → RECALL → FALLBACK`).
- **Outils agents** : exposés en **MCP** ; REST réservé à l'UI.
- **Inference locale** : `llama-cpp-python` (démarrage, GGUF Q4) → ExLlamaV2 / vLLM (optimisation). Baseline : Ollama.
- **Embeddings / rerank** : `sentence-transformers` (bge/e5) + cross-encoder, **sur CPU**.
- **RAG** : Chroma (vector) + BM25 (`rank_bm25`) + RRF + reranking. Elasticsearch seulement plus tard.
- **Données** : PostgreSQL (état + event store), Redis (cache + broker léger).
- **Qualité** : `ruff` (format + lint), `pytest`, `mypy` (optionnel).
- **Conteneurs** : Docker (une image par service) + docker-compose ; kind / Kubernetes pour la phase infra.

## Objets de domaine (cœur)

`CountryState`, `WorldState`, `GeoEvent`, `AgentDecision`, `DiplomaticMessage`, `RoundSummary`. Tous en Pydantic, dans `core/`.

## Roadmap (rester dans la phase courante)

Fait : `P0` moteur déterministe → `P1` agents LLM → `P2` diplomatie → `P3` RAG → `P4` données réelles → **interface (théâtre live)**. Ensuite : `P6` infra (Docker → K8s) → `P7` MCP / distribué.
**Enrichissement** (ludique × réel) : voir `docs/roadmap_features.md` — keystone = **marché de prédiction** + **couche recherche**.
**MVP** : 1 zone (ex. mer Rouge), 6–8 acteurs, 1 scénario, 1 risk score, dashboard simple.

## Structure de repo cible

```
app/        # FastAPI (entrée, config)
core/       # objets de domaine + moteur de rounds + conséquences
agents/     # base_agent, country_agent, game_master
inference/  # service d'inférence Python (InferenceBackend + impls)
rag/        # ingestion, chunking, retriever, reranker, citations
simulation/ # engine, action_space, risk_engine, diplomacy
storage/    # postgres, redis, vector_store
data/       # countries/*.json, scenarios/*.json, corpus
docs/       # architecture.md, simulation_model.md, data_governance.md, limitations.md
tests/      # unit + integration
```

## Garde-fous éthiques

Outil d'**analyse de signaux de risque explicables**, pas un oracle (« je ne prédis pas la guerre »). **Jamais** de boucle de décision létale autonome. Documenter les limites dans `docs/limitations.md`. **Aucun secret dans le code** (`.env` + variables d'environnement).

## Workflow attendu de l'assistant

1. Avant de coder une brique : vérifier la **phase** courante, proposer le **design le plus simple**, puis écrire/lancer les **tests**.
2. Respecter la structure OO et les conventions ci-dessus ; petits diffs, commits atomiques.
3. Toute dépendance lourde doit être **justifiée** d'abord.
4. À la fin d'une tâche : tests verts + `ruff` propre + court résumé du diff.
