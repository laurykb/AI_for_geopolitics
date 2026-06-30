# AI for Geopolitics

Simulation géopolitique **agentique** : des pays-agents, contraints par des données réelles, réagissent par **rounds** sous un **Game Master** ; RAG sourcé + moteur de risque explicable. Double objectif : un système crédible **et** un vecteur d'apprentissage d'AI Engineer.

> Voir `docs/` pour l'**état de l'art** et le **plan d'action Claude Code**, et `CLAUDE.md` pour le guide projet.

## Phase 0 — moteur déterministe (sans LLM) ✅

La boucle de simulation tourne déjà, **sans aucun LLM** :

- **Modèles de domaine** (Pydantic) : `CountryState`, `WorldState`, `GeoEvent`, `AgentDecision`, `RoundSummary`.
- **Espace d'action** + **agent rule-based** (heuristique reproductible, même interface `Agent` que le futur `LLMAgent`).
- **Moteurs** : conséquences déterministes, risque explicable (escalade, perturbation éco, fracture d'alliance), round engine.
- **Scénario seed** : crise de la **mer Rouge**, 6 acteurs (USA, Chine, France, Égypte, Iran, Arabie saoudite), 3 événements.

## Installation & tests

```bash
python -m venv .venv
# Windows : .venv\Scripts\activate   |   Linux/macOS : source .venv/bin/activate
pip install -e . pytest ruff
ruff check .
pytest -q
```

## Structure

```
core/        # modèles de domaine + moteurs (conséquences, risque, rounds)
agents/      # base_agent (interface) + rule_based_agent (P0)
simulation/  # action_space
data/        # countries/*.json + scenarios/red_sea.json
tests/       # unitaires + intégration (un round complet)
docs/        # plan d'action ; (état de l'art à la racine)
```

## Prochaine étape

**Phase 1** — agents LLM + **service d'inférence Python** (FastAPI + llama-cpp-python), sortie JSON validée. Cette phase nécessite le GPU et se fait dans **Claude Code sur ta machine** (voir `docs/PLAN_ACTION_CLAUDE_CODE.md`).
