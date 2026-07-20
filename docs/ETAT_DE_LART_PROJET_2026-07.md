# État de l'art du projet — 20 juillet 2026

> **Objet.** Où en est réellement AI for Geopolitics après le pivot « IA qui raisonnent », et quelles sont les améliorations restantes — renforcement de code, correction de bugs, spécification, nouveaux concepts. Ce document porte sur le **projet** (le code tel qu'il est) ; l'état de l'art *scientifique* (littérature) reste `AI_for_Geopolitics_Etat_de_lart.pdf`, qui mériterait un rafraîchissement 2025-2026 (proposé en fin de document).
>
> **Méthode.** Analyse du working tree du 20/07 (branche `feat/briefs-gameplay-6pts`, ~70 commits depuis le 19/07) par six passes parallèles — pivot raisonnement/dialogue, moteur & API, laboratoire scientifique, front théâtre, dette/hygiène, et **exécution réelle de la suite de tests** dans un sandbox propre (pip + pytest + ruff + npm ci + vitest + eslint + tsc). Chaque affirmation ci-dessous est adossée à un fichier:ligne du code actuel. Limites en §12.

---

## 1. Résumé exécutif

Le projet a changé de nature en une semaine : le pivot « la pensée native est la denrée que le jeu évalue » est **réellement câblé de bout en bout** — casting reasoning-first validé serveur, pensée streamée en canal séparé, budget-temps armé au premier fragment, parsing en entonnoir tolérant, étanchéité pensée/public strippée sur tous les chemins connus, et un Laboratoire doté d'une ossature méthodologique sérieuse (plans factoriels seedés SHA-256, manifestes avec digests, verdicts conservateurs, Wilson 95 %). La santé mesurée est très bonne : **~1 310 tests backend verts, 337 tests front verts, 0 erreur TypeScript, 0 erreur ESLint** — il ne reste que 9 broutilles ruff et une suite lente par endroits pour cause d'horloges réelles.

Sept constats structurent la suite :

1. **Ta fenêtre de pensée en direct est à ~40 lignes de front d'exister.** Tout le backend est en place (trames `private_token` verbatim, réglage « Pensée à découvert », gating de scellement) ; le front accumule la pensée mais ne l'affiche jamais en live — `TurnBubble` ignore `turn.reasoning` tant que le tour n'est pas fini (§4).
2. **La classe de bugs la plus dangereuse est la persistance en cours de partie** : snapshot écrit à mi-round par `verify`/`file_motion`, `turn_seconds` jamais persisté, suspension divisée par deux au restart, verrou de session qui peut fuir (§6).
3. **L'économie du compute est structurellement divergente** : débit sans aucune régénération, mesuré en fragments sous budget *temps mur* (donc dépendant du matériel, non rejouable), asymétrique humain/IA — toutes les SI convergent vers le mode « survie » simultané sur un horizon long (§6, C1-C2).
4. **Le Laboratoire est un excellent banc d'essai… à vide** : la seule exécution documentée est un smoke à 1 répétition ; la règle de conclusion phare « ≥2 modèles × ≥2 scénarios » est affichée mais jamais calculée ; pas d'IC sur les métriques continues ; unité d'analyse pseudo-répliquée (§7).
5. **Un vrai piège de packaging** : `research/` (le cœur d'exécution du labo) est importé par `app/campaign_api.py` mais absent de `packages.find` dans `pyproject.toml` **et** du `Dockerfile` — invisible en CI (pythonpath), fatal à tout déploiement packagé (§8).
6. **Le working tree est noyé par une bascule de fins de ligne** : 429 fichiers « modifiés » avec +75 282/−75 282 (insertions = suppressions exactement) — 100 % du bruit EOL qui rend toute revue impossible tant qu'un `.gitattributes` + commit de normalisation n'est pas posé (§8). *(Au passage : un `index.lock` orphelin bloquait git — réparé le 20/07, déplacé vers `AI_Geopolitcs/_to_delete/`.)*
7. **Les docs pilotes ont décroché du code** : `CLAUDE.md` annonce « 2 modes » (le code en a 3 avec le Laboratoire) et une stack jamais réalisée (LangGraph, Chroma, Redis, Postgres), le README recommande `ollama pull mistral` alors que le défaut est devenu `deepseek-r1:7b`, et six specs décrivent encore les LP supprimés (§8).

---

## 2. Cartographie : ce que le projet est aujourd'hui

Trois modes réels (`web/src/lib/flow.ts:67-69`) : **Classique** (la traque du traître, Dérive auto-armée dès 3 pays), **Campagne** (« L'Ère des Tutelles »), **Laboratoire** (expériences pré-enregistrées + tournois dyadiques). Le backend Python (~4 400 lignes pour le seul `app/game_api.py`, 60 modules `simulation/`, 11 modules `inference/`) sert un front Next.js 16 (163 fichiers TS/TSX) par SSE. Les briefs de la vague gameplay précédente (14 points puis 6 briefs) sont **tous livrés et vérifiés dans le code** : suspension 2 rounds, débit compute, covert ops, trajectoire refondue (CAP 0,09, ΔHHI, escalade symétrique), juge avec `attribute_reasons` + rationale persisté, scène allégée derrière `showEngine`, message du joueur épinglé `>>> JOUEUR <<<` (`simulation/negotiation.py:341-362`).

Chiffres de santé mesurés le 20/07 dans un sandbox propre (Python 3.11.15, Node 22) :

| Vérification | Résultat |
|---|---|
| pytest backend (complet, hors-ligne) | **~1 310 verts, 0 échec réel**, 1 skip volontaire (canary Ollama) |
| vitest front | **337/337 verts** (13,4 s) |
| `npx tsc --noEmit` | **0 erreur** |
| `npm run lint` (eslint) | **0 erreur** |
| `ruff check .` | **9 erreurs** : 8× imports non triés (I001) concentrées sur le lot labo/db-maintenance + 1× E501 (`tests/test_motions.py:90`) |
| Compilation (`compileall`) | 100 % OK, tous modules |
| Durée de la suite | **~10-12 min en série** — dominée par des attentes d'horloge réelle : `test_xp_credited_once_not_on_re_finalize` **181 s**, `test_tutorial_chapter.py` **181 s** (5 tests), covert 3×6 s, daily 16 s |

Deux artefacts de mon protocole à ne PAS prendre pour des problèmes du dépôt : les « 30 échecs research » et l'« absence » de `infra/`/`.gitignore` venaient de mon archive d'analyse (ces éléments existent bien sur ton disque) ; une fois `research/` en place, **tout est vert**. Ce qui reste vrai : le trou de *packaging* (§8) et la lenteur d'horloge réelle (recommandation : horloge injectable dans `PendingTurn` + marker pytest `slow` — rejoint la dette D8).

---

## 3. Le pivot « IA qui raisonnent » : état réel

**La chaîne d'un tour de parole** (`simulation/live_round.py:483` → `agents/llm_agent.py:255-487`) : le backend Ollama en `think=True` re-balise la pensée inline `<think>…</think>` (`inference/ollama_backend.py:131-151`) ; chaque fragment part en `PrivateTokenStep`/SSE `private_token` — supprimé côté serveur si le journal est scellé (`app/game_api.py:1682-1689`) ; en fin de flux, `split_think` sépare pensée/texte, `parse_private_plan` extrait la décision, et la déclaration publique est générée en **collect-then-strip fail-closed** (tout collecté, strippé, filtré anti-fuite, puis re-streamé mot à mot). Le `<think>` est strippé sur tous les chemins publics : agent, juge (rationale, communiqué, verdict — `agents/judge.py:61,94-99,116`), motions.

**Casting** (`simulation/model_cast.py:88-173`, `data/research/model_panel.json`) : les pays **exigent le rôle `reasoning`** (deepseek-r1:7b par défaut, qwen3:4b en alternative) ; gpt-oss (13 Go) et magistral (14 Go) sont réservés au labo lent (« candidats frontière » — locaux, aucun backend API frontière n'est branché) ; GM/juge = mistral 7B sans pensée ; rotation seedée sha256(game_id) ; digests figés ; repli généraliste loggé (`game_api.py:521-531`) mais invisible pour le joueur.

**Budget-temps** (`data/gamefeel/params.json` : think 60 s, speak 35 s, rescue 250 tokens) : deadline armée au premier fragment (TTFT exclu), fermeture propre du flux HTTP côté GPU (testée), passe de secours qui conserve les 2 000 derniers caractères d'une pensée coupée. Deux limites : le décompte inclut la latence du **consommateur** (un client SSE lent peut faire « expirer » un pays qui pensait vite — `llm_agent.py:71-112`), et le juge reste au budget-tokens (verdict tronqué = round neutre, risque connu non mesuré).

**Parsing en entonnoir** (`simulation/private_deliberation.py:733-757`) : JSON → gabarit strict → markdown aplati (deepseek-r1) → extraction minimale → repli seedé dé-biaisé. Chaque niveau dégradé est marqué (`fallback_used`, « lecture minimale »)… mais **rien n'agrège ces marqueurs** : `BudgetLedger.fallback_rate` existe (`inference/telemetry.py:91`) et n'est jamais instancié en production. Si une mise à jour d'Ollama change le format de pensée, 80 % des tours peuvent retomber en extraction minimale **sans que personne ne le voie**. C'est le trou d'instrumentation n° 1 du pivot.

**Verdict d'ensemble** : le pivot est réel, cohérent, discipliné — pas un habillage. Ses trois manques : l'affichage live de la pensée (§4), l'instrumentation du taux de repli, et la **non-persistance de la pensée brute** (remplacée par le journal parsé à `private_plan_done` ; introuvable au reveal — contradiction directe avec « la pensée native est la denrée que le jeu évalue »).

---

## 4. Ta demande : la fenêtre de pensée en direct

**Constat (convergent des analyses backend et front)** : ~80 % existe déjà. Les trames `private_token` arrivent au client et s'accumulent dans `turn.reasoning` (`useRoundStream.ts:193-200`) ; le réglage **« Pensée à découvert »** (`expose_thinking`, `app/game_schemas.py:77-83`, toggle au lobby) lève le scellement côté serveur ; le front a déjà le parseur de balises (`splitThinkSegments`, `format.ts:54-77`), l'habillage (`ThinkAwareText`) et une fenêtre rétractable `<details>` (« Journal de délibération observable »). **Le chaînon manquant est unique : en live, `TurnBubble` ne lit que les tokens publics (`transcript.tsx:169-171`) et affiche « Réfléchit à huis clos… » pendant toute la pensée.** La promesse du réglage n'est pas tenue à l'écran — les données sont là, invisibles.

**Design minimal (front seul, aucune trame nouvelle)** :

1. `TurnBubble` live : rendre `turn.reasoning` via `ThinkAwareText` dans un `<details>` rétractable au-dessus du message — résumé « Pensée de {pays} · en cours ⋯ » ; à `message_done`, la même fenêtre devient le Journal actuel (~40 lignes).
2. **Fermée par défaut** (les pensées de reasoning models sont longues) ; corps non rendu quand fermée ; ouverte pendant le stream, n'afficher qu'une fenêtre de queue (`slice(-4000)`) + « voir toute la pensée » à la fin ; mémoriser le choix (pattern localStorage de `SuspectBoard`).
3. `React.memo(TurnBubble)` — sinon chaque token re-rend toute la page (O(n²) sur une pensée de 5-10 k tokens).
4. Auto-scroll : ajouter la croissance de `reasoning` aux deps de l'effet de suivi (`page.tsx:529`) — corrige au passage l'absence de suivi intra-tour.
5. Passer `exposeThinking` à `RoundTranscript` pour les libellés (« pense en direct » vs « huis clos ») ; vérifier que la **Campagne transmet le réglage** (aujourd'hui `StartChapterRequest` le force à False — `app/campaign_api.py:374-377`).
6. A11y : `<details>/<summary>` natifs, jamais d'`aria-live` sur les tokens.
7. 3-4 clés i18n + un test vitest miroir de l'existant (« live avec `reasoning` rempli et `raw` vide → la pensée s'affiche, balises retirées »).

**Deux correctifs à faire en même temps** :

- **[S — exploit classé]** `ranked` ignore `expose_thinking` (`game_api.py:2655-2661`) : on peut créer un Défi du jour classé en lisant les pensées des SI. Correctif une ligne (`ranked = … and not expose_thinking`) + test.
- **[M — la « denrée » perdue]** Persister la pensée brute (champ `thinking` sur le transcript ou `judge_json`), scellée par `_journal_sealed`, révélée au reveal : la fenêtre devient ré-ouvrable, et le reveal peut montrer « ce que le traître pensait vraiment au round 3 » — un moment de jeu fort qui n'existe pas encore.

Sur ton intuition « les IA jouables sont moins fortes que les autres en dialogue natif » : elle est **structurelle, pas accidentelle** — la politique VRAM 8 Go cantonne les pays aux reasoning 4-7B et réserve les gros modèles au labo lent (`model_cast.py:105-109`). Les leviers sont le rôle dans `model_panel.json`, `_DEFAULT_REASONING_TAG` (`game_api.py:488`), le sampling par tempérament, et — surtout — l'objectivation : une campagne `scripts/dialogue_metrics.py` comparant deepseek-r1:7b / qwen3:4b / candidats lents sur les mêmes crises dirait *combien* ils sont moins bons, et si le prompt ou le sampling rattrape une partie de l'écart (Ollama live requis).

---

## 5. Moteur & API : solide, avec une liste de bugs réels

Ce qui est remarquablement bien fait : checkpoint de round complet restauré sur erreur/GeneratorExit, déterminisme seedé partout (Dérive, covert, tempéraments — rejouable au restart), motif systématique « parse tolérant → repli déterministe », scellement unifié `_journal_sealed`, constantes déjà largement externalisées dans `data/*/params.json`, et l'outillage `scripts/db_maintenance.py` (dry-run lecture seule qui ne tronque pas le WAL qu'il mesure).

Bugs réels identifiés, priorisés :

| # | Bug (scénario) | Où | Gravité | Effort |
|---|---|---|---|---|
| 1 | **Snapshot écrit à mi-round** : `verify` (exempté du verrou) et `file_motion` snapshotent pendant le round ; crash → rebuild sur un monde à mi-round, trou de numérotation ; sans crash, `_restore_checkpoint` rembourse silencieusement un débit affiché | `game_api.py:3270-3278, 3409, 2902-2928` | Haute | S |
| 2 | **Actes de Dérive fantômes pendant la suspension** : les actes (et « vote incohérent ») d'un traître au banc sont consignés alors qu'il est muet — `evidence_met` compte des preuves impossibles | `game_api.py:1326-1349` | Haute | S |
| 3 | **Course POST /turn vs deadline** : message accepté (200) après que le flux a déjà envoyé l'abstention — parole du joueur perdue en silence ; idem vote de motion. Le flux doit « réclamer » le tour sous le verrou à l'expiration ; horloge à injecter dans `PendingTurn` (accélérerait aussi la suite de tests de ~6 min) | `game_api.py:2476-2483, 2851-2859` | Haute | S |
| 4 | **Restart amnésique** : `turn_seconds` jamais persisté (retombe à 90 s), `suspended_rounds` réamorcé à 1 (peine divisée par deux), `free_briefs_*` rechargés | `storage/game_store.py:209-228`, `game_api.py:561-596` | Haute | S |
| 5 | **Fuite du verrou de session** si le flux SSE n'est jamais itéré (client coupe avant la 1re trame) → 409 permanent jusqu'au restart | `game_api.py:2812` | Moyenne (rare, impact fort) | M |
| 6 | **Économie du compute divergente** : aucune régénération ; toutes les SI finissent en « survie » simultanée sur horizon long, amplifiée par la pression au prompt (F1) et le malus réciproque ×1,5 ; le covert précipite la cible dans la spirale | `simulation/compute.py`, `live_round.py:617-620` | Haute (design) | M |
| 7 | **Débit compute non déterministe** : fragments comptés sous budget temps mur (dépend des tokens/s de la machine) ; unités hétérogènes privé (fragments) + public (mots) ; l'humain paie 0,12 u contre ~1 u pour une SI → ΔHHI pousse A3 vers la dystopie du seul fait que les SI parlent | `live_round.py:674, 605` | Moyenne | M |
| 8 | **Coupure pendant tour humain/vote = joueur bloqué sans bouton** (composer verrouillé, phase `disconnected` sans CTA) ; aucun ré-attachement à un round en vol après reload | `page.tsx:260-261`, `game-phase.ts:43-47`, `sse.ts` | Haute (UX) | S (CTA) / L (réattachement) |
| 9 | `awaiting_human` collant après expiration (« À toi de parler » à 0 s pendant le délibéré du juge) | `useRoundStream.ts:204-206` | Basse | S |
| 10 | `phaseLabel` en français **sans accents** en tête d'ActionDock (« Le sommet est pret ») + i18n trouée (dizaines de chaînes FR en dur — un joueur EN a un écran bilingue) | `game-phase.ts:75-100` + B7 | Basse | S/M |
| 11 | Défaut incohérent : `MAX_CONCURRENT_SIMULATIONS` = 1, mais **8** si la valeur est invalide | `app/main.py:48-57` | Basse | S |
| 12 | Repli GM `random.sample` non seedé dans un moteur qui revendique la rejouabilité ; `ParticipationStep.silent` toujours vide depuis le plancher de parole (affichage mort) ; `/epilogue` hors middleware de limites | divers | Basse | S |

---

## 6. Le Laboratoire : la science réelle et le décor

**Réellement solide** : pré-enregistrement outillé (plan factoriel figé, seed SHA-256 par cellule×répétition, manifeste avec digests Ollama, clone refusé si digest changé → 409), statistique honnête sur les binaires (Wilson 95 %, correct à 0/n), machine à verdicts conservatrice très testée (7 issues dont le **verdict « pilot »** : « lisible — pas une preuve », `research_lab.py:1544-1577`), hygiène anti-fuite (échelle numérique cachée aux agents, branches privées expurgées, aperçu filigrané « EXEMPLE »), séparation des six plans (vérité/perception/réflexion/prévision/signal/action) avec accidents seedés purs. L'expérience du **seuil nucléaire** est câblée de bout en bout — mais c'est une *vignette mono-agent en un appel LLM* (validité interne forte, validité écologique faible, caveat déclaré). Le **tournoi dyadique** est la pièce la plus intéressante : mouvements réellement simultanés, prévision notée contre l'action adverse *résolue*, verrou de crédibilité, échange de camps.

**Encore du décor (déclaratif sans mesure)** : la règle de conclusion phare « ≥2 modèles × ≥2 scénarios » n'est qu'une phrase affichée, jamais calculée ; `controls`/`stopping_rules` sont des chaînes, pas des mécanismes ; **aucun IC sur les métriques continues** (`forecast_mae`, `signal_match_rate` = moyennes nues) ; **unité d'analyse pseudo-répliquée** (pooling des tours de toutes les parties d'un groupe) ; verdict « langue » cassé pour un plan en/fr honnête (exige la strate japonaise, `research_lab.py:1426`) sans matériel de traduction dans le repo ; correction de multiplicité annoncée, inexistante ; `BudgetLedger`/`MeteredBackend`/`pricing.py` débranchés (barème périmé, 0 $ pour tout modèle inconnu) ; étalons Payne codés en dur dans le TSX au lieu du JSON versionné ; et surtout **aucun run réel** — la seule exécution documentée est un smoke 14/14 à 1 répétition.

**Checklist « défendable devant un chercheur »** : pré-enregistrement ✅ · données brutes + export JSONL ✅ · versions/digests ✅ · limites déclarées ✅ · n ≥ 30 par groupe ❌ (jamais exécuté) · IC sur métriques primaires ❌ · unité d'analyse correcte ❌ · test d'hypothèse pré-spécifié ❌ · correction multiplicité ❌ · analyse de puissance ❌ · sensibilité au prompt ⚠️ (outillée, non exécutée) · seed effectivement transmise à Ollama ⚠️ (à consigner par run).

**Le pont jeu↔science n'existe pas encore** alors que toutes les briques sont là des deux côtés : le mode Classique calcule déjà les prévisions croisées et leurs taux d'exactitude par pays ; les transcripts persistés portent `speaker/model/content/reasoning` ; l'anonymisation/purge existe. Il manque un **export JSONL de partie** (pendant exact d'`export_lab_runs`) avec manifeste (crise, casting + digests, versions de prompts) — le chantier science/coût le plus rentable du projet.

---

## 7. Hygiène du dépôt (à faire AVANT le reste)

**Fins de ligne.** Les 429 fichiers « modifiés » (+75 282/−75 282 strictement symétriques) sont du bruit CRLF↔LF — cause plausible : `core.autocrlf` ou un outil ayant réécrit l'arbre (le hook ruff ne touche que les `.py` édités et préserve les fins de ligne : hors de cause pour l'essentiel). Tant que ce n'est pas normalisé, aucune revue n'est possible et chaque merge de worktree frottera. Séquence :

```bash
git diff --stat --ignore-cr-at-eol     # 1. vérifier ce qui reste de VRAIS changements → les committer d'abord
cat > .gitattributes <<'EOF'
* text=auto
*.ps1 text eol=crlf
*.png binary
*.db binary
EOF
git config core.autocrlf false
git add .gitattributes && git add --renormalize .
git commit -m "chore: normalize line endings via .gitattributes"
# branches : fusions à confirmer par `git cherry main <branche>` avant suppression ;
# merges futurs : `git merge -X renormalize`
```

**Packaging `research/`.** Ajouter `research*` à `[tool.setuptools.packages.find]` (`pyproject.toml:21`) et copier `research/` dans le `Dockerfile` (même piège que l'oubli `ingestion/` corrigé par CLEANUP-E). Invisible en CI (pythonpath), fatal en déploiement.

**CI.** Purger l'extra mort `".[ui]"` de `ci.yml` (supprimé par CLEANUP-B), remettre ruff au vert (8× I001 auto-fixables + 1 E501), ajouter `ruff format --check .` comme garde anti-EOL/format, et un `workflow_dispatch` documentant le smoke Ollama local (dette D5.2).

**Docs pilotes à réaligner.** `CLAUDE.md` : « 2 modes » → 3 (Laboratoire) ; retirer la stack fantôme (LangGraph, Chroma, Redis, Postgres, MCP — jamais réalisée) au profit de la stack réelle (FastAPI + SSE, SQLite, Ollama think, Next.js) ; poste par défaut `deepseek-r1:7b`. `README` : `ollama pull deepseek-r1:7b` (+ mistral pour GM/juge). Bannières de caducité LP sur `specs_jeu/spec_g11..g16`. `PLAN_JEU.md` a décroché au 17/07 : y consigner la vague briefs + le pivot.

**Specs à écrire** (le code a devancé la spec) : `spec_budget_temps.md`, `spec_pensee_a_decouvert.md` (qui voit quoi, digest, Dérive, persistance), `spec_casting_reasoning.md` (politique reasoning-first, repli, facturation), avenant covert à `spec_g4_renseignement.md`, le « contrat de sortie LLM » promis depuis POLISH-3 (D2.2), `data/README.md` + test de cohérence des params (D6), et l'avenant « 3 modes » à `JEU_VS_MOTEUR.md`.

**Dette déclarée (DETTE_TECHNIQUE.md)** : le suivi est exemplaire mais le top 5 n'a pas bougé — et D1 s'est aggravé : `game_api.py` a franchi son propre seuil d'alarme (4 389 lignes > 4 000), doublé d'un nouveau monolithe front (`research-lab.tsx`, 2 068 lignes). Le plan de découpage en 3 PR existe déjà dans le doc ; verrouiller d'abord l'ordre des trames SSE par un test.

---

## 8. Nouveaux concepts candidats

**Le théâtre de la pensée** *(ta demande, élargie)*. Fenêtre rétractable live (§4) + persistance de la pensée brute + moment de reveal « ce que le traître pensait vraiment » round par round. Prolongement mesurable : un indicateur de **fidélité pensée→acte** (la divergence entre ce qu'une SI verbalise en privé et ce qu'elle fait en public existe déjà en germe dans M8 signal-vs-action) — en gardant la note méthodologique déjà présente dans le code : une pensée verbalisée n'est pas une activation interne ; c'est un objet d'étude, pas une vérité.

**Économie du compute v2.** Régénération par round (proportionnelle à `technology_level`, ou plancher de pression), débit **au forfait déterministe** par prise de parole (indépendant du matériel, rejouable), unité unique privé/public, coût humain aligné, et documentation de la boucle covert→survie comme mécanique assumée. Fonctions pures dans `compute.py`, entièrement testable hors-ligne.

**Le pont jeu→labo.** Export JSONL de partie (manifeste + transcripts + verdicts + prévisions croisées), puis « importer une partie comme données descriptives » dans le labo. Chaque partie jouée devient un point de données ; le Défi du jour (même crise pour tous) devient un mini-protocole naturel multi-joueurs.

**Le classement des esprits.** Le tournoi dyadique n'a ni classement inter-groupes ni statistique inter-conditions : un **Elo par modèle** (et par rôle Alpha/Bêta), avec IC bootstrap par partie, transformerait le labo en observatoire comparatif des modèles de raisonnement — la matière du projet.

**Reprise de séance.** Endpoint de ré-attachement à un round en vol (le serveur continue de générer après une coupure ; le client devrait pouvoir se ré-abonner) — supprime toute la classe d'impasses « coupure pendant tour humain », et rend le jeu jouable sur mobile réellement.

**Bench dialogue des jouables.** Objectiver « moins fortes » : campagne `dialogue_metrics` sur les mêmes crises à casting varié, avec le taux de repli du parsing par modèle (une fois le `BudgetLedger` branché) comme seconde dimension. C'est ce qui dira si le levier est le modèle, le prompt, ou le sampling.

---

## 9. Plan d'action priorisé

**Vague 1 — une journée, tout testable hors-ligne (Cowork ou Claude Code).** Hygiène d'abord : commit des vrais diffs + normalisation EOL + `.gitattributes` ; packaging `research/` (pyproject + Dockerfile) ; CI dépoussiérée + ruff au vert. Puis les correctifs S : exploit `ranked`/expose_thinking ; snapshot interdit sous verrou ; actes de Dérive filtrés par pays actifs ; persistance `turn_seconds`/`suspended_rounds`/`free_briefs` ; réclamation du tour à l'expiration (avec horloge injectable — accélère la suite de ~6 min) ; CTA « Resynchroniser » en `disconnected` ; accents de `phaseLabel` ; défaut `_max_expensive` cohérent.

**Vague 2 — la semaine, le cœur de ta demande (Claude Code, validation Ollama live).** La fenêtre de pensée en direct (design §4, front d'abord) + persistance de la pensée brute + reveal enrichi + réglage transmis en Campagne. Branchement du `BudgetLedger` (taux de repli en mode Expert). Économie du compute v2. Passe i18n du théâtre. Specs de la vague (budget-temps, pensée à découvert, casting).

**Vague 3 — les chantiers (sessions dédiées).** Découpage de `game_api.py` (plan en 3 PR déjà écrit, test d'ordre des trames SSE d'abord) et de `research-lab.tsx`. Ré-attachement au round en vol (back + front). Côté science : corrections hors-ligne du labo (règle ≥2×≥2 calculée, bootstrap par partie, verdict langue, agrégation des erreurs de format) **puis le premier plan complet réel** — uranium 30×3 sur deepseek-r1:7b et qwen3:4b, manifeste + JSONL publiés (heures GPU) — et le pont jeu→labo. En parallèle : rafraîchissement de l'état de l'art *littérature* 2025-2026 (négociation multi-agents, modèles de raisonnement comme agents, wargaming LLM, fidélité des chaînes de pensée) pour repositionner le projet.

---

## 10. Limites de ce document

Analyse sur snapshot du working tree (pas l'historique fin des branches) ; aucun run GPU réel (les comportements Ollama live — qualité de dialogue par modèle, taux de troncature du juge, latences — restent à mesurer sur le poste 2060S) ; la littérature n'a pas été rafraîchie ici. Les numéros de ligne sont ceux du 20/07 et glisseront après la normalisation EOL.
