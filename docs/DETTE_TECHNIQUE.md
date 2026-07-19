# Dette technique — audit d'ingénierie (POLISH-3, 2026-07-15)

> Inventaire priorisé de la dette du projet ENTIER (pas seulement le diff du jour),
> dressé par la passe POLISH-3 après lecture du code, des notes de session
> (`PLAN_JEU.md`) et des schémas. **Aucun des chantiers ci-dessous n'est à faire
> « au fil de l'eau »** : chacun mérite sa session, avec tests et smoke.
>
> Échelle d'effort : **S** = ≤ ½ journée · **M** = 1-2 jours · **L** = ≥ 3 jours.
> Chaque item : description, localisation, impact, effort, recommandation,
> séquencement. Le « top 5 si on n'a qu'une journée » clôt le document.

---

## D1 — `app/game_api.py` : le monolithe (3 597 lignes) — **L**

**Description.** Le module héberge quatre responsabilités : les **sessions** en
mémoire process (Deadline, PendingTurn, GameSession, snapshot/rebuild), les
**schémas d'API** (~25 modèles Pydantic), l'**orchestration du round**
(`_start_round` → `_handle_step` → `_run_stream`, plus la fin de partie LP/XP)
et **26 endpoints**. POLISH-2 a nommé les blocs (`_choose_event`,
`_persist_verdict_sections`…) mais tout vit dans un seul fichier.

**Localisation.** `app/game_api.py`. Repères (lignes actuelles) : sessions 174-242,
schémas 243-502, SSE 503-533, reconstruction 551-770, Dérive 852-912, blocs de
round 913-1553, `_handle_step` 1554-1930, fin de partie 1930-2340, routes 2391+.

**Impact.** Vélocité (toute session touche ce fichier → conflits de merge entre
branches empilées), onboarding (il faut lire 3 600 lignes pour toucher un
endpoint), risque de régression (l'ordre sémantique de `_start_round` et l'ordre
des trames SSE sont des invariants implicites du fichier).

**Recommandation — plan de découpage (à PROPOSER, pas fait ce soir) :**

1. **PR 1 — extraction sans dépendance** : `app/game_schemas.py` (tous les
   modèles de requête/vue, zéro logique) + `app/game_sessions.py` (Deadline,
   PendingTurn, GameSession, `_snapshot_session`/`_rebuild_session`/horloge,
   bibliothèques fog/crises). Les deux n'importent que core/simulation/storage.
2. **PR 2 — l'orchestrateur** : `app/round_engine.py` (RoundRun, les blocs
   `_choose_event`…`_gm_story`, `_start_round`, `_persist_verdict_sections`,
   `_settle_due_ultimatum`, `_handle_step`, `_update_gamefeel`, `_finalize`,
   `_run_stream`). C'est ici que vivent les DEUX invariants à verrouiller par
   test AVANT le déplacement : l'ordre des blocs de `_start_round`
   (motion > conséquence > crise > décret > fog) et l'ordre des trames SSE.
3. **PR 3 — les endpoints par domaine** : `app/rounds_api.py` (create/play/turn/
   motion/directives), `app/drift_api.py` (reveal), `app/intel_api.py`,
   `app/narrative_api.py` (epilogue/publish), `app/market_bot_api.py` (bot,
   flash), `app/admin_api.py` (crises), `app/players_api.py` (players, league,
   stats, forfeit). `game_api.py` ne garde que le router qui les monte
   (rétro-compat des imports de tests : ré-exporter les symboles au besoin).

**Risques à respecter** : les imports paresseux kahn↔alignment (verdict_fields est
neutre exprès), `get_engine`/`get_store` injectés par les tests, la session dict
partagée module-level. **Séquencement** : après la vérification visuelle finale,
en tête de la prochaine série — ce découpage réduit le coût de TOUT le reste.

---

## D2 — Sorties LLM : un patron de validation à unifier et documenter — **S/M**

**Description.** Le verdict du juge est désormais durci de bout en bout
(POLISH-1/3 : `_extract_json` → validateurs `mode="before"` tolérants sur les
7 champs listes + le dict + le bool → nettoyeurs par champ → budget de sortie
dédié `VERDICT_MAX_TOKENS`). Les AUTRES sorties structurées suivent des patrons
voisins mais **jamais écrits noir sur blanc**, et l'extracteur JSON est
**copié-collé à 4 exemplaires identiques** :

| Sortie | Lieu | Patron actuel |
|---|---|---|
| Verdict juge | `agents/judge.py` | extraction + validateurs before + nettoyeurs + budget dédié (référence) |
| Événement GM | `agents/game_master.py` | `_ask` → `_coerce` validant + retry ties + repli déterministe (bon) |
| Vote de motion | `simulation/motions.py` | `_extract_json(...) or {}` → `VoteBallot.model_validate` (validateurs tolérants ?) |
| Forecaster marché | `market/forecaster.py` | `_coerce_probs` + repli uniforme (bon) — copie locale de `_extract_json` |
| Forge de pays | `simulation/country_forge.py` | validé/borné + repli — copie locale de `_extract_json` |
| Acte de dialogue | `simulation/dialogue_integrity/message.py` | copie locale de `_extract_json` |
| Communiqué / rationale / narrateur / storyteller | prose streamée | repli message d'erreur (pas de JSON — OK) |

**Impact.** Chaque nouvelle sortie structurée réinvente le patron (le bug n°2 et
le bug n°4 de POLISH-1 étaient exactement ça) ; 4 copies à maintenir.

**Recommandation.**
1. (S) Déplacer `_extract_json` dans UN module neutre sans dépendance
   (`inference/json_extract.py` — le forecaster reste découplé d'`agents/`,
   raison historique des copies) et importer partout.
2. (S) Écrire le **contrat de sortie LLM** dans `docs/` (½ page) : extraction
   partagée · validateurs `mode="before"` tolérants champ par champ (le champ
   fautif se vide, jamais l'objet) · repli déterministe · budget de tokens
   DIMENSIONNÉ sur le schéma (leçon POLISH-1 n°4 : un schéma qui grossit sans
   son budget tronque en silence).
3. (M) Passer motions/forge/dialogue au crible du contrat (test rouge par champ,
   comme POLISH-3 l'a fait pour les 3 champs anciens du Verdict).

---

## D3 — Double store SQLite/Supabase : parité de schéma à la main — **M**

**Description.** Trois définitions du même monde : `storage/game_store.py`
(11 tables, DDL SQLite inline), `market/store.py` (5 tables SQLite) et
`supabase/schema.sql` (les 16 en Postgres). S'y ajoutent deux implémentations
de requêtes (`storage/supabase_store.py`, `market/supabase_store.py`) qui
doivent rester en phase avec les stores SQLite. **Aucun outillage de
migration** (pas d'Alembic — choix assumé « simplicité d'abord »), donc chaque
colonne ajoutée doit être portée À LA MAIN aux trois endroits.

**Impact.** La classe de bugs la plus sournoise en prod : une colonne présente
en local (SQLite) et absente en ligne (Supabase) ne casse RIEN en dev ni en CI
(les tests tournent sur SQLite) — elle casse chez les joueurs.

**Recommandation.**
1. (S, prioritaire) Un **test de parité de schéma** : introspecter les DDL
   SQLite (`sqlite_master` sur un store `:memory:`) et parser
   `supabase/schema.sql` ; comparer tables et colonnes (mapping de types
   toléré). Il attrape l'oubli au moment du commit, pas en prod.
2. (M) À terme : générer les deux DDL d'une source unique (les modèles Pydantic
   existent déjà) — seulement si le rythme d'évolution du schéma le justifie.

---

## D4 — i18n : le reliquat CC-15b, et les libellés fabriqués côté serveur — **L**

**Description.** L'infrastructure est saine (dictionnaires plats fr/en, `useT`,
verrou `lexicon.test.ts` avec parité de clés) mais la couverture s'est arrêtée
en chemin. Deux couches distinctes :

**(a) Front : chaînes FR en dur** (~150+ hors commentaires) dans des composants
pourtant déjà branchés sur `useT` pour partie. Principaux gisements, par ordre
de visibilité en partie EN :
- `web/src/app/games/[id]/page.tsx` (≈ 80 chaînes : header « Théâtre live »,
  pastilles d'état, boutons Jouer/Accélérer/Stop, bloc décret, bloc fog,
  motions, avis/bannières, fin de partie/publication) — le fichier fait
  d'ailleurs **1 737 lignes** : le découper (bloc commandes, notices, colonne
  transcript) est le préalable naturel à sa migration (miroir front de D1) ;
- `components/modes.tsx`, `intel.tsx`, `judge.tsx`, `treaties.tsx`,
  `drift.tsx` (panneau révélation entier), `observables.tsx` (résidus),
  `stage-band.tsx`, `gamefeel.tsx`, `event-timeline.tsx` ;
- pages lobby/fin/replay/r (moindre priorité : le théâtre d'abord).

**(b) Backend : libellés FR fabriqués côté serveur** (les trois consignés
CC-15b, examinés par POLISH-3 — voici pourquoi ils n'ont PAS été corrigés ce
soir) :
- `d.label` (échéances G7-a, `app/game_api.py` ~l.920-1880) : cinq phrases
  composées (« échéance du pacte a-b », « menace de palier N (…) », bandeau
  ultimatum via `strip_label`) qui embarquent des données dynamiques, sont
  **persistées dans les snapshots** et **rejouées telles quelles dans les
  trames SSE**. Le front ne peut pas les recomposer (le schéma `Deadline` n'a
  ni slug ni arguments). Correctif propre : composer selon `game.language` à la
  création (la langue EST déjà sur la partie — G14/CC-3) + variantes EN de
  `rung_label` et `strip_label` ; les vieux snapshots gardent leurs labels FR
  (cohérent : la partie était FR).
- `profile_label` (révélation Dérive) : le slug `profile` est DÉJÀ exposé par
  `DriftRevealView` → mappable front (3 clés). Non fait ce soir car le panneau
  révélation entier est encore FR-dur : traduire la seule pastille aurait créé
  un panneau bilingue. À faire DANS la migration de `drift.tsx`. Attention :
  le `result_json` publié (`/r/{id}`) ne persiste QUE `profile_label` — ajouter
  le slug (additif) au moment de cette migration.
- `act.label` (indices de la déviante) : catalogue **data-driven**
  (`data/drift/params.json`, 16 actes) sans slug stable — (profil, palier) ne
  suffit pas (l'acte « vote » partage le palier 0,30). Correctif propre : des
  champs `act_en` dans le params + sélection par `game.language` au reveal
  (les actes sont relus des rounds persistés : la langue de la partie fait foi).

**Impact.** Une partie EN affiche un théâtre majoritairement FR — la feature
« langue » (G14) est à moitié tenue.

**Recommandation / séquencement.** Trois lots : (1) chrome du théâtre
(page.tsx + stage-band + gamefeel) ; (2) panneaux (modes/intel/judge/treaties/
drift avec le mapping `profile`) ; (3) la passe serveur `game.language`
(deadlines + actes + slug au result_json). Chaque lot : parité de clés + le
verrou lexique + un rendu EN testé (patron `SettingsProvider` des tests).

---

## D5 — Aucun smoke LLM en CI : les bugs « mistral réel » passent — **S/M**

**Description.** `.github/workflows/ci.yml` = pytest offline (MockBackend) +
ruff + lint/tests/build front. Correct et rapide, mais les smokes Ollama sont
gatés (3 skips permanents) et **les 4 bugs de POLISH-1 n'étaient visibles qU'au
smoke réel** (verdict tronqué à 400 tokens, notamment) : la CI actuelle ne
peut PAS les attraper. Le script de smoke de référence des passes POLISH
(`smoke_polish_mistral.py`) vit dans un scratchpad de session, pas dans le repo.

**Impact.** Chaque montée de version de prompt/schéma re-risque une régression
silencieuse ; le savoir-faire du smoke est dans les notes de session, pas
outillé.

**Recommandation.**
1. (S) **Versionner le smoke** : `scripts/smoke_theatre_mistral.py` (le script
   POLISH : Dérive 2 rounds/3 pays, décret+ultimatum, assertions sur verdict/
   promesses/reveal) à côté des `scripts/smoke_*_mistral.py` existants.
2. (S) Un `workflow_dispatch` (ou une checklist de release dans docs/) qui
   déroule les smokes sur le poste local — la 2060S est le seul runner qui a
   Ollama ; un runner self-hosted GitHub est possible mais engage la machine.
3. (M) Si le projet se déploie (Vercel + backend hébergé) : un smoke nightly
   sur un modèle API frontière économe, marqué `allow-failure`, pour au moins
   détecter les JSON tronqués.

---

## D6 — Les `params.json` multipliés : conventions divergentes, cohérences non gardées — **S**

**Description.** Quatre familles de paramètres de gameplay, quatre conventions :
`data/gamefeel/params.json`, `data/drift/params.json`, `data/intel/params.json`
(+ `lexicons.json`), et la **table de difficulté en CODE**
(`simulation/difficulty.py`). Des invariants inter-fichiers ne sont gardés que
par des commentaires : `difficulty.drift_k` doit rester cohérent avec `drift.k`,
`lp_multiplier` est annoté « miroir du bloc lp, doit rester cohérent »,
`si_context` est défini dans la table ET dans `data/gamefeel/params.json` sans
être branché nulle part (voir D7).

**Impact.** L'équilibrage Cowork (raison d'être de ces fichiers) peut
désynchroniser deux paramètres jumeaux sans qu'aucun test ne bronche.

**Recommandation.** (S) Un `data/README.md` (une table : fichier → qui le lit →
invariants) + un `tests/test_params_coherence.py` qui charge tout et vérifie
les miroirs documentés. Décider si la table de difficulté migre en data
(cohérence) ou reste en code (elle est plus proche d'une règle que d'un réglage
— trancher et l'écrire).

---

## D7 — Reliquats V2 consignés (à arbitrer, pas à laisser en suspens) — **S chacun**

Quatre décisions en attente, chacune documentée mais sans porteur :

| Reliquat | Localisation | État |
|---|---|---|
| `si_context` (9ᵉ levier de difficulté) | `simulation/difficulty.py:38` + `data/gamefeel/params.json` | Défini, testé, **jamais lu** par le moteur depuis G11-d. Brancher (résumé des actions du joueur dans le contexte des IA) ou supprimer le champ. |
| Remboursement des books caducs | `PLAN_JEU.md` §G22 (l.772-775, 806) | Les marchés vivants ne connaissent que YES/NO/OPEN ; une promesse caduque laisse un book jamais réglé (personne ne perd, v1 documentée). Décision : ajouter « void » au moteur LMSR ou entériner la v1. |
| og:image de partage (défi du jour) | notes G16 ; `/r/{id}` a la sienne | Le partage Wordle du défi est textuel ; la carte d'aperçu dédiée au défi reste à faire (ou à déclarer non voulue). |
| Marché du jour côté spectateurs | notes G16 | Le défi quotidien n'expose pas de marché aux non-joueurs — idée V2 à spécifier ou fermer. |

**Recommandation.** Passer les quatre en arbitrage utilisateur (garder/faire/
fermer) lors de la prochaine planification — un reliquat fermé est de la dette
en moins.

---

## D8 — Divers repérés à la lecture (petits, à saisir d'opportunité)

- **`web/src/app/games/[id]/page.tsx` = 1 737 lignes** : le monolithe front,
  miroir de D1 — voir D4(a) pour le découpage suggéré (S/M).
- **Idiome `float(r.trajectory.get("utopia", 0.5) or 0.5)`** (2 occurrences,
  `app/game_api.py`) : un utopia légitimement à 0.0 retomberait à 0,5. Cas
  quasi impossible (dérive bornée ±0,05/round), arbitré deux fois (POLISH-1/2)
  — à corriger d'office au découpage D1 (`x if x is not None else 0.5`).
- **Suite Python à ~215 s** (917 tests) : dominée par les suites d'API SSE
  (TestClient consomme des flux complets). Sans nouvelle dépendance : marquer
  les suites longues et offrir `-m "not slow"` en boucle courte ; xdist si un
  jour autorisé (S).
- **`legacy/`** (app Streamlit archivée R4, en-tête « ARCHIVÉ ») : 3 fichiers
  morts dans le repo ; git garde l'historique — supprimable (S, décision user).
- **0 TODO/FIXME dans tout le code** (py/ts/tsx) et ruff/eslint stricts au
  vert : la dette de ce projet est STRUCTURELLE (fichiers-monolithes, parité
  manuelle, couverture i18n), pas du laisser-aller local. C'est la bonne
  nouvelle de cet audit.

---

## D9 — Dette du lot « briefs gameplay » (2026-07-19) — **S/M par item**

> Consignée par la revue finale de branche `feat/briefs-gameplay-6pts` (3 lentilles +
> vérification adversariale). Aucun item ne bloquait le merge ; les correctifs bloquants
> (mode survie câblé, strip du verdict, cycle-limite, touched, reason façade, 409
> directive/suspendu, pays inventé) ont été appliqués dans la branche elle-même.

- **Facturation compute asymétrique (M6)** — la phase privée est débitée par fragment
  brut (trace de pensée incluse) mais la parole publique par MOT du texte final déjà
  strippé (`agents/llm_agent.py` re-streame le texte propre) : un pays casté reasoning
  sous-paie sa parole publique ; un message de repli (backend mort) est facturé comme
  généré. Borné (≤ 220 tokens publics) mais systématique. Piste : compter le brut côté
  agent ou exposer `completion_tokens` du backend. **S**
- **Unités mixtes `IntelParams`** — `covert_compute_cost` en TOKENS (÷100 via
  `compute_cost`) vs `covert_sabotage_amount` en UNITÉS de compute, appliqué direct.
  Commenté dans le JSON, mais une confusion ×100 au calibrage est vite arrivée. **S**
- **Coûts intel en dur dans l'UI** — `intel.tsx` affiche « 25/15/30/60 » et « coûte 5 de
  calcul » en littéraux : tout recalibrage de `data/intel/params.json` rend la copie
  fausse en silence. Piste : servir les coûts depuis l'API. **S**
- **Tension numérique des actions cachées** — `disinfo_expose_tension` défini mais lu
  nulle part ; l'exposition (disinfo ET covert) n'a pas de delta chiffré, seulement
  l'annonce publique du juge. À câbler pour les deux ensemble (chip de session créée). **S/M**
- **Chemin « réflexion libre » des modèles reasoning** — mesuré live (deepseek-r1:7b,
  52 tok/s, pic VRAM 5,8/8 Go) : 5/5 délibérations privées en repli car le modèle rédige
  en markdown libre (`**FUTUR 1 : …**`), pas les lignes strictes — même sans troncature.
  Option 4 du brief 2, reportée sciemment (chip de session créée). **M**
- **i18n des raisons du juge** — `attribute_reasons` sort en FR du prompt FR ; même
  famille que le reliquat `result.verdict` (D4). À traiter avec D4, pas isolément. —
- **Biais A1 en monde muet parfaitement calme** — escalade strictement 0 → signal de
  coordination max → U se stabilise ~0,6. Pré-existant (G9), rendu plus visible par le
  pas rapide. Piste : centrer le repli sur l'escalade neutre Kahn (0,5). **S** (playtest d'abord)
- **Convention `id == nom de fichier`** de `known_country_ids()` (détection du pays
  inventé) vérifiée sur les 33 pays mais non verrouillée par un test. **S**
- **Petites hygiènes** — frontière exacte `gap == deadband` sans test littéral ;
  duplication `_last_message_from`/`format_transcript` ; duplication validation target
  dans `buy_intel` (style existant) ; dérive des pays suspendus via le repli juge-muet
  (choix assumé, à observer au playtest). **S**
- **`VERDICT_MAX_TOKENS = 1300`** — pari raisonné, smoke mistral vert, mais la
  troncature du JSON enrichi (reasons) n'est pas mesurée sous stress (6 pays, transcript
  long). À surveiller au playtest. —

---

## Top 5 si on n'a qu'une journée

1. **Test de parité SQLite ↔ Supabase** (D3.1, S) — la classe de bugs
   invisible en dev qui casse en prod ; une matinée, rentable pour toujours.
2. **Versionner le smoke théâtre mistral + checklist de release** (D5.1-2, S) —
   les bugs du calibre POLISH-1 n°4 redeviennent détectables en un
   `python scripts/smoke_theatre_mistral.py`.
3. **Factoriser `_extract_json` + écrire le contrat de sortie LLM** (D2.1-2, S)
   — quatre copies deviennent une, et le patron qui a sauvé le verdict est
   écrit pour la prochaine sortie structurée.
4. **`data/README.md` + test de cohérence des params** (D6, S) — protège le
   travail d'équilibrage Cowork qui commence (calibrations « 10 parties »).
5. **Lot 1 i18n du théâtre** (D4 lot 1, reste de la journée) — le chrome de la
   page de jeu en EN : c'est ce qu'un joueur anglophone voit en premier.

Le découpage de `game_api.py` (D1) n'entre pas dans une journée — le programmer
comme PREMIÈRE série de la prochaine session longue, avant que le fichier ne
franchisse les 4 000 lignes de nouveau.
