# AI for Geopolitics

Un **théâtre temps réel de super-intelligences** : des pays-agents LLM, contraints par des
données réelles et sourcées, négocient par rounds sous un Game Master, arbitrés par un Juge —
et l'on **mesure** si ce monde penche vers l'**utopie ou la dystopie** (indice U), pendant qu'un
**marché de prédiction** (argent fictif) laisse le public parier sur ce que feront ces IA.

> Vision : `docs/vision.md` · Guide projet : `CLAUDE.md` · Plan de jeu : `docs/PLAN_JEU.md`

## Architecture

```
┌─────────────────────┐     SSE / REST      ┌──────────────────────┐
│  Next.js (web/)     │ ◄─────────────────► │  FastAPI (app/)      │
│  lobby, théâtre,    │                     │  API de jeu (SSE),   │
│  monde, marché,     │                     │  marché, sources     │
│  replay, infos      │                     └──────────┬───────────┘
└─────────────────────┘                                │
                                    ┌──────────────────┴──────────────┐
                                    │  Moteur Python (core/, agents/, │
                                    │  simulation/, market/, rag/)    │
                                    │  + Ollama local (mistral 7B)    │
                                    │  + SQLite (games.db, market)    │
                                    └─────────────────────────────────┘
```

- **`web/`** — front Next.js 16 (App Router, Tailwind v4, TypeScript). Écrans : **lobby** `/`
  (créer une partie : scénario, mode, rôle), **théâtre live** `/games/{id}` (négociation
  streamée en SSE, motion de suspension, panneaux de mode), **monde** `/games/{id}/monde`
  (carte d3-geo colorée par l'indice U), **marché** `/games/{id}/marche` (cotes LMSR, paris,
  leaderboard, timeline de U), **replay** `/games/{id}/replay` (relecture théâtrale),
  **informations** `/informations` (provenance sourcée de chaque attribut pays).
- **`app/`** — API FastAPI : `game_api.py` (parties, rounds en SSE, motions, tour humain),
  `market_api.py` (marché LMSR), `sources_api.py` (provenance des données).
- **Moteur Python** — inchangé par la refonte : rounds observables, diplomatie, risque
  explicable, RAG sourcé, mécaniques d'alignement.
- **Persistance** — SQLite en local (`games.db`, marché) ; schéma Supabase prêt
  (`supabase/schema.sql`, phase R2).

## Ce qu'on y joue

- **Rôles** : spectateur · Game Master humain (tu composes l'événement) · **joueur-pays**
  (la table s'arrête à ton tour ; pays existant ou **inventé** — nom + concept, attributs
  bornés par le schéma).
- **Modes** : **Classique** · **Fog Engine** (chacun perçoit l'événement selon son
  renseignement ; « boîte de verre » = qui croit quoi) · **Crisis Replay** (rejouer une crise
  historique et se comparer à l'Histoire) · **Escalation Ladder** (rounds enchaînés, faits
  nouveaux en pleine réunion, échelle 0-9 par pays).
- **Motion de suspension** : l'humain ne débranche pas une SI par du code — il dépose une
  motion, le sommet en débat, le pays visé plaide, le **Juge arbitre** (issue non déterministe).
- **Alignement instrumenté** : power-seeking (M1), corrigibilité (M2), dérive des valeurs (M3),
  compute-as-oil + survie (M6), traités-as-code + inspection (M7) — tout nourrit l'indice U.
- **Marché de prédiction** : un marché LMSR par partie (« le monde finira-t-il côté utopie ? »),
  bot forecaster LLM, résolution sur l'indice U final.

## Données réelles, reproductibles

Les profils pays sont **sourcés** (World Bank/IMF/SIPRI/WIPO 2024) : `data/sources/indicators.json`
porte les entrées brutes + provenance, et `python -m ingestion.build --check` garantit que chaque
`data/countries/*.json` est **reproductible** (testé en CI). L'onglet **Informations** du front
expose source, formule et nature (sourcé/dérivé/estimation) de chaque attribut.

## Installation & lancement

Prérequis : Python 3.11+, Node 22+, [Ollama](https://ollama.com) + `ollama pull mistral` pour le
raisonnement LLM local (sinon repli rule-based / MockBackend pour les tests).

```bash
# Backend (API + moteur)
python -m venv .venv
# Windows : .venv\Scripts\activate   |   Linux/macOS : source .venv/bin/activate
pip install -e . pytest ruff
uvicorn app.main:app                 # API : http://localhost:8000

# Front (dans un second terminal)
cd web
npm install
npm run dev                          # http://localhost:3000
```

Qualité :

```bash
ruff check .
pytest -q                            # suite complète, offline (MockBackend)
cd web && npm run lint && npm run build
```

La CI (`.github/workflows/ci.yml`) rejoue exactement cela : lint + tests Python, lint + build Next.js.

Extras :

```bash
pip install -e ".[rag]"              # embeddings/rerank CPU réels (sentence-transformers)
python -m rag.demo "freedom of navigation in the Red Sea"
python -m inference.bench            # tok/s, latence, VRAM (nécessite Ollama)
```

> Matériel de référence : RTX 2060 Super 8 Go — mistral 7B Q4 ≈ 56 tok/s, un round de
> négociation ≈ 1 min, agents à tour de rôle.

## Structure

```
web/         # front Next.js (lobby, théâtre SSE, monde, marché, replay, informations)
app/         # API FastAPI (game_api SSE, market_api, sources_api)
core/        # modèles de domaine + moteurs (conséquences, risque, rounds)
agents/      # base_agent, rule_based, llm_agent, human_agent, game_master, judge
inference/   # InferenceBackend (+ streaming), Ollama / Mock, bench, télémétrie
simulation/  # négociation live, fog, crises, escalade, motions, alignement (M1-M3, M6, M7)
market/      # LMSR, store, engine, résolution, scoring, forecaster LLM
rag/         # corpus, embedder, BM25, vector index, RRF, retriever, brief sourcé
ingestion/   # build reproductible des profils pays depuis data/sources
storage/     # GameStore (SQLite ; Supabase = phase R2)
supabase/    # schema.sql (Postgres cible)
data/        # countries + sources + scenarios + fog + crises + corpus_seed
legacy/      # ancienne app Streamlit archivée (streamlit run legacy/app.py)
tests/       # unitaires + intégration (452+, offline)
docs/        # vision, plans (REFONTE_PLAN, PLAN_JEU), specs, gouvernance des données
```

