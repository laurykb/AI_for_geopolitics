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

## Phase 5 — app interactive ✅

**App Streamlit** avec laquelle on **joue** la simulation, round par round, via un **sélecteur de rôle** :

- **Spectateur** : dérouler le scénario et regarder les pays-agents réagir.
- **Incarner un pays** : choisir soi-même l'action de son pays (les autres restent des agents).
- **Game Master** : composer et **envoyer un événement** (titre, acteurs, sévérité).

Agents **rule-based** par défaut (instantané) + **toggle LLM (Ollama)**. Affiche tensions, alliances/pactes, décisions, résumé diplomatique et **risque par round**. Le back-end **FastAPI** est conservé (`/health` + `/api/run`) pour l'architecture services (P6/P7). La logique de partie (`ui/game.py`) est testée **sans Streamlit**.

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

App interactive (aucun GPU — nécessite l'extra `ui`) :

```bash
pip install -e ".[ui]"
streamlit run ui/app.py              # jouer : spectateur / incarner un pays / game master
uvicorn app.main:app                 # backend API : /health + /api/run
```

## Structure

```
core/        # modèles de domaine + moteurs (conséquences, risque, rounds)
agents/      # base_agent, rule_based (P0), llm_agent (P1), human_agent (P5)
inference/   # InferenceBackend + OllamaBackend / MockBackend + bench (P1)
simulation/  # action_space (P0), diplomacy (P2), loader
rag/         # corpus, embedder, BM25, vector index, RRF, retriever, brief, eval (P3)
ingestion/   # build reproductible des profils pays depuis data/sources (P4)
ui/          # app Streamlit interactive + game (contrôleur testable) (P5)
app/         # backend API FastAPI (/health, /api/run) (P5)
data/        # countries + sources + scenarios + corpus_seed
tests/       # unitaires + intégration (rounds, LLM, diplomatie, RAG, données, UI)
docs/        # plan d'action, gouvernance des données ; (état de l'art à la racine)
```

## Prochaine étape

**Phase 6** — infra : Docker (une image par service) → docker-compose → kind/K8s ; `docs/deployment.md`. Voir `CLAUDE.md` et `docs/PLAN_ACTION_CLAUDE_CODE.md`.
