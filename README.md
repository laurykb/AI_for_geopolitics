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

## Structure

```
core/        # modèles de domaine + moteurs (conséquences, risque, rounds)
agents/      # base_agent + rule_based_agent (P0) + prompts + llm_agent (P1)
inference/   # InferenceBackend + OllamaBackend / MockBackend + bench (P1)
simulation/  # action_space
data/        # countries/*.json + scenarios/red_sea.json
tests/       # unitaires + intégration (rounds rule-based ET LLM)
docs/        # plan d'action ; (état de l'art à la racine)
```

## Prochaine étape

**Phase 2** — diplomatie : messages bilatéraux, alliances, accept/refuse, résumé public (voir la roadmap dans `CLAUDE.md` et `docs/PLAN_ACTION_CLAUDE_CODE.md`).
