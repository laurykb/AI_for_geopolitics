# Handoff de session — reprendre sans perdre le contexte

> Écrit pour qu'une **nouvelle session Claude Code** reparte à l'identique. La mémoire projet
> (`~/.claude/.../memory/` : `vision-nord`, `dev-environment`, `prefer-interactive-ui`) se recharge
> automatiquement ; ce fichier est le **détail complet**. Dernière mise à jour : 2026-07-01.

## Le but (nord du projet)

**Pas** un dashboard qui résume une sim déterministe. Un **théâtre temps réel qui rend visibles les
boîtes noires** d'un multi-agent de **super-intelligences** (pays = agents LLM) : le Game Master génère
un événement → les pays **négocient en direct** (streamé, chacun son tour) → un **juge LLM** arbitre les
attributs → **communiqué G7** + la date avance. Métaphore : *un G7 dont on voit tous les messages*.

## Où on en est

- **Branche courante : `feat/observable-round`** (HEAD, **non poussée**) — théâtre live + Lot A + mode Fog Engine.
- **185 tests verts** (`pytest -q`, tous offline via MockBackend), `ruff` propre.
- Contrainte matérielle : **RTX 2060 Super 8 Go** → 1 modèle 7B (mistral) en local, **séquentiel**,
  ~1 min/round. Impossible de faire tourner 6 modèles en parallèle.

## Ce qui est fait (phases + slices du théâtre)

Roadmap CLAUDE.md P0→P7 : **P0** moteur déterministe · **P1** agents LLM (Ollama) · **P2** diplomatie
déterministe · **P3** RAG sourcé · **P4** données réelles (World Bank/SIPRI, + build reproductible
`ingestion/`) · **P5** interface. **P6** (Docker) = **parqué** sur `feat/p6-infra` (non fini/vérifié).

Puis **refonte vers le théâtre observable** (branche `feat/observable-round`), 4 slices :
1. **Round observable spectateur** : streaming des backends, `SimClock`+dates, `GameMasterAgent` (LLM),
   `LLMAgent.stream_deliberation`, `run_live_round` (orchestrateur → RoundStep).
2. **Négociation arbitrée** : `run_negotiation_round` (N passes, chrono+badge modèle/prise de parole),
   `JudgeAgent` (rationale streamé + verdict), `apply_verdict` (garde-fou bornant les deltas).
3. **Rôles humains** : `TurnCursor` (négociation pilotable tour par tour), UI machine à états —
   **Spectateur / Game Master humain / Joueur-pays** (à son tour la table PAUSE → saisie → reprise).
4. **Réalisme** (triage d'un gros brainstorm, on écarte les conseillers multi-agents = trop d'appels) :
   **prompt profilé** (négocie depuis la vraie fiche CountryState + penchant), **mémoire par pays**
   (`WorldState.country_memory`), **perception/fog of war** (`simulation/perception.py`),
   **communiqué G7** (juge) + `support_levels`. Tout déterministe **sauf** le communiqué (+1 appel/round).

**Lot A LIVRÉ** (réalisme + instrumentation, 3 commits atomiques sur la même branche) :
- **Slice 5 — raisonnement privé visible** : chaque pays « pense à voix haute » puis parle en UNE
  génération (marqueur `MESSAGE:`, `split_reasoning`) ; UI = expander « 🧠 Réflexion privée » streamé,
  séparé de la bulle publique ; budget négociation 180→360 tokens.
- **Slice 6 — prise de parole dynamique** : `simulation/engagement.py` (`engagement_score` déterministe :
  acteur/tension/interpellation/tempérament/fatigue/jitter) + `TurnDirector` (dans `negotiation.py`,
  `next_speaker`/`commit`/`silent`, `max_turns`) remplacent le round-robin figé. Un pays peut reparler,
  couper la file quand on l'interpelle, ou **se taire** (0 appel) s'il n'est pas concerné. `ParticipationStep`.
- **Slice 7 — LLM Budget Dashboard** : `inference/telemetry.py` (`BudgetLedger`+`CallRecord`, contexte
  round/rôle/pays, 9 indicateurs/round + `by_country`), `inference/pricing.py` (local≈0$ + équivalent
  frontière Claude), `inference/metered_backend.py` (`MeteredBackend` : cache de prompts, JSON valide,
  estimation tokens en streaming). UI = onglet `st.tabs` « 💸 LLM Budget ». Vérifié live (Ollama/mistral).
**Modes de jeu LIVRÉS** (dimension orthogonale aux 3 rôles ; sélecteur « Mode de jeu » en sidebar) :
- **Fog Engine** (2 commits) : chaque pays réagit à ce qu'il **croit** voir, pas à la vérité. `PerceivedEvent`
  enrichi (suspected_actor/narrative/delay_hours/authored) ; `simulation/fog.py` (`FogScenario`,
  `resolve_perception` = fournie > uninformed > `perceive`, `load_fog_scenarios`) ; prompt **belief-aware**
  (montre la croyance, masque la vérité si authored) ; `stream_negotiation_message(perceived=…)` ;
  `run_negotiation_round(fog=…)` ; `data/fog/*.json`. UI : **Spectateur omniscient** (vérité + panneau
  perceptions, désinfo ⚠️/uninformed), **Joueur-pays aveugle** (voit UNIQUEMENT sa perception), **GM** auteur
  du fog. Juge = arbitre omniscient. Vérifié live (china croit « faux drapeau US »).
- **Crisis Replay** (2 commits) : rejouer une crise passée + comparer l'issue simulée à l'issue historique
  (déterministe, explicable). `simulation/crisis.py` (`Crisis` = événement(s) + `HistoricalOutcome` {résumé,
  escalade, mesures} ; `load_crises` ; `compare_outcome` = écart d'escalade + mesures retrouvées/manquées +
  explication) ; `data/crises/*.json` (hormuz_energy_shock, tech_sanctions, satellite_interference). UI : mode
  « Crisis Replay », selectbox crise (3 rôles), rejouable, panneau « 🕰️ Simulé vs historique » en fin de round.
- **Escalation Ladder** (2 commits) : échelle 0-9 + plafond atteignable par pays (déterministe).
  `simulation/escalation.py` (`LADDER`, `EscalationProfile` = 5 curseurs dérivés de CountryState surchargeables,
  `ceiling` = jusqu'où un pays peut monter, `reached_rung`, `rung_label`). UI = **overlay** du round négocié
  (réutilise le provisionnement classique/GM) : panneau échelle (5 params + plafond/label par pays + échelon
  atteint ce round). Vérifié live (egypt plafond 0, usa élevé).
- **À faire (décidé)** : **budget modes** Cheap/Balanced/Full = un sélecteur pilotant `TurnDirector.max_turns`
  (au-delà du budget, silence déterministe).
- **Raffinement noté** : en Fog, `engagement_score`/urgence du mandat se basent sur les VRAIS acteurs ; à terme,
  pondérer par la perception (un pays accusé/se croyant visé devrait plus parler).

**Réalisme G7 LIVRÉ** (contexte apporté par l'user sur le fonctionnement d'un vrai G7, 2 commits, 0 appel LLM en plus) :
- **Fiche de comportement (mandat)** : `simulation/mandate.py` (`CountryMandate`, `derive_mandate` déterministe —
  ligne rouge, priorités, concessions, contraintes internes, urgence ; dérivée de `CountryState`, **surchargeable**
  via le champ optionnel `CountryState.mandate`) ; injectée dans `build_negotiation_prompt` (bloc « FEUILLE DE ROUTE »).
- **Bilatérale informelle** : `NEGOTIATION_SYSTEM` demande d'envisager une entente hors-table avec UN pays précis, qui
  influence le message **sans être déclarée** — reste dans la pensée privée (box 🧠, invisible des autres agents).
- **Communiqué G7 réaliste** : `COMMUNIQUE_SYSTEM` = déclaration politique **non contraignante**, position commune +
  2-3 mesures coordonnées envisagées ; le G7 aligne/coordonne/prépare (n'impose pas).

## Architecture (modules)

- `core/` : domaine Pydantic (`CountryState` (+`mandate` optionnel), `WorldState` (+`country_memory`),
  `GeoEvent` (+`date`), `AgentDecision`, `DiplomaticMessage`, `RoundSummary`) + moteurs `consequences`,
  `risk`, `rounds`.
- `agents/` : `base_agent`, `rule_based_agent`, `llm_agent` (JSON validé, `stream_deliberation`,
  `stream_negotiation_message` (+`perceived`), `model_tag`), `human_agent`, `game_master` (GM LLM), `judge`
  (`stream_rationale`/`verdict`/`stream_communique`), `prompts` (prompts + `_profile_brief` + FEUILLE DE
  ROUTE/bilatérale + communiqué G7 réaliste + perception belief-aware).
- `inference/` : `InferenceBackend` (+`stream_generate`), `OllamaBackend`, `MockBackend`, `bench` ;
  **`telemetry`** (`BudgetLedger`, `CallRecord`, `RoundBudget`, `grounding_proxy`), **`pricing`**
  (barème + équivalent frontière), **`metered_backend`** (`MeteredBackend` = enveloppe mesurée + cache).
- `simulation/` : `action_space`, `diplomacy` (P2), `clock`, `loader`, `perception` (`PerceivedEvent`
  +suspected_actor/narrative/delay_hours/authored), **`fog`** (`FogScenario`, `resolve_perception`,
  `load_fog_scenarios` — Fog Engine), **`crisis`** (`Crisis`, `HistoricalOutcome`, `load_crises`,
  `compare_outcome` — Crisis Replay), **`escalation`** (`LADDER`, `EscalationProfile`, `ceiling`,
  `reached_rung` — Escalation Ladder), **`mandate`** (`CountryMandate`, `derive_mandate` — fiche de
  comportement), **`engagement`** (`engagement_score`, `SPEAK_THRESHOLD`),
  `negotiation` (NegotiationMessage +`reasoning`, `split_reasoning`, Verdict, `apply_verdict`, `TurnCursor`,
  **`TurnDirector`**, `speaking_order`, `update_memories`, `support_levels`, `AttributeDelta`), `live_round`
  (RoundStep +`ParticipationStep` + `run_live_round` + **`run_negotiation_round`** = orchestrateur
  headless/tests, `ledger`/`fog` optionnels).
- `rag/` (P3), `ingestion/` (P4), `app/` (backend FastAPI `/health`+`/api/run`),
  `ui/` : **`ui/app.py`** = théâtre live (machine à états, c'est L'UI) ; `ui/game.py` = `GameSession` (legacy P5, encore testé).

**Le round live (UI)** : l'UI pilote **tour par tour** (un tour = un rerun Streamlit, pour permettre la
pause joueur-pays) ; elle appelle directement `stream_negotiation_message`, `JudgeAgent`, `apply_verdict`,
`update_memories`, `stream_communique`. `run_negotiation_round` (générateur) sert le headless + les tests.

## Décisions clés / renversements (à ne pas ré-ouvrir sans raison)

- **Attributs fixés par le JUGE LLM** (interprète comme un G7, non déterministe) ; le moteur déterministe
  = **garde-fou** (bornes). Renverse le « tout déterministe » initial.
- **Streamlit** pour l'UI interactive (pas HTML statique — 1er dashboard P5 jugé « faute technique »).
- **K8s + MCP** = substrat distribué, **reporté** (sur 8 Go ne parallélise pas ; on construit en in-process).
- **« Plus réel sans complexifier »** : privilégier les ajouts déterministes ~0 appel LLM ; refuser ce qui
  multiplie le coût (ex. délégation Leader/Sherpa/6-conseillers = 30-40 appels/round).

## Lancer / tester

```bash
py -3.11 -m venv .venv                    # (déjà fait : .venv existe)
./.venv/Scripts/python.exe -m pip install -e ".[ui,rag]"
./.venv/Scripts/python.exe -m pytest -q   # 123 tests, offline
./.venv/Scripts/python.exe -m ruff check .
# App (nécessite Ollama lancé + `ollama pull mistral`) :
./.venv/Scripts/python.exe -m streamlit run ui/app.py    # http://localhost:8501
```
Ollama 0.31.1 installé, modèles présents : `mistral:latest` (défaut), `llama3.2:3b`, `bge-m3`.
Preview via l'outil `.claude/launch.json` (configs `ui` port 8501, `api` port 8000).

## État Git

- **Poussées** (upstream origin) : `feat/p1-llm-agents`, `feat/p2-diplomatie`, `feat/p3-rag`,
  `feat/p4-data`, `feat/p5-dashboard`. `main` = P0.
- **NON poussées** : `feat/p6-infra` (Docker parqué), **`feat/observable-round`** (tout le théâtre —
  la branche qui compte). Remote : `github.com/laurykb/AI_for_geopolitics`.
- **À faire un jour** : pousser `feat/observable-round` + ouvrir les PRs (empilées). L'user ne veut pas
  push automatiquement — demander.

## Prochaines pistes (au choix de l'user)

- **Budget modes (prochain, décidé)** Cheap(1)/Balanced(3)/Full(all) = un sélecteur pilotant
  `TurnDirector.max_turns` (déjà en place) ; au-delà du budget, silence déterministe.
- Puis substrat distribué **K8s + MCP** ; raffinements (engagement/urgence pondérés par la perception en Fog).
- **Affiner** : engagement pondéré par la perception en Fog ; animer les deltas d'attributs.
- Dernier morceau de la vision : **K8s + MCP** (agents-services échangeant en langage naturel).

## Manière de travailler (attendue)

Français. **Plan mode → validation → TDD → commits atomiques** par feature (playbook
`docs/PLAN_ACTION_CLAUDE_CODE.md`). L'user corrige quand on rate l'**intention expérientielle** (il veut
que ça se **joue** et que ça soit **réaliste**), pas juste la DoD littérale. Commits `Co-Authored-By: Claude`.
