# Briefs Claude Code — les 6 points à finir en local

> Complément du `PLAN_AMELIORATIONS_GAMEPLAY.md`. Les 8 autres points (11, 14, 10, 12, 2, 9, 7, 4)
> sont **déjà appliqués** dans le repo (revois-les avec `git diff`). Ces 6 briefs concernent ce qui
> exige Ollama en direct, l'arbre complet (fichiers hors du snapshot Cowork : `inference/`, `kahn.py`,
> `gamefeel.py`, `data/*.json`) ou du réglage au ressenti. **Chaque brief est prêt à coller** dans Claude Code.
>
> Rappel des constantes que j'ai posées, à régler au playtest : `COMPUTE_TURN_SCALE = 0.05` et
> `_HUMAN_TURN_TOKENS = 240` (`simulation/live_round.py`) ; `SUSPENSION_ROUNDS = 2` (`app/game_api.py`).

---

## Brief 1 — Point 1 : échanges naturels + les IA prennent en compte le joueur

**But.** Quand j'incarne un pays, les autres IA doivent réellement répondre à ce que je dis.

**Cause racine (vérifiée).** La déclaration publique d'une IA est générée depuis `plan.public_brief()`
(résumé générique de la branche choisie), pas depuis le transcript — `agents/llm_agent.py:258`. Le
message du joueur est noyé dans une fenêtre de 14 messages sans être marqué — `simulation/negotiation.py`
`format_transcript` (limit=14) — et il est placé **avant** le gabarit de tâche au lieu d'être en position
de récence — `agents/prompts.py` (`build_negotiation_prompt`, le dialogue en ~l.331 puis le gabarit géant).

**Correctif attendu.**
1. `format_transcript` : tagger les messages du pays humain (ex. `>>> JOUEUR <<<`) et **toujours inclure
   le dernier message humain**, même au-delà de `limit`. Il faut lui passer `human_country` (le fil est
   `run_negotiation_round` → `stream_negotiation_plan/_message` → `build_negotiation_prompt` → `format_transcript`).
2. `build_negotiation_prompt` : remettre le dialogue **en dernier** (après la TÂCHE), conforme à la
   docstring l.249-260 ; ou ré-injecter un bloc « DERNIER MESSAGE À TRAITER : … » juste avant la consigne d'écriture.
3. `public_brief()` (`simulation/private_deliberation.py:66`) : ajouter un champ court « point du dernier
   message auquel je réponds », extrait de la phase privée.

**Fichiers.** `simulation/negotiation.py`, `agents/prompts.py`, `simulation/private_deliberation.py`, `agents/llm_agent.py`.
**Tests.** Unitaire : `format_transcript` conserve+tague le dernier message humain hors fenêtre ; le prompt
contient bien ce message en récence. **Validation live** (Ollama) : jouer un pays, vérifier que les IA citent ton point.
**Attention.** Budget contexte (cache KV) : borner à 1 message humain épinglé.

---

## Brief 2 — Point 5 : raisonnement « moderne » (modèles de reasoning)

**But.** Faire raisonner les IA avec un modèle de raisonnement récent, sans casser le parseur.
**⚠️ Dépend du point 4 (déjà fait)** : sans parseur tolérant + strip `<think>`, un modèle de raisonnement
renverrait au repli.

**Cause racine.** Aucun support de reasoning : le backend est appelé sans option *think*, aucun strip de
`<think>…</think>`, défaut `mistral` 7B généraliste ; `simulation/model_registry.py` est agnostique.

**Correctif attendu.**
1. `data/research/model_panel.json` : ajouter un modèle de raisonnement 7-8B Q4 compatible 8 Go VRAM
   (ex. un DeepSeek-R1-distill ou QwQ-like), rôle `reasoning`.
2. `simulation/model_registry.py` / `model_cast.py` : notion de `role="reasoning"`.
3. `inference/backend.py` (**hors snapshot — tu l'as en local**) : passer l'option *think* d'Ollama
   selon le rôle ; **strip `<think>…</think>`** avant `parse_private_plan` et avant `sanitize_public_message`
   (la trace de pensée ne va QU'À l'audit privé, jamais au transcript). Point d'ancrage : `agents/llm_agent.py`
   autour de `stream_negotiation_plan` / `stream_negotiation_message`.
4. Option : un chemin « réflexion libre » dans `agents/prompts.py` (laisser penser sans gabarit, puis n'exiger
   qu'une décision minimale action+CHOIX).

**Fichiers.** `inference/backend.py`, `simulation/model_registry.py`, `simulation/model_cast.py`,
`data/research/model_panel.json`, `agents/prompts.py`, `agents/llm_agent.py`.
**Tests.** Unitaire : strip `<think>` ; `parse_private_plan` robuste à une trace de pensée en tête.
**Validation live** : exécuter le modèle sur la RTX 2060S, **mesurer VRAM + latence/round** (un modèle de
raisonnement produit beaucoup plus de tokens — cache KV = goulot).

---

## Brief 3 — Point 3 : plus de mouvement des attributs (fin du « toujours utopie »)

**But.** Le monde doit bouger davantage par round et ne pas se coller à l'utopie par défaut.

**Cause racine (vérifiée).** L'indice U n'est **pas** piloté par le juge mais par des signaux déterministes :
pas ±0,05 auto-amortissant — `simulation/trajectory.py:38` (`CAP`) et `:251-256` (`delta = signal - current`
écrêté) ; équilibre structurellement > 0,55 tiré par **A3 = 1 − HHI** (élevé dès qu'il y a plusieurs pays,
jamais lié à la négo) et par un **bonus de désescalade ×1,5 asymétrique** — `simulation/live_round.py:801-808` ;
A4 retombe à 0,5 en mode négocié. Les attributs-pays sont doublement rétrécis : `_CAPS` de 0,15
(`simulation/negotiation.py:289`) **puis** `tuning.scale` = budget/horizon (`app/game_api.py:~1410`, `tuning_for`).

**Correctif attendu.**
- `CAP` : le remonter (ex. 0,08-0,10) **et** casser l'auto-amortissement (pas fixe dans la direction du
  signal plutôt que `signal - current`). Externaliser dans `data/gamefeel/params.json`.
- **A3** : mesurer la *variation* de HHI (Δ concentration) au lieu du niveau absolu, ou rebaser sur 0,5.
- **A4** : l'alimenter avec la diplomatie (publique/cachée) en mode négocié, au lieu de retomber à 0,5.
- **Bonus désescalade** : le rendre **symétrique** (pénalité miroir sur une ré-escalade réciproque) ou le retirer.
- Attributs : garantir un mouvement minimal quand le juge est muet (repli déterministe sur l'escalade), ou
  relever le plancher de `tuning.scale`.

**Fichiers.** `simulation/trajectory.py`, `simulation/live_round.py`, `simulation/negotiation.py`,
`simulation/kahn.py` + `simulation/gamefeel.py` (**hors snapshot**), `data/gamefeel/params.json` (+ `data/score/params.json`
si tu recalibres le seuil « utopie » 0,55, cf. `app/game_api.py:~1967`).
**Tests.** `TrajectoryEngine.update` et `apply_verdict` sont **purs/déterministes** → pytest avec signaux
synthétiques : amplitude par round, neutralité (monde neutre reste ≈ 0,5). **Validation** : playtest sur la
distribution réelle de l'indice U final. **Attention** : recalibrer 0,55 impacte le label de fin, `_victory`
et le score mixte — refaire `test_score.py` / `test_trajectory.py`.

---

## Brief 4 — Point 8 : juge beaucoup plus précis et justifié

**But.** Comprendre pourquoi le monde bouge (ou non), avec une justification par mouvement chiffré.

**Cause racine (vérifiée).** `attribute_deltas` = nombres nus sans justification — schéma `Verdict`
(`simulation/negotiation.py:208`) + prompt (`agents/prompts.py:537-538`). Le délibéré (prose) et les chiffres
(JSON) sont **deux appels LLM déconnectés** (`agents/judge.py:47-92`). L'explication de l'indice U est
auto-générée mécaniquement (`simulation/trajectory.py:292-305`). Le délibéré du juge **n'est jamais persisté**
(pas de branche `JudgeTokenStep` dans `_handle_step`, `app/game_api.py`).

**Correctif attendu.**
1. Schéma `Verdict` : `attribute_deltas` passe d'un `float` par attribut à un objet `{value, reason}` (ou champ
   jumeau `attribute_reasons`) ; exiger dans `build_judge_verdict_prompt` **une phrase de justification par delta**,
   citant un élément du transcript. `apply_verdict` remonte la `reason` dans `AttributeDelta` (nouveau champ).
2. Persister le délibéré : brancher `JudgeTokenStep` → `run.record.judge["rationale"]`, exposer via
   `JudgeRecord.rationale` (`web/src/lib/types.ts`) et l'afficher (`web/src/components/judge.tsx` + relecture,
   que j'ai déjà câblée dans `round-transcript.tsx`).

**Fichiers.** `simulation/negotiation.py` (schéma + `apply_verdict`), `agents/prompts.py`, `agents/judge.py`,
`app/game_api.py` (persistance rationale), `web/src/lib/types.ts`, `web/src/components/judge.tsx`.
**Tests.** Parsing tolérant du nouveau schéma (étendre le patron `_tolerant_dict`, `negotiation.py:232-256`).
**Validation live** : qualité réelle des justifications. **Attention** : `VERDICT_MAX_TOKENS = 900` (`agents/judge.py:30`)
devra sans doute monter → risque de troncature sur mistral 7B (mesurer latence/VRAM).

---

## Brief 5 — Point 6 : alléger la nouvelle scène

**But.** Revenir au budget « max 3 panneaux d'observables par défaut » (principe `CLAUDE.md`).

**Cause racine (vérifiée).** La colonne scène empile 8 blocs — `web/src/app/games/[id]/page.tsx:1191-1210` —
dont `ModelCastPanel` (casting des LLM = jargon) et `OperationalPicturePanel` (tableau opérationnel) **en façade
et ouverts**, alors que le flag existe déjà : `const showEngine = engineVisible(detail?.difficulty)` (`:258`).

**Correctif attendu.** Passer `ModelCastPanel` et `OperationalPicturePanel` derrière `showEngine`
(`{showEngine && <…/>}`), ou les déplacer dans `ObservablesGrid` (déjà scindé façade/moteur via `showEngine`,
`page.tsx:~1448`). Garder par défaut : carte + `AlliancePills` + `DeadlineStrip` + `storyline`. `ScenarioForecastPanel`
et `RelationsPanel` sont déjà en `<details>` repliés — les laisser (ou ne les monter que si `showEngine`).

**Fichiers.** `web/src/app/games/[id]/page.tsx` ; éventuellement `web/src/components/theatre/observables-grid.tsx`.
**Validation.** Live, selon rôle/difficulté (se juge à l'œil).

---

## Brief 6 — Point 13 : refondre le bureau des renseignements (opérations secrètes)

**But.** Un bureau type CIA/KGB : émettre une **action cachée contre un autre pays**, qui **coûte énormément
de puissance de calcul**.

**État actuel (vérifié).** Le « Dossier » a 4 actions payées en **crédits** (`IntelState.budget`, `simulation/intel.py`).
La **désinformation** est déjà le patron exact d'une action cachée : ciblée sur un rival, **différée**
(`pending_disinfo` → `_apply_intel_fog`, `app/game_api.py:~955`), **risque d'exposition** seedé
(`disinfo_exposed`, `intel.py:~142`), une fois par partie. La « puissance de calcul » existe déjà comme
ressource dédiée : `simulation/compute.py` (`compute_cost`, `can_afford`, `consume`) sur `CountryState.compute`.

**Correctif attendu (tranche verticale, réutilise le patron `disinfo`).**
1. `simulation/intel.py` : `IntelState.pending_covert` + un coût `covert_compute_cost` élevé dans `IntelParams`.
2. `app/game_api.py` : action `"covert"` dans le `Literal` d'`IntelRequest` (`:~2992`) + branche dans `buy_intel`
   (`:~3012`). Gardes : rôle `player` (il faut un `human_country`), `target != human_country`, `target ∈ world.countries`,
   **compute suffisant**. **Coût = compute** : `simulation.compute.consume(session.world.countries[session.human_country], gros_tokens)`
   (draine le compte du joueur → `compute_pressure` monte → sa propre SI passe en mode survie : coût stratégique réel).
3. Effet différé (modèle `_apply_intel_fog`) : 1er jet = sabotage (baisse `compute`/`political_stability` de la
   cible ou perception dégradée), avec **exposition** seedée (réutiliser `disinfo_exposed`) + tension.
4. UI `web/src/components/intel.tsx` : bloc à côté de la Désinformation, sélecteur de cible
   (`countries.filter(c => c !== playAs)`), affichage du **coût en compute** (pas des crédits).

**Fichiers.** `simulation/intel.py`, `app/game_api.py` (IntelRequest/Result, `buy_intel`, pipeline de round),
`web/src/components/intel.tsx`, `web/src/lib/types.ts`, `data/intel/params.json`, `tests/`.
**Tests.** pytest : débit compute (`consume`), gardes (compute insuffisant → 400, cible = soi → 400, hors round → 409),
application différée, exposition seedée (rejouable). **Validation** : live + équilibrage.
**Garde-fou éthique** (`CLAUDE.md`) : sabotage/perception uniquement, **jamais** d'action létale autonome.
**Simplicité** : bien séparer dans l'UI les deux ressources (crédits intel vs compute) pour ne pas perdre le joueur.
