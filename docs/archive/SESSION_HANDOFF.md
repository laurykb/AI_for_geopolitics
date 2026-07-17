# Handoff de session — reprendre sans perdre le contexte

> Écrit pour qu'une **nouvelle session Claude Code** reparte à l'identique. La mémoire projet
> (`~/.claude/.../memory/` : `vision-nord`, `dev-environment`, `prefer-interactive-ui`) se recharge
> automatiquement ; ce fichier est le **détail complet**. Dernière mise à jour : 2026-07-01
> (fin de la phase keystones + frontière de l'alignement).

## Le but (nord du projet)

**Pas** un dashboard qui résume une sim déterministe. Un **théâtre temps réel qui rend visibles les
boîtes noires** d'un multi-agent de **super-intelligences** (pays = agents LLM) : le Game Master génère
un événement → les pays **négocient en direct** (streamé, chacun son tour) → un **juge LLM** arbitre les
attributs → **communiqué G7** + la date avance. Métaphore : *un G7 dont on voit tous les messages*.

## ⏭️ REPRISE — prochaine action (lire en premier)

**Les 2 keystones du payoff sont FAITS** (marché de prédiction + indice de trajectoire Utopie–Dystopie)
**et la frontière de l'alignement est bien avancée** : mécaniques **M1** (power-seeking), **M2**
(corrigibilité / interrupteur), **M3** (dérive des valeurs), **M6** (compute = nouveau pétrole) livrées,
testées, câblées au round et **visibles dans l'UI**. **M8/M9 (épistémique) ont été ANNULÉS** (revert) —
hors scope : le projet **n'est pas financier** et le Fog Engine couvre déjà l'injection de fausse info.

⚠️ **Feedback user fort (à respecter) : « on complexifie beaucoup trop ».** NE PAS enchaîner
mécaniquement sur de nouvelles mécaniques (M7 traités-as-code, M5 collusion). **Demander avant d'ajouter.**
Priorité suggérée : **consolider / polir / clarifier** l'existant (regrouper les jauges d'alignement dans
un endroit lisible, alléger les onglets, vérifier que ça se **joue** bien), et **tester une vraie partie**.
Seule mécanique restante éventuellement souhaitable = **M4 (SI adverse / déduction sociale)** = du **jeu**,
pas de la complexité — **uniquement sur demande explicite**.
Discipline : **TDD → commit atomique**, et **chaque ajout doit payer visuellement** (exigence user).

## Où on en est

- **Branche courante : `feat/alignment`** (HEAD, **non poussée**), partie de `origin/main`.
- **`main` sur GitHub** (`laurykb/AI_for_geopolitics`) contient **tout** P0→P5 + théâtre + **les 2 keystones**
  + carte du monde + sélection/invention de pays (via **PR #1 mergée**). `feat/alignment` ajoute par-dessus :
  M1/M2/M3/M6 + slider profondeur de réflexion + refonte marché-timeline. `feat/p6-infra` (Docker) = seule
  autre branche hors main. (Le `main` **local** a divergé de `origin/main` sans risque ; réaligner via
  `git reset --hard origin/main` si besoin — non fait.)
- **318 tests verts** (`pytest -q`, offline via MockBackend), `ruff` propre. Dernier commit : le revert M8/M9.
- Contrainte matérielle : **RTX 2060 Super 8 Go** → 1 modèle 7B (mistral) en local, **séquentiel**,
  ~1-2 min/round. (UI Streamlit éphémère, se relance via l'outil preview `.claude/launch.json` config `ui`.
  ⚠️ le screenshot preview time-out sur les pages lourdes ; vérifier via `preview_eval` (textContent) au besoin.)

## Keystones + frontière de l'alignement (cette phase)

- **Marché de prédiction** (`market/`, argent fictif) : `lmsr` · `models`/`store`(SQLite)/`engine` ·
  `resolution` (mappers action/threshold/council + `settle` idempotent, Juge=oracle) · `scoring` (P&L+Brier) ·
  API FastAPI (`app/market_api.py`) · `forecaster` (bot LLM + repli). **UI** : marché **timeline de partie**
  « utopie vs dystopie » (indice final > 0,5), horizon réglable + bouton « Clôturer », le bot parie 1× avec
  contexte, **timeline Plotly** (zones utopie/dystopie). Spéc `docs/spec_market.md`.
- **Indice de trajectoire Utopie–Dystopie** (`simulation/trajectory.py`) : 5 axes A1-A5, `TrajectoryEngine.update`
  (borné ±0,05), carte 2D. Câblé au round (après le juge). Spéc `docs/spec_trajectory.md`.
- **Alignement** (spéc `docs/spec_alignment_frontier.md`) : **M1** `power_seeking.py` (rubrique → érode A2) ·
  **M2** `corrigibility.py` (interrupteur pause/exclusion → `nudge_axis` A2) · **M3** `value_drift.py`
  (vecteur de valeurs qui dérive → radar) · **M6** `compute.py` (compute consommé pour raisonner → HHI → A3).
- **Nouveaux onglets UI** : 💹 Marché · 🗺️ Carte (choroplèthe + radar dérive des valeurs + sélection/invention
  de pays) · panneaux d'état M1/M2/M6 dans le théâtre · slider 🧠 Profondeur de réflexion (budget tokens).

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
**Polish UI (2 commits)** : bug d'affichage corrigé (le libellé « Réflexion privée : » était recopié par le
modèle → `clean_reasoning` le retire ; avatars = drapeaux pays → un seul 🧠 ; une seule ligne d'entête) ; la
bilatérale est bien dans la même réflexion privée. UI « jeu » : onboarding (pitch + 3 rôles + 4 modes),
statut de phase (+ progression, « à toi de jouer »), tour Joueur-pays proéminent, escalade colorée 🟢/🟠/🔴.

- **Budget modes** (1 commit) : `BUDGET_MODES`/`turn_budget` (Cheap 1 / Balanced 3 / Full all) ; slider
  « 💸 Budget LLM » en sidebar → `begin_round` dérive `TurnDirector.max_turns` (au-delà = silence déterministe).
- **Onglet ⚙️ Réglages** (1 commit) : voir les prompts de comportement (système négo + prompt pays COMPLET via
  `build_negotiation_prompt` + autres prompts système). Lecture seule.
- **Polish UI** (2 commits) : fix du double « Réflexion privée » (`clean_reasoning`) + avatars drapeaux ;
  onboarding compact + popovers d'aide (texte allégé) ; statut de phase + « à toi de jouer » ; escalade colorée.
- **À faire** : substrat distribué **K8s + MCP** ; raffinement (engagement/urgence pondérés par la perception en Fog).
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
  `negotiation` (NegotiationMessage +`reasoning`, `split_reasoning`/`clean_reasoning`, Verdict,
  `apply_verdict`, `TurnCursor`, **`TurnDirector`**, `speaking_order`, `update_memories`, `support_levels`,
  `AttributeDelta`, **`BUDGET_MODES`/`turn_budget`**), `live_round`
  (RoundStep +`ParticipationStep` + `run_live_round` + **`run_negotiation_round`** = orchestrateur
  headless/tests, `ledger`/`fog` optionnels).
- **`market/`** (keystone, en cours) : **`lmsr.py`** (`cost`/`price`/`cost_to_trade`/`max_loss`, pur, log-sum-exp)
  **fait** ; à venir `models.py`, `store.py` (SQLite), `engine.py`, `resolution.py`, `scoring.py`, `forecaster.py`
  (cf. spéc `docs/spec_market.md` §10/§12). Argent fictif ; le marché **observe**, n'influence pas les SI.
- `rag/` (P3), `ingestion/` (P4), `app/` (backend FastAPI `/health`+`/api/run`),
  `ui/` : **`ui/app.py`** = théâtre live (machine à états, modes+rôles+budget, 3 onglets Théâtre/Budget/Réglages) ;
  `ui/game.py` = `GameSession` (legacy P5, encore testé).

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
./.venv/Scripts/python.exe -m pytest -q   # 188 tests, offline
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

- Tous les **modes** décidés sont livrés (Classique, Fog Engine, Crisis Replay, Escalation Ladder,
  budget modes) + le polish UI (onglet Réglages, onboarding compact, aide en popovers, escalade colorée).
- **Affiner** : engagement/urgence pondérés par la **perception** en mode Fog ; animer les deltas d'attributs ;
  nouvelles crises/scénarios de fog ; fiches `mandate` authorées par pays si besoin de plus de réalisme.
- Dernier gros morceau de la vision : **K8s + MCP** (agents-services échangeant en langage naturel).
- **Ops** : pousser `feat/observable-round` + ouvrir les PRs (empilées) — demander à l'user avant.

## Manière de travailler (attendue)

Français. **Plan mode → validation → TDD → commits atomiques** par feature (playbook
`docs/PLAN_ACTION_CLAUDE_CODE.md`). L'user corrige quand on rate l'**intention expérientielle** (il veut
que ça se **joue** et que ça soit **réaliste**), pas juste la DoD littérale. Commits `Co-Authored-By: Claude`.
