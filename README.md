# AI for Geopolitics

Simulation géopolitique **agentique** : des pays-agents, contraints par des données réelles, réagissent par **rounds** sous un **Game Master** ; RAG sourcé + moteur de risque explicable. Double objectif : un système crédible **et** un vecteur d'apprentissage d'AI Engineer.

> Voir `docs/` pour l'**état de l'art** et le **plan d'action Claude Code**, et `CLAUDE.md` pour le guide projet.

## Phase 0 — moteur déterministe (sans LLM) ✅

La boucle de simulation tourne déjà, **sans aucun LLM** :

- **Modèles de domaine** (Pydantic) : `CountryState`, `WorldState`, `GeoEvent`, `AgentDecision`, `RoundSummary`.
- **Espace d'action** + **agent rule-based** (heuristique reproductible, même interface `Agent` que le futur `LLMAgent`).
- **Moteurs** : conséquences déterministes, risque explicable (escalade, perturbation éco, fracture d'alliance), round engine.
- **Scénario seed** : crise de la **mer Rouge**, 6 acteurs (USA, Chine, France, Égypte, Iran, Arabie saoudite), 3 événements.

## Phase 1 — agents LLM + service d'inférence local ✅

Les pays-agents décident désormais via un **LLM local**, en **JSON validé** :

- **`InferenceBackend`** (abstraction) + **`OllamaBackend`** (modèle 7-8B Q4 local, sortie contrainte par schéma JSON) + **`MockBackend`** (tests offline, sans GPU).
- **`LLMAgent`** : *drop-in* du `RoundEngine`. Parse tolérant, bornes clampées, identité injectée, **repli `RuleBasedAgent`** si JSON invalide ou backend indisponible.
- **Mesure** (`python -m inference.bench`) : tok/s, latence/round, VRAM (`nvidia-smi`).

> Baseline mesurée (mistral 7B Q4, RTX 2060 Super 8 Go) : **~56 tok/s**, ~3,4 s/agent, **~6,0 Go VRAM**, **0 fallback** sur 18 appels.

## Phase 2 — diplomatie ✅

Une **phase de négociation** s'intercale dans le round (`décisions → conséquences → diplomatie → risque`) :

- **`DiplomacyEngine`** (déterministe, explicable) : les propositions sont **agentiques** (`form_coalition`/`support` + cible, ou `proposed_alliances`) ; l'**accept/refuse** suit des règles claires (rivalité, tension, rival commun).
- **Pactes** : à l'acceptation, un pacte partagé `pact:<a>+<b>` est ajouté aux deux pays (`share_alliance` devient vrai) et la tension baisse — ce qui alimente la **fracture d'alliance** du moteur de risque.
- **Négociation visible** : `DiplomaticMessage` bilatéraux (offre + réponse) + **résumé public** dans `RoundSummary`, tracés dans `WorldState.diplomatic_history`.

## Phase 3 — RAG sourcé ✅

Pipeline de retrieval **hybride et explicable**, isolé dans `rag/` :

- **Hybride** : dense (`InMemoryVectorIndex`, cosinus numpy) + lexical (**BM25**) → fusion **RRF** → **reranking** cross-encoder (optionnel).
- **Embeddings/rerank sur CPU** (sentence-transformers, bge-small + cross-encoder) → libère la VRAM pour le LLM. Abstraction `Embedder` avec un **`HashingEmbedder`** déterministe pour des tests **offline** (sans torch).
- **Citations** : chaque résultat porte sa provenance → `build_brief` produit un **brief sourcé** (`[source: …]`).
- **Éval** : `recall@k` / `MRR` sur un jeu de requêtes labellisées (`data/corpus_seed/eval_queries.json`).

> Corpus seed **illustratif** (`data/corpus_seed/`) ; l'ingestion de données réelles est la **Phase 4**.

## Phase 4 — données réelles ✅

Les profils pays sont **sourcés** (World Bank/IMF/SIPRI/WIPO 2024) et **reproductibles** :

- `data/sources/indicators.json` : entrées brutes sourcées + provenance ; `docs/data_governance.md` documente source/année/confiance/normalisation/licences par champ.
- **Build déterministe** (`ingestion/`) : `python -m ingestion.build --check` garantit que chaque `data/countries/*.json` **est reproductible** depuis les sources (testé en CI).

## Interface — théâtre live des super-intelligences ⭐

Le cœur du projet : un **théâtre temps réel** où l'on **rend visibles les boîtes noires** du système
multi-agent. En spectateur, un round se déroule sous les yeux :

1. le **Game Master** (LLM) **génère un événement** ;
2. les pays-**super-intelligences** **négocient sur plusieurs passes** — chacune parle à son tour, en
   **streaming**, avec **badge du modèle** (`🧠 usa · mistral:latest`) et **chrono** (traçabilité du séquentiel) ;
3. un **Juge LLM** lit toute la négociation, **arbitre** qui a gagné / les alliances (raisonnement streamé),
   et fixe les **deltas d'attributs** — comme un G7, **non déterministe**, mais **borné** par un garde-fou ;
4. la **date avance** (~6 mois) → timeline réaliste.

Métaphore : un **G7 dont on voit tous les messages**. Sur RTX 2060 Super (8 Go), les agents parlent
**à tour de rôle** (mistral 7B local) — un round de négociation ≈ **1 min** ; repli si Ollama est éteint.
L'orchestration (`simulation/live_round.py`, `simulation/negotiation.py`, `agents/judge.py`) est
**testée sans Streamlit** ; le back-end **FastAPI** reste (`/health` + `/api/run`) pour l'archi services.

> À venir : rôles humains (GM humain, **joueur-pays** qui interjecte dans la négociation), puis substrat
> distribué **Kubernetes + MCP** (agents-services échangeant en langage naturel).

> Slice 1 (spectateur). À venir : messages **bilatéraux** multi-tours, rôles humains (incarner/GM) en live, attributs animés.

## Installation & tests

```bash
python -m venv .venv          # Python 3.11 recommandé
# Windows : .venv\Scripts\activate   |   Linux/macOS : source .venv/bin/activate
pip install -e . pytest ruff
ruff check .
pytest -q                     # suite complète, sans Ollama (MockBackend)
```

Bench LLM réel (nécessite [Ollama](https://ollama.com) lancé + `ollama pull mistral`) :

```bash
python -m inference.bench                 # mistral:latest par défaut
python -m inference.bench --model llama3.2:3b
```

RAG réel (embeddings/rerank CPU — nécessite l'extra `rag`) :

```bash
pip install -e ".[rag]"
python -m rag.demo "freedom of navigation in the Red Sea"   # retrieval + brief sourcé
python -m rag.demo --eval                                    # recall@k / MRR
```

Théâtre live (extra `ui` ; Ollama + mistral pour le raisonnement LLM, sinon repli rule-based) :

```bash
pip install -e ".[ui]"
streamlit run ui/app.py              # regarder les super-intelligences délibérer en direct
uvicorn app.main:app                 # backend API : /health + /api/run
```

## Structure

```
core/        # modèles de domaine + moteurs (conséquences, risque, rounds)
agents/      # base_agent, rule_based, llm_agent, human_agent, game_master
inference/   # InferenceBackend (+ streaming), Ollama / Mock, bench
simulation/  # action_space, diplomacy, clock, loader, live_round (round observable)
rag/         # corpus, embedder, BM25, vector index, RRF, retriever, brief, eval
ingestion/   # build reproductible des profils pays depuis data/sources
ui/          # app Streamlit (théâtre live) + game (contrôleur testable)
app/         # backend API FastAPI (/health, /api/run)
data/        # countries + sources + scenarios + corpus_seed
tests/       # unitaires + intégration (rounds, LLM, délibération, live, RAG, données, UI)
docs/        # plan d'action, gouvernance des données ; (état de l'art à la racine)
```

## Prochaine étape

**Théâtre live — slices suivants** : messages **bilatéraux** multi-tours (négociation LLM bornée par
timer), rôles humains (incarner un pays / Game Master) en live, attributs **animés**. Puis **infra**
(Docker, fichiers parqués sur `feat/p6-infra`). Voir `CLAUDE.md` et le nord dans la mémoire projet.
