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

## Phase 5 — dashboard ✅

**Dashboard FastAPI** (lecture seule) : rejoue le scénario mer Rouge (rule-based) et rend, dans une page server-rendered avec **SVG inline** (aucune dépendance JS) : **timeline** + headlines, **scores de risque** par round, **heatmap de tensions**, **alliances/pactes**, **journal diplomatique**.

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

Dashboard (aucun GPU) :

```bash
python -m ingestion.build            # vérifie la reproductibilité des profils pays
uvicorn app.main:app                 # puis http://127.0.0.1:8000/
```

## Structure

```
core/        # modèles de domaine + moteurs (conséquences, risque, rounds)
agents/      # base_agent + rule_based_agent (P0) + prompts + llm_agent (P1)
inference/   # InferenceBackend + OllamaBackend / MockBackend + bench (P1)
simulation/  # action_space (P0) + diplomacy (P2)
rag/         # corpus, embedder, BM25, vector index, RRF, retriever, brief, eval (P3)
ingestion/   # build reproductible des profils pays depuis data/sources (P4)
app/         # dashboard FastAPI + charts SVG + gabarit (P5)
data/        # countries + sources + scenarios + corpus_seed
tests/       # unitaires + intégration (rounds, LLM, diplomatie, RAG, données, dashboard)
docs/        # plan d'action, gouvernance des données ; (état de l'art à la racine)
```

## Prochaine étape

**Phase 6** — infra : Docker (une image par service) → docker-compose → kind/K8s ; `docs/deployment.md`. Voir `CLAUDE.md` et `docs/PLAN_ACTION_CLAUDE_CODE.md`.
