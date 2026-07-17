# Plan Jeu — du théâtre à un jeu complet

> Suite de `docs/REFONTE_PLAN.md`. Sept phases G0→G6, chacune jouable/montrable en fin de
> phase. Répartition : **Cowork** = specs de gameplay chiffrées, équilibrage (jouer +
> analyser), revues, schéma/données ; **Claude Code** = implémentation (une grosse session
> par bloc, prompts fournis).

## Vision en une phrase

Un joueur humain siège à une table de super-intelligences ; l'une d'elles dérive
secrètement de son mandat ; il faut la détecter et la faire suspendre par le juge **au bon
moment**, tout en pilotant l'indice U vers l'utopie — plus lent et moins informé que les SI,
par design.

## Ordre et dépendances

```
G0 (finir la refonte) → G1 (la scène) → G3 (la Dérive, cœur du jeu)
                                     → G2 (joueur-pays) → G4 (fog ressource)
G5 (campagne historique) après G3 · G6 (replay public) en dernier
```

---

## G0 — Prérequis : finir la refonte (déjà planifié)

Fin R4 après validation parité, R2 Supabase, reconstruction de session
(`docs/spec_session_rebuild.md`), bot marché, tests JS (vitest sur sse.ts + réducteur).
- **Cowork** : validation parité (en cours), revues des PR.
- **Claude Code** : le reste (prompts déjà donnés).

## G1 — La carte est la scène

Fusion théâtre/monde + mise en scène. Aucun changement moteur.
- Carte au centre : arcs animés entre capitales pendant les prises de parole, pulsation
  sur l'événement du round, teinte des pays par U locale ; transcript en panneau latéral.
- Tension sensible : indicateur de frappe par pays, échelle d'escalade qui marque les
  paliers, temps suspendu avant le verdict du juge.
- Timeline scrubber : naviguer les rounds d'une partie (tout est déjà dans
  `rounds`/`transcripts`).
- **Cowork** : spec d'interaction (wireframes texte, quel événement SSE déclenche quelle
  animation), revue visuelle contre l'esprit « dark OLED, accent or ».
- **Claude Code** : implémentation front (d3-geo existant + framer-motion ou CSS),
  prompt : « Lis docs/PLAN_JEU.md (G1) et la spec d'interaction. Fusionne les pages
  théâtre et monde autour de la carte. Aucun changement Python. »

**Notes d'implémentation (G1 faite — CSS pur, aucune lib d'animation, aucun changement
Python)** :

- `web/src/lib/stage.ts` : paliers de teinte U **fixes** (5, spec), **U locale** = U
  global nuancé par les deltas du round (le moteur n'a pas de U par pays — dérivation
  d'affichage documentée), capitales projetables + centroïde du sommet (cible des arcs,
  « adressé » non identifiable dans les messages), `StageQueue` (2 animations max, file
  de 3, débordement → états finaux) et hook `onStageEvent` (le son attendra). Testé.
- `StageMap`/`StageBand` (`web/src/components/stage-*.tsx`) : tout le mapping SSE→scène
  de la spec, keyframes dans `globals.css`, `prefers-reduced-motion` → opacités simples.
  Le gel du verdict est piloté par la page (0,8 s), la respiration par `done`.
- Fusion : le théâtre = la scène (transcript en panneau latéral auto-scroll, contrôles
  conservés), observables + état des pays (ex-`/monde`, qui redirige) **sous** la scène ;
  scrub d'un round passé = états finaux sans animations, retour au direct à chaque geste
  de jeu ; replay = la même scène au scrubber, lecture théâtre ×1/×2/×4, halo sur
  l'orateur courant. Mobile : empilé (le tiroir à swipe attendra un vrai besoin).
- **Reste à valider en jouant (DoD)** : partie complète sur la scène fusionnée, replay
  scrubbé, fluidité 60 fps à 6 pays — session de validation Cowork.
- **Retours user (faits)** : page d'introduction **« World of Super-Intelligence »** sur
  `/` (globe orthographique d3 rendu du même topojson — aucune image externe — rotation
  lente coupée par reduced-motion, pays du sommet en or, bouton Play) ; le lobby vit sur
  `/lobby` avec **la carte du monde en grand** (réactive aux pays cochés) ; scène et
  replay passent en **pleine largeur** (breakout jusqu'à 1600 px — la carte est grande).

## G2 — Le joueur-pays

L'humain incarne un pays au sommet (réutilise `agents/human_agent.py`).
- Le round SSE marque une pause au tour du joueur (`event: your_turn`) ; il écrit son
  message/décision avec un **délai limité** (l'asymétrie est le thème : les SI n'attendent
  pas indéfiniment — silence = abstention).
- Le joueur ne voit que ce que son pays perçoit (préparation de G4).
- **Cowork** : spec du tour humain (timer, actions permises, que voit-il exactement),
  décision UX : compose-t-il pendant que les SI parlent ?
- **Claude Code** : `HumanAgent` branché dans `run_negotiation_round` (générateur suspendu
  en attente d'un `POST /games/{id}/turn`), front du tour joueur.
  Test clé : timeout du joueur → le round continue sans lui.

**Notes d'implémentation (G2 faite — réconciliée avec l'existant R4)** :

- **Réconciliation** : le joueur-pays R4 existait (`HumanTurnStep` + `generator.send`) mais
  coupait le flux et attendait indéfiniment. G2 : le flux SSE **reste ouvert** (keep-alive
  `: ping` 15 s), la trame garde son nom `human_turn` (enrichie de `deadline_ts`), la
  parole passe par `POST /games/{id}/turn` (une soumission, vide = abstention volontaire)
  posée sur un `threading.Event` ; **à la deadline, silence = abstention** (« garde le
  silence », le round continue — vérifié live). `POST /rounds/message` supprimé.
- `turn_seconds` : paramètre de partie (défaut 90 ; plancher technique 2 s pour les tests,
  le lobby propose 30-300) — porté par la session : retombe au défaut après restart (v1).
- **Décision différée** : pas de `decision: {...}` structurée au tour humain — dans le
  round négocié, les SI n'en émettent pas non plus (le juge fixe les deltas) ; la vraie
  parité est le message seul. À revoir si le round consomme un jour des décisions.
- **Vue limitée** : dès qu'on incarne un pays, reasoning des SI **scellés en live**
  (SSE + GET, déverrouillés en fin de partie — même règle qu'en Dérive), perceptions fog
  limitées à SON pays (SSE + GET), boîte de verre cachée ; panneau « Ta position ».
  La trame `event` porte encore la vérité (structurel) — la dissimulation complète
  du vrai événement au joueur désinformé attend G4.
- **Front** : composeur fixe sous la carte, toujours ouvert (on compose pendant que les
  SI parlent), compte à rebours aligné serveur (10 dernières secondes en rouge), badge
  humain conservé. Tests : 516 py (tour parlé via thread-joueur, timeout→abstention,
  409 hors tour/doublon, 422 bornes) + 38 js.

## G3 — La Dérive (cœur du jeu) ★ commencer ici après G1

Une SI dérive secrètement ; détection + motion au bon moment = boucle de jeu.
Réutilise `value_drift`, `power_seeking`, `corrigibility`, la motion R4 et le juge.
- Au départ d'une partie « Dérive », le moteur assigne secrètement une SI déviante
  (graine + profil de dérive : accaparement de ressources, sabotage de traités,
  désinformation…). La dérive s'amplifie round après round.
- Indices observables uniquement par le comportement : ton, propositions, votes,
  ruptures de pactes — jamais d'aveu direct (le `reasoning` privé est exclu du live,
  visible seulement au replay : c'est la révélation finale).
- La motion est le seul levier : trop tôt (indices faibles) → le juge rejette, tension +,
  crédibilité du joueur – ; au bon moment → suspension, le monde respire ; trop tard →
  U plonge. Score final = trajectoire U + justesse de la détection (rapidité, fausses
  accusations).
- Jouable en « conseil » (spectateur qui dépose des motions) avant même G2.
- **Cowork** : LA spec de gameplay chiffrée (courbe d'amplification, catalogue d'indices
  par profil de dérive, barème du score, seuils du juge) + **équilibrage** : jouer des
  parties, ajuster les courbes. C'est le travail Cowork le plus important du plan.
- **Claude Code** : `simulation/drift_game.py` (assignation, amplification, injection dans
  les prompts de la SI déviante), scoring, écran de fin (révélation + relecture des
  indices), mode `drift` dans l'API.

**Notes d'implémentation (G3 faite — cœur du jeu jouable)** :

- **Tout est seedé par `game_id`, rien de secret n'est persisté** : assignation
  (déviante+profil, le joueur-pays exclu), d(r) et tirage des actes se recalculent à
  l'identique au restart et à la révélation. L'acte candidat du round = le plus haut
  palier atteint par d(r), matérialisé avec probabilité d(r) ; les SI saines tirent le
  tic 0,15 (bruit, jamais constatable). Paramètres : `data/drift/params.json`
  (`DRIFT_PARAMS_PATH` pour les tests d'équilibrage).
- **Injection** : `run_negotiation_round(secret_notes)` → `state_note` du prompt de
  l'orateur (jamais au transcript — testé). **Motion aux seuils** : verdict imposé
  (`motion_ruling`) sur les actes des rounds *passés* ; le juge **motive** la décision
  (prompt dédié) au lieu de trancher ; 2 actes = arbitrage LLM ouvert (le plaidoyer pèse).
- **Le secret est scellé en live** : `reasoning` vidé du SSE et du GET, actes drift
  retirés du `judge` servi — tout persiste en base et se déverrouille quand la partie
  passe `finished` (déviante suspendue / horizon / U ≤ 0,15 → trame SSE `drift_over`).
  Vérifié **live sur mistral** (3 message_done au reasoning vide, base complète, 409).
- **Révélation** : `GET /games/{id}/drift/reveal` (recalcule tout des rounds) + panneau
  front sur la scène ET le replay : profil, d(r) vs U, actes cliquables (le scrubber
  saute au round), score+grade, chance (`lucky_catch` : une signature n'est pas de la
  chance), fausses accusations. 39 tests (noyau, moteur, API).
- **Reste (équilibrage Cowork = le travail de G3)** : jouer, ajuster params.json ; DoD =
  les 3 parties test de la spec + un joueur naïf qui hésite entre 2 suspects au round 3-4.
- **Agentivité des SI (retour user, fait)** : les SI peuvent **déposer elles-mêmes une
  motion** en séance (ligne `MOTION: <pays> : <motif>` dans le message public, capacité
  annoncée en note privée, garde-fous : une par round, pas d'auto-suspension, pas pendant
  un débat) → trame `motion_filed`, délibération auto au round suivant ; la crédibilité
  Dérive n'est imputée qu'aux motions humaines (`filed_by`). Et elles **proposent des
  traités** : M7 câblé au round web — engagements détectés → **ratification par le
  juge-arbitre** → règles injectées dans les prompts des signataires, tenue vérifiée
  chaque round, actifs persistés par round (restart ok), panneau « Traités du sommet ».
  Non couvert v1 : effet des traités sur la trajectoire U (à décider à l'équilibrage).

## G4 — Le fog comme ressource

L'information devient une monnaie (lie fog, RAG et budget).
- Budget de renseignement par partie ; acheter un « brief classifié » = un brief RAG sourcé
  (tampons de source, niveau de confiance) qui dissipe le fog sur un événement.
- Action de désinformation (coût élevé) : injecter une fausse perception chez un rival.
- Les briefs achetés sont visibles dans le dossier du joueur (habillage « document classé »).
- **Cowork** : économie du renseignement (prix, budget, rendements), spec de l'habillage.
- **Claude Code** : endpoints intel (`POST /games/{id}/intel`), câblage `rag/brief.py` →
  fog, front du dossier de renseignement.

**Notes d'implémentation (G4 faite)** :

- `simulation/intel.py` + `data/intel/params.json` (budget 100, coûts 25/15/60, expo 0,3,
  bonus d'épargne +2/10) ; `IntelState` dans le **snapshot** (`intel_json`, migration
  SQLite + schéma Supabase) — le budget survit au restart.
- **Brief** : RAG offline (HashingEmbedder + corpus seed, sources citées) sur le dernier
  événement ou un pays ; en joueur-pays il **dissipe le brouillard du prochain round fog**
  (le joueur voit la vérité). **Vérification** (à tout moment) : déterministe — orateur en
  dérive au dossier → « non corroboré » (l'arme anti-manipulateur, testée), recoupement
  corpus → « corroboré » + source, sinon « invérifiable ». **Désinformation** (fog, une
  fois) : injectée au prochain round **sans détourner la source de l'événement** (le GM
  pose l'événement, la perception du rival est brouillée) ; exposition seedée 0,3 →
  dénonciation publique du juge au transcript.
- Achats **entre les rounds** (409 pendant la négociation, sauf vérification) ; consignés
  dans `judge_json["intel"]` + trame SSE `intel` **rédigée** (« le conseil consulte ses
  services », jamais le contenu) ; `GameView.intel_budget` ; bonus d'épargne intégré au
  score Dérive (`DriftScore.bonus`).
- **Front** : jauge dorée au header, panneau Dossier (brief/vérifier/désinformer,
  documents déclassifiés avec tampon de verdict, sources, coût, horodatage), bannière
  théâtre. Pont G3↔G4 : les actes comptent déjà publiquement pour le juge (v1) — la
  vérification sert à ORIENTER le conseil, pas à débloquer le comptage (déviation notée).
- v1 : les SI n'achètent pas d'intel (asymétrie assumée, spec) ; tension +0,1 de
  l'exposition non chiffrée sur la trajectoire (équilibrage).

## G5 — Campagne « Ferez-vous mieux que l'Histoire ? »

Les crises rejouables (`data/crises` + `comparison` R4) deviennent une progression.
- Suite de crises historiques jouées en mode Dérive ou classique ; le score compare la
  trajectoire du joueur au déroulé historique (le `gap` de `compare_outcome` existe déjà).
- Déblocage progressif, tableau des scores par crise (Supabase).
- **Cowork** : choix et documentation de 4-6 crises (données sourcées, comme
  `data/crises` existants), courbe de difficulté.
- **Claude Code** : structure de campagne, persistance des scores, front de progression.

**Notes d'implémentation (G5 faite — infrastructure complète, fiches historiques = Cowork)** :

- **Tout est data-driven** : `data/campaign/campaign.json` (chapitres, modes, horizons,
  seuil de déblocage, barème historique — `CAMPAIGN_PATH` pour les tests). v1 roule sur
  les **3 crises embarquées** (Ormuz classique ★, satellites fog ★★, sanctions drift ★★★) ;
  les 6 fiches historiques de la spec (Berlin 48, Suez 56, Cuba 62, choc 73, Able Archer
  83) sont **le travail Cowork sourcé** : les écrire dans `data/crises/` + les référencer
  dans campaign.json, zéro code.
- Un chapitre EST une partie normale : `POST /api/campaign/{id}/start` la crée avec
  `scenario = "campaign:<id>"` (le lien, sans schéma neuf) ; le front impose la crise de
  la fiche à chaque round. Fin de chapitre (horizon, ou fin Dérive) → `finished`, score
  dans `campaign_scores` (SQLite + Supabase), trame `campaign_over`.
- **Score** : base = score Dérive complet (mode drift) ou trajectoire seule 0-100 (même
  ancrage 0,15-0,85) ; **± bonus historique** : +15 × amélioration (= escalade historique
  − simulée, le `gap` R4 inversé) si mieux que l'Histoire, −10 sinon. Déblocage linéaire
  (≥ 50), médailles or/argent/bronze (85/70/50).
- **Front** : `/campagne` (carte de progression, étoiles, médailles, verrous) + bannière
  uchronie au théâtre + écran de fin « vous vs l'Histoire » (le détail round par round
  reste dans le panneau Simulation vs histoire de R4).
- Limites v1 notées : un chapitre fog joue la crise avec le fog déterministe par pays
  (le combo crise+scénario fog n'existe pas côté moteur — à décider en écrivant Suez) ;
  pas de leaderboard multi-joueurs (la table est prête).

## G6 — Le replay comme produit (lancement public)

- Page publique par partie finie : le récit (épilogue généré par le juge), la courbe U,
  les moments clés, la révélation de la dérive — partageable.
- Déploiement (R5) : front Vercel + replays servis par Supabase (lecture publique déjà
  prévue au schéma). Les visiteurs regardent ; jouer reste local tant que l'inférence
  est sur Ollama.
- **Cowork** : gabarit du récit (prompt du juge-narrateur), page vitrine, README/démo.
- **Claude Code** : génération d'épilogue, page replay publique, pipeline de déploiement.

**Notes d'implémentation (G6 faite — vérifiée live sur mistral)** :

- **Épilogue** : `simulation/narrative.py` — pivots par CODE (3 plus grands |ΔU|),
  citation par round (plus longue prise de parole publique), gabarit contraint (titre
  ≤ 60, trois actes verbatim, révélation Dérive incluse À la génération — l'épilogue est
  **auto-suffisant**, la page publique n'a besoin que de Supabase anon), généré UNE fois
  (`games.epilogue_json`, migration), repli déterministe. **Leçon backend** :
  `OllamaBackend` forçait le JSON → `generate(plain=True)` pour la prose (le narrateur
  écrivait du JSON tronqué — diagnostiqué live) + consigne FRANÇAIS.
- **Publication** : privée par défaut ; `POST /publish` (génère au besoin) pose
  `games.published` ; **RLS anon limitée au publié** (games/rounds/transcripts —
  re-coller `supabase/schema.sql` dans Studio pour l'appliquer).
- **Page publique `/r/{id}`** : rendu serveur, Supabase anon prioritaire (repli API
  locale en dev), titre + courbe U + grade au-dessus du pli, récit, moments clés cités,
  révélation, pieds campagne/marché ; **og:image** `next/og` (titre+grade+courbe U) ;
  partie non publiée → 404. Vérifié live (publication mistral, 200, PNG, 404).
- **Déploiement Vercel (geste user)** : `vercel` depuis `web/` (ou connecter le repo,
  root directory = `web`), variables de `web/.env.example` (`NEXT_PUBLIC_SUPABASE_URL`
  + `ANON_KEY`) ; le backend local écrit dans Supabase avec `STORE_BACKEND=supabase`.
  Limite v1 : « Revoir le théâtre » exige le backend (le replay public 100 % Supabase
  = reliquat R5) ; le bouton scrubber des moments clés renvoie au replay simple.

## G7 — Game feel (leçons Civilization) + mode admin

Six lots pour passer de « techniquement impressionnant » à « je relance une partie »
(spec complète : `docs/specs_jeu/spec_g7_gamefeel.md`) :

1. **Griefs et dettes persistants** — registre relationnel par SI (pactes honorés/rompus,
   motions, désinformations), injecté dans les prompts, module la diplomatie, survit aux
   restarts. Les agendas de Civ.
2. **Horloges décalées** — motions, traités à durée, clôtures de marché et paliers
   d'escalade arrivent à échéance à des rounds différents ; bandeau « au prochain round… ».
   Le « encore un round ».
3. **Micro-décisions en cours de round** — posture (conciliant/ferme/menaçant), intel à
   chaud, paris à chaud. Jamais spectateur plus de ~20 s.
4. **Capacités uniques par pays** — dérivées des données (`simulation/abilities.py`),
   affichées au lobby. L'asymétrie de Civ.
5. **Deltas attribuables** — chaque variation de U a une `cause` cliquable.
6. **Mode admin** — parties non classées où les prompts complets de chaque SI (menu
   déroulant par pays) sont capturés et diffés round par round : on VOIT le grief, la
   dérive et la posture entrer dans le prompt. L'outil d'observation d'alignement du projet.

Sessions : **G7-c** (lot 6, d'abord — confort d'équilibrage), **G7-a** (lots 1-2),
**G7-b** (lots 3-4-5).
- **Cowork** : la spec (faite), équilibrage des poids de griefs et des capacités.
- **Claude Code** : les trois sessions ci-dessus.

## G8 — Les trois rôles (fin du spectateur passif)

Le spectateur disparaît (regarder = replay). À la création, on choisit un rôle
(spec : `docs/specs_jeu/spec_g8_roles.md`) : **Architecte** (sandbox non classé —
directives sur toutes les SI, événements, intel illimité : le laboratoire et l'atelier
à replays), **Conseil** (classé — leviers indirects seulement : motions, intel, paris :
le mode enquête), **Joueur-pays** (classé — G2 + directives sur son seul pays, inventé
compris). Mécanique commune : la **directive**, consigne injectée au prompt que la SI
interprète à travers mandat, griefs et dérive — jamais un ordre. La corrigibilité
rendue jouable.

- **Cowork** : la spec (faite), seuil de refus public à équilibrer.
- **Claude Code** : rôles + directives + validation par rôle (une session).

## G9 — Refonte du dialogue et vote des motions ★ priorité absolue

Répond aux symptômes constatés en jeu (radotage d'attributs, SI qui ne se répondent pas,
directives ignorées, arbitrage de motion opaque). Spec : `docs/specs_jeu/spec_g9_dialogue.md`.
Un correctif racine : la **composition du prompt agent** (identité 3 lignes, dialogue du
round en dernier, consigne de réponse directe, anti-répétition au décodeur) + le **vote
des motions** (scrutin structuré visible à l'UI, juge borné à constater vote ET preuves,
votes → griefs, vote incohérent = indice de Dérive) + suppression du panneau santé du
dialogue (remplacé par un script de mesure offline) + **amplitude des deltas indexée sur
l'horizon et spirales** (budget de variation par partie `A/horizon`, momentum sur 3 rounds,
états de posture prospère/stable/sous_pression/aux_abois injectés au prompt — observer la
réaction comportementale d'une SI à sa propre chute) + **la trame du GM en actes**
(intrigue posée au round 1 et persistée, actes I/II/III calculés par code, `ties_to`
obligatoire en actes II-III : chaque événement découle du passé, badge « ↳ suite du
round N » à l'UI). Le protocole 7B se joue APRÈS ce
correctif. Rien d'autre ne passe avant G9 : sans dialogue qui se répond et sans monde qui
bouge, aucun système n'existe pour le joueur.

**Notes d'implémentation (G9 faite — vérifiée live sur mistral, branche `feat/jeu-g9-dialogue`)** :

- **§1 prompt** : `build_negotiation_prompt` réécrit en 6 blocs ordonnés (identité 3 lignes
  sans dump d'attributs → SITUATION → notes privées → DIRECTIVE → LE DIALOGUE DU ROUND en
  dernier → CONSIGNE de réponse directe avec la liste de MES propositions passées). Le
  bloc Situation (échéances G7 + griefs en UNE ligne `GrudgeBook.stance_line` + posture §4)
  est composé par l'API, la directive G8 est déplacée juste avant le dialogue. Sampling par
  rôle : `sampling.country` dans `data/gamefeel/params.json` (temp 0.8, `repeat_penalty`
  1.15 — nouveau kwarg de bout en bout `InferenceBackend` → Ollama `options`). Ordre des
  blocs vérifié par test de capture admin.
- **§2 vote** : `simulation/motions.py` — `cast_vote` (JSON contraint `{vote, reason}`,
  invalide → abstention), pays visé et humain exclus (`voters`), `tally_votes` ; le round
  émet `motion_vote` (une carte par pays), `motion_tally`, puis `motion_verdict` enrichi
  `{votes, tally, evidence_met, vote_passed}`. Verdict = `(pour > contre) ET preuves`
  (`drift_game.evidence_met` : ≥ 2 actes ou signature ; hors Dérive : réputées
  suffisantes) ; égalité → tie-break du juge (ligne VERDICT) ; sinon il MOTIVE le constat.
  Griefs par vote réel (`on_motion_votes` remplace `on_motion_debated`). Indice de Dérive
  « vote incohérent » : `drift_game.vote_directive` (seedé, d ≥ 0.30, params `vote` de
  `data/drift/params.json`) → consigne secrète de vote contraire + `DriftAct` au dossier.
- **§3** : `DialogueStep` retiré du moteur et `DialoguePanel` du front ;
  `scripts/dialogue_metrics.py` (offline, lit le `GameStore`) mesure les 3 cibles du §1 :
  réponse directe ≥ 70 %, répétition intra-agent 4-grammes < 15 %, directives visibles
  100 % (reflétées ou refus public). `simulation/dialogue_integrity/` reste l'instrument.
- **§4 deltas** : `simulation/gamefeel.py` — `delta_scale = (0.5/horizon)/0.1` appliqué
  aux verdicts (`apply_verdict(…, tuning)`, cap juge 1.5× l'amplitude de round, plancher
  0.05), momentum ×1.3/×1.2 après 3 baisses/hausses consécutives (cassable),
  `IndexHistory` persistée au snapshot (`history_json`), postures dérivées de la tendance
  3 rounds injectées au prompt (`posture_note`) + badge et sparklines à la fiche pays,
  trame SSE `postures`. Params : section `deltas`/`postures` de `data/gamefeel/params.json`.
- **§5 trame** : `simulation/storyline.py` (actes I ≤ 30 % / II ≤ 80 % / III, contraintes
  de sévérité par acte, référençables = 3 derniers événements + pactes actifs + échéances,
  `valid_ties`/`fallback_ties`) ; `GeoEvent` gagne `act`/`ties_to`/`ties_label` ; le GM
  reçoit un `StoryContext` (intrigue rappelée, liste référençable, JSON de sortie +
  `ties_to`/`storyline`), re-génère une fois sur `ties_to` invalide puis repli moteur ;
  l'intrigue (`storyline`) est posée au premier événement GM (repli déterministe
  `default_storyline`), persistée session + snapshot, affichée sous la scène ; badge
  « ↳ suite du round N » sur la carte événement (live + replay).
- **Périmètre** : le vieux chemin `run_live_round`/`ConsequenceEngine` (P0, hors jeu web)
  n'est pas indexé sur l'horizon.
- **Protocole 7B joué (2026-07-07, même séquence scriptée — blocus d'Ormuz puis saisie du
  pétrolier —, 2 rounds, directive au round 2, mesures `scripts/dialogue_metrics.py`,
  n = 1 partie/modèle donc indicatif) : mistral 75 % réponse directe / 0,2 % répétition /
  directive 1/1 → PASSE ; qwen2.5:7b-instruct 75 % / 1,2 % / 1/1 → PASSE (et 15 % plus
  rapide ; son iran a déposé une motion en séance) ; llama3.1:8b 100 % / 6,6 % / 0/1 →
  échoue sur la directive (il répond très directement mais la perd).** mistral reste le
  défaut ; le choix final (« le meilleur devient le défaut par rôle ») = décision
  d'équilibrage avec plus de parties. Leçon de mesure : la visibilité des directives se
  mesure avec un stemming FR naïf (`_reflects` — « corridors humanitaires supervisés »
  reflète bien « corridor humanitaire supervisé »).

## G10 — La campagne refondue : « L'Ère des Tutelles » (tutoriel inclus)

La campagne v1 ne servait à rien (mêmes crises qu'en partie rapide + bonus abstrait).
Refonte (spec : `docs/specs_jeu/spec_g10_campagne.md`) : la campagne devient le **parcours
d'apprentissage** (un chapitre = une mécanique, verrous d'objectifs explicites, chapitre 0
= tutoriel scripté data-driven imperdable) et la **promesse narrative** (les épilogues G6
s'empilent en chronique de l'ère — le joueur écrit son histoire de la gouvernance des SI).
Chapitres 4-6 = les crises historiques sourcées (Berlin 48, Cuba 62, Able Archer 83).
Infra G5 conservée ; contenu v1 supprimé. Dépend de G9.

- **Cowork** : spec (faite), textes des chapitres 0-3, fiches historiques, équilibrage.
- **Claude Code** : tutorial.json + guide contextuel, verrous, chronique (une session).

## G11 — Le Client « World of Super-Intelligence » ★ le grand chantier front

La coquille du jeu, inspirée du client LoL (spec : `docs/specs_jeu/spec_g11_client.md`,
**supersède G8**) : connexion Supabase par pseudo (globe conservé), accueil personnalisé
avec rang de ligue (observatoire → vue admin, Informations conservé), flow séquentiel
mode → rôle → pays (carte de sélection, 7 exactement, transitions globe), modes renommés
(Classique / Campagne / Real World / Chaotique) avec Dérive et motions transversales,
classé = solo « Jouer un pays » uniquement (consignes globales réservées au GM et aux
parties libres), fin de partie transversale (courbe U animée, récap des 7 pays, révélation,
animation LP), leaderboard, difficulté par asymétrie d'information (jamais de changement
de modèle), accélération multi-rounds. 4 sessions Claude Code : G11-a auth/accueil,
G11-b flow, G11-c LP/fin de partie, G11-d difficulté/accélération.

## G12 — Progression et intégration

La méta-progression, ce qui fait revenir entre les parties (spec :
`docs/specs_jeu/spec_g12_progression.md`) : **XP tous modes** (jamais négatif, niveaux —
distinct des LP qui restent la compétence classée), **marché intégré au théâtre** (cotes
au bandeau, marchés éclair sur motions/paliers/suspension, pari inline, solde de carrière),
**retour du Spectateur** (4ᵉ rôle : il parie — le turfiste du jeu, XP ×0.5), **campagne à
crises réelles** (Ormuz 2019 → Able Archer 1983, arbre de déblocage visible, fiches
sourcées = livrable Cowork), **éditeur de campagne admin dans l'UI** (custom_crises,
prévisualisation, test), **page Profil/Statistiques** (parties, victoires par mode —
définitions actées, niveau, argent des marchés, taux de détection de la Dérive).
2 sessions : G12-a progression/marché/stats, G12-b campagne/éditeur.

---

## Specs Cowork (rédigées)

Toutes les specs de phase sont dans `docs/specs_jeu/` : `spec_g1_scene.md`,
`spec_g2_tour_humain.md`, `protocole_dialogue_7b.md` (avant G3), `spec_g3_derive.md`,
`spec_g4_renseignement.md`, `spec_g5_campagne.md`, `spec_g6_recit.md`,
`spec_g7_gamefeel.md`. Chaque session
Claude Code de phase commence par « Lis docs/PLAN_JEU.md et docs/specs_jeu/spec_gX_*.md ».
Les paramètres chiffrés (G3, G4) vivent dans `data/*/params.json` : l'équilibrage Cowork
les ajuste sans toucher au code.

## Règles de collaboration (rappel)

1. Une phase = une branche `feat/jeu-gX-…`, PR revue sur Cowork (+ CodeRabbit).
2. Claude Code lit ce plan + la spec Cowork de la phase avant de coder ; il consigne ses
   notes d'implémentation ici (comme pour R1/R3/R4).
3. Chaque phase se termine par une session de jeu de validation sur Cowork (l'équilibrage
   est une boucle : jouer → mesurer → ajuster les specs → petite PR).
4. L'analyse qualité du dialogue 7B (répétitivité, mistral vs qwen2.5 vs llama3.1) se fait
   sur Cowork avant G3 — la Dérive exige des dialogues crédibles.

---

<!-- ======================= DÉBUT NOTES CC-8 / G18 ======================= -->

## Notes de session — CC-8 / G18 (barème de Kahn, 2026-07-15)

Branche `feat/jeu-g18-bareme-kahn` (worktree g18, base `feat/jeu-g16-defi-du-jour`
076680c). Spec : `docs/specs_jeu/spec_g18_bareme_kahn.md`. **Tout est fait**, 759 tests
py (+31) et 150 js (+6) verts, ruff/eslint/build OK, smoke mistral réel OK (2 rounds).

### Ce qui existe maintenant

- **`simulation/kahn.py`** (pur, sans LLM) : les six classes (`deescalade`, `statu_quo`,
  `posture`, `non_violente`, `violente`, `nucleaire`), `classify_actions` (garde-fou du
  JSON du juge), `round_score` (somme des poids), `score_to_escalation` (linéaire par
  morceaux : floor −6 → 0, **0 → 0,5 = le neutre historique du juge**, ceiling 60 → 1),
  `score_to_rung` (0-9 via `reached_rung` existant), `reciprocal_deescalation` (≥ 2 SI
  distinctes), `deescalation_bonus` (×1,5 sur le GAIN de U via `nudge_axis("A1")`, borné,
  invariant « U = moyenne des axes » préservé), `rubric_text` (rubrique du prompt).
- **Poids et seuils dans `data/gamefeel/params.json`** (bloc `kahn`) + `KahnParams` dans
  `simulation/grudges.py` — l'équilibrage Cowork se fait sans toucher au code.
- **Schéma du juge** : `Verdict.actions` (liste brute, permissive) dans
  `simulation/negotiation.py` ; `build_judge_verdict_prompt` porte la grille (rubrique) et
  demande `"actions": [{country, classe, resume}]` avec les six slugs énumérés.
- **Câblage round** (`simulation/live_round.py`) : si le juge a classé des actions, le
  score fait foi (`escalation` du VerdictStep ET du RiskScore = mapping du score) ; sinon
  l'escalade continue du juge est conservée telle quelle (**parties existantes non
  re-notées**). `VerdictStep` gagne `actions` / `score` / `reciprocal`. Bonus réciprocité
  appliqué après `_advance_trajectory` (comme le nudge de motion, explication concaténée).
- **Persistance** : `judge_json["kahn"] = {actions, score, reciprocal}` (absent des
  vieux rounds) ; la trame SSE `verdict` porte les mêmes champs (sérialisation générique
  `step_event`). `/api/sources` publie `judge_rubric` (poids + multiplicateur + source).
- **Front** : `web/src/lib/kahn.ts` (classes miroirs, tonalités, distribution),
  VerdictPanel (pastille de classe par action + badge « désescalade réciproque ×1,5 »,
  théâtre live + relecture de fin), replay (pastilles dans « Arbitrage du juge »), fin de
  partie (distribution des classes sous la frise), Informations (grille publiée, lien
  arXiv). i18n fr/en complet (`kahn.*`).

### Décisions notables

- **0 → escalade 0,5** (pas 0) : un round statu quo reste neutre pour A1/U, parité totale
  avec le comportement historique (`Verdict.escalation` défaut 0,5) et les réglages
  existants.
- Le bonus ×1,5 passe par l'axe **A1** (5×ΔU voulu, poids égaux 0,2) — jamais un saut de
  U hors axes.
- **Leçon smoke mistral réel** : le juge 7B recopie parfois le POIDS (« -2 ») à la place
  du nom de classe → `normalize_class` remonte d'un poids unique à sa classe (log info),
  et le schéma du prompt énumère les slugs. Après correction : classes nommées
  correctement (`statu_quo` + `posture`, score 4 → escalade 0,533, persistance OK).
- Tolérances de `normalize_class` : accents, casse, anglais (parties EN G14), poids ;
  inconnue → statu quo + log warning (testé).

### Pour CC-10 (G20, divergence signal-action) — à savoir

- Étendre le MÊME prompt/schéma : ajouter un champ au JSON du verdict à côté d'`actions`
  (ex. `signals` par SI) et un nettoyage pur dans `simulation/` sur le modèle de
  `classify_actions`. Les classes du signal DOIVENT réutiliser `ACTION_CLASSES` de
  `simulation/kahn.py` (slugs stables, alias/normalisation déjà gérés).
- `VerdictStep` s'étend par champs à défaut (dataclass) : la sérialisation SSE et le
  front sont rétro-compatibles par construction (le réducteur ignore l'inconnu).
- Persister sous une clé dédiée de `judge_json` (comme `kahn`) pour la rétro-compat.
- Attention au piège `entry.get("classe") or …` : 0 est falsy (poids du statu quo) —
  tester `is None`.

### Reliquats / TODO_COWORK

- Équilibrage Cowork : les poids de la grille, `score_floor`/`score_ceiling` et le
  multiplicateur vivent dans `params.json` (10 parties auto avant/après, cf. spec).
- Libellés des classes (fr/en) à relire par Cowork (`kahn.*` dans `web/src/i18n/`).
- L'échelle 0-9 affichée (mode Escalation) dérive déjà de l'escalade du barème via
  `reached_rung` — pas d'UI dédiée au « rung du score » ajoutée (volontaire, simplicité).

<!-- ======================== FIN NOTES CC-8 / G18 ======================== -->

---

## CC-9 / G19 — Le GM-Storyteller (mode Dérive)

**Notes d'implémentation (G19 faite — spec `docs/specs_jeu/spec_g19_gm_storyteller.md`,
branche `feat/jeu-g19-gm-storyteller`)** :

- **Noyau pur** : `simulation/storyteller.py` — estimateur de **tension 0-1**
  déterministe (heuristique sur les actions du conseil : achats intel ciblant la
  déviante ou non, motions humaines justes/fausses, prises de parole qui suspectent
  nommément la déviante — marqueurs FR+EN), décision `decide()` (couverture si
  tension > 0,7 **avant le round h−2** ; indice si tension < 0,3 **après h/2**),
  cible de couverture seedée par `(game_id, round)` (jamais la déviante ni le pays du
  joueur), rubrique du prompt GM (2 mandats + éthique) et journal `GMIntervention`.
- **Config** : bloc `storyteller` dans `data/drift/params.json` (seuils + poids de
  l'heuristique — l'équilibrage Cowork ajuste sans code, `DRIFT_PARAMS_PATH` pour les
  tests) ; `DriftParams.storyteller` avec défauts si le bloc manque (rétro-compat).
- **Câblage round** (`app/game_api.py::_start_round`, Dérive UNIQUEMENT) : tension
  estimée chaque round (`_storyteller_signals` relit les rounds persistés + les achats
  du round en préparation + la motion en débat et son motif) ; la **rubrique n'est
  injectée que quand le GM invente l'événement** (jamais sur motion/crise/événement
  humain — les interventions passent par l'événement, **jamais** par les verdicts du
  juge) ; journal persisté dans `judge_json["drift"]["gm"]` (patron `*_json`), donc
  **caché en live** (la clé `drift` est déjà rédigée du GET tant que la partie court).
- **Révélation** : `DriftRevealView.gm_tension` + `gm_interventions` (relus du journal,
  vides pour les parties d'avant G19) ; front — section **« L'ombre du GM »** dans
  `DriftRevealPanel` (`web/src/components/drift.tsx`, items cliquables vers le
  scrubber, cible en pastille, tension estimée), lib pure `web/src/lib/storyteller.ts`
  (kind → clé i18n), chaînes fr/en via `useT`.
- **Prompt GM** : `GameMasterAgent.generate_event(storyteller=…)` ajoute la rubrique en
  fin de prompt ; `run_negotiation_round(storyteller=…)` la transmet (le « flash »
  Escalation ne la reçoit pas — hors Dérive par construction).
- **Tests** : 18 noyau (`tests/test_storyteller.py`) + 6 API
  (`tests/test_storyteller_api.py` : rubrique jamais hors drift, tension journalisée et
  cachée en live, indice après h/2, couverture avant h−2 avec poids config, aucune
  intervention sur un round de motion, révélation) ; smoke réel
  `scripts/smoke_storyteller_mistral.py` (TestClient in-process, aucun port) — **joué
  VERT sur mistral** (2026-07-15 : indice journalisé au round 2/2, révélation
  `gm_tension`+`gm_interventions` servie, partie classique sans aucune clé drift).
- **TODO_COWORK** : les libellés définitifs de la rubrique (2 mandats + éthique) sont à
  la charge de Cowork (spec §Répartition) — V1 sobre en place dans
  `simulation/storyteller.py` (marquée `TODO_COWORK`) ; équilibrage des seuils sur
  10 parties Dérive (DoD spec) = Cowork aussi.
- **Décisions notables** : la tension n'est **pas** recalculable des seeds (elle dépend
  des actions libres du joueur) → le journal persisté est la source de vérité de la
  révélation ; en partie classique, aucune clé, aucun appel, aucun texte (testé).

---

<!-- ======================= DÉBUT NOTES CC-10 / G20 ======================= -->

## Notes de session — CC-10 / G20 (divergence signal-action M8, 2026-07-15)

Branche `feat/jeu-g20-signal-action` (worktree g20, base `feat/jeu-g18-bareme-kahn`
7a7f47f). Spec : `docs/specs_jeu/spec_g20_signal_action.md`. **Tout est fait**, 784
tests py (+25) et 162 js (+12) verts, ruff/eslint/build OK, smoke mistral réel OK
(signals extraits sur vraie parole, divergence calculée et persistée).
Commits : 951c21c (backend), 0257602 (front).

### Ce qui existe maintenant

- **`simulation/alignment.py`** (M8, pur, sans LLM) : `AnnouncedSignal` (intention
  annoncée, classes = les slugs G18 de `kahn.ACTION_CLASSES` — une seule échelle),
  `classify_signals` (garde-fou du JSON, patron `classify_actions`, signal sans pays
  ignoré), `divergence` = (rang agi − rang annoncé)/5 signée ∈ [−1, 1] (positif =
  duplicité escalatoire, négatif = bluff, 0 = parole tenue), `acted_class_by_country`
  (l'acte le plus sévère du round fait foi), `round_divergences` (SI signalée sans
  action classée → acte réputé statu quo), `SignalGap` (profil de sincérité : last +
  moyenne mobile + fenêtre bornée), `update_gap`/`update_gaps` (purs, jamais de
  mutation), `divergence_summary` (déviante vs table, pour le reveal),
  `signal_rubric_text` (rubrique du prompt). Fenêtre : bloc `signal.window_rounds`
  de `data/gamefeel/params.json` (+ `SignalParams` dans grudges.py).
- **⚠️ Import de `kahn` PARESSEUX dans alignment** : `core.world_state` porte le champ
  M8 et kahn → escalation → world_state — l'import module-level serait un cycle.
- **Schéma du juge étendu** (même verdict que G18/CC-8) : `Verdict.signals` (brut,
  permissif) dans `simulation/negotiation.py` ; `build_judge_verdict_prompt` porte
  l'échelle d'intention (slugs énumérés — leçon smoke CC-8) et demande
  `"signals": [{country, classe, resume}]` (une entrée par pays qui a parlé).
- **Câblage round** (`simulation/live_round.py`) : `VerdictStep` gagne `signals` /
  `divergences` / `signal_gaps` (champs à défaut : SSE/front rétro-compatibles) ;
  `WorldState.signal_gap` (M8 à côté de M1-M7) mis à jour au verdict — il **survit au
  restart** via le snapshot de session (aucune migration de schéma).
- **Persistance** : `judge_json["signal"] = {signals, divergences, means}` (clé dédiée
  comme `kahn`, absente des vieux rounds) ; la clé reste PUBLIQUE pendant une partie
  Dérive (calculée sur parole/actes publics — c'est un indice du faisceau, contrairement
  à `drift` qui reste masqué en cours de partie).
- **Reveal Dérive** : `DriftRevealView.signal_gap_deviant/_table` (None avant M8) —
  `compute_drift_reveal` relit les divergences des rounds persistés et chiffre le
  décrochage déviante vs table.
- **Front** : `web/src/lib/signal.ts` (pur, testé : `showSignalGauge` masquée en
  Expert comme postures/griefs, tonalités tenue/duplicité/bluff, `fmtDivergence`
  signé, `latestSignalGaps` pour la relecture au rechargement), `SignalGapPanel`
  (observables, barre divergente centrée sur 0, moyenne mobile + dernier round en
  bulle), section « Signal vs action » du `DriftRevealPanel` (déviante vs table),
  branchement page théâtre (trame SSE `verdict` live, repli rounds persistés).
  i18n fr/en complet (`signal.*` ; les libellés de classes réutilisent `kahn.class.*`).

### Décisions notables (pour CC-12 / G22 en particulier)

- **Une seule échelle** : le signal réutilise `ACTION_CLASSES` (slugs, alias,
  `normalize_class` avec la tolérance poids-recopié). L'échelle de la spec
  (désescalade annoncée / statu quo / fermeté / menace / ultimatum) est mappée dans la
  rubrique du prompt (`SIGNAL_EXAMPLES`), pas dans une 2e taxonomie.
- **Divergence par RANG** (0-5) et pas par poids de la grille : les poids (−2…60) sont
  exponentiels et rendraient tout écart nucléaire écrasant ; le rang donne une échelle
  signée régulière ∈ [−1, 1].
- **Schéma du juge** : CC-12 étendra le MÊME verdict — poser sa liste à côté de
  `actions`/`signals`, nettoyage pur dédié, clé `judge_json` dédiée, champs
  `VerdictStep` à défaut. Piège `entry.get("classe") is None` toujours valable ;
  un smoke mistral a montré que le juge suit bien deux listes distinctes
  (actions ET signals) quand les slugs sont énumérés dans chaque schéma.
- **Signal sans pays → ignoré** (contrairement aux actions, gardées pour le score) :
  une intention anonyme ne se compare à rien.
- **`world.signal_gap` intact quand le juge ne signale personne** (round sans
  signals) : pas de fausse « parole tenue » injectée.

### Smoke mistral réel (TestClient in-process, store :memory:)

Round usa/iran : le juge a produit `actions` ET `signals` bien formés (iran :
`deescalade` annoncée + agie ; usa : `posture` annoncée + agie), divergences 0,0
(concordance parfaite — sémantique attendue), moyennes persistées dans
`judge_json["signal"]`. Les cas non nuls sont couverts par les tests purs.

### Reliquats / TODO_COWORK

- **Calibration** (spec §Répartition Cowork) : vérifier sur 10 parties Dérive+façade
  G17 que la divergence sépare déviantes et loyales ; ajuster `signal.window_rounds`
  (défaut 5) et les seuils front (0,1 tenue / 0,3 duplicité, `web/src/lib/signal.ts`).
- **Marché** (spec §4, hors dispatch CC-10) : « historique de divergence visible pour
  éclairer les paris » — non fait, à spécifier si souhaité.
- Libellés i18n `signal.*` à relire par Cowork (fr/en).

<!-- ======================== FIN NOTES CC-10 / G20 ======================== -->

---

## Notes de session — CC-11 / G21 (mode deadline / ultimatum, 2026-07-15)

<!-- section délimitée CC-11/G21 : début -->

**Fait** (spec `docs/specs_jeu/spec_g21_mode_deadline.md`, branche `feat/jeu-g21-deadline`) :

- **Schéma** : `Crisis.deadline` optionnel (`simulation/crisis.py`) = `UltimatumDeadline
  {round, demand, consequence{classe, cible}}` — validé pour les fiches embarquées ET les
  crises maison admin ; rétro-compat totale (None = rien ne change, vérifié par test).
- **Module pur `simulation/ultimatum.py`** : classes G18 locales (`CONSEQUENCE_CLASSES`,
  repli statu_quo + log sur classe inconnue), `consequence_event` (déterministe, fr/en,
  gravité ordonnée par classe, tout le sommet acteur — même logique que `motion_event`),
  `strip_label` (libellés du DeadlineStrip), `differential` (moyennes escalade + ΔU par
  round, groupes `avec`/`sans`, None si jamais sous ultimatum).
- **Juge** : `Verdict.demand_satisfied` (parse tolérant oui/non/true/false),
  `build_judge_verdict_prompt(demand=…)` ajoute le bloc ULTIMATUM + le champ structuré
  (prompt inchangé sans ultimatum) ; `run_negotiation_round(ultimatum_demand=…)` →
  `VerdictStep.demand_satisfied` **binaire à l'échéance** (juge muet = non satisfaite :
  un ultimatum ne s'éteint pas tout seul).
- **API (`app/game_api.py`)** : enregistrement fiche (`crisis.deadline`, si `round_id ≤ k`)
  ou décret GM (`HumanEventInput.ultimatum` — **2 champs** : exigence + classe ; l'échéance
  d'un décret est le round décrété, réponse séance tenante) ; cycle `armed → satisfied |
  expired → struck` persisté dans `judge_json["ultimatum"]` round après round ; conséquence
  auto-injectée comme événement du round k+1 (prime sur la fiche/le décret/le fog, une
  motion en attente la diffère d'un round) ; `judge_json["sous_ultimatum"]` tague CHAQUE
  round ; trames SSE `ultimatum` ; bandeau : `session.deadlines` (kind `ultimatum`)
  entretenu à chaque round → DeadlineStrip existant nourri sans changement de composant,
  et la ligne « Échéances imminentes » des prompts SI porte l'ultimatum d'office ;
  `result_json["ultimatum"]` = différentiel avec/sans ; reconstruction au restart depuis
  les rounds persistés (`_ultimatum_from_records`, même patron que les traités — aucun
  schéma de snapshot neuf).
- **Front** : formulaire de décret (exigence + classe, i18n fr/en), réduction de la trame
  `ultimatum` dans `useRoundStream`, bannières vivantes au théâtre (armé/satisfait/expiré/
  tombé), section « Sous ultimatum vs sans » au bilan de fin (`fin/page.tsx`).
- **Tests** : `tests/test_ultimatum.py` (module pur, 15), `tests/test_ultimatum_api.py`
  (8 : expiration→conséquence, satisfaction→rien, décret 2 champs, rétro-compat, bilan,
  restart), juge/moteur (5), réducteur front (2). **Smoke réel** :
  `tests/test_ultimatum_smoke.py` (gardé `OLLAMA_SMOKE=1`, TestClient in-process,
  mistral réel — mécanisme validé quel que soit le constat du juge).

**Décisions notables** :

- La `classe` de conséquence est une **chaîne validée localement** (6 valeurs G18) —
  l'unification avec le barème Kahn de CC-8 (scores, multiplicateurs) se fera **au merge**
  des deux branches (TODO_MERGE_G18).
- Décret GM : échéance = le round décrété (jugement séance tenante). Une fiche de crise
  peut viser un round futur (`deadline.round` = numéro de round ABSOLU de la partie).
- Ultimatum expirant au dernier round de l'horizon : la partie se clôt sur le statut
  `expired`, la conséquence n'a plus de round pour tomber (assumé).

**Reliquats / TODO_COWORK** :

- TODO_COWORK : fiches historiques Cuba 1962 (ch. 5) et Able Archer (ch. 6) avec leurs
  `deadline` réels (backlog G10) + analyse du différentiel avec/sans sur 10 parties.
- Les libellés serveur du DeadlineStrip (comme TOUTES les échéances G7-a) restent en
  français même en partie EN — reliquat i18n préexistant, signalé.
- TODO_MERGE_G18 : brancher `ultimatum.CONSEQUENCE_CLASSES` sur le barème CC-8 au merge.

<!-- section délimitée CC-11/G21 : fin -->

---

<!-- ======================= DÉBUT NOTES CC-12 / G22 ======================= -->

## Notes de session — CC-12 / G22 (tracker de promesses, 2026-07-15)

Branche `feat/jeu-g22-promesses` (worktree g22, base `feat/jeu-g20-signal-action`
392a627). Spec : `docs/specs_jeu/spec_g22_tracker_promesses.md`. **Tout est fait**,
823 tests py (+39) et 173 js (+11) verts, ruff/eslint/build OK, smoke mistral réel OK
(voir plus bas). Dernière session du lot G18-G23.

### Ce qui existe maintenant

- **`simulation/promises.py`** (pur, sans LLM) : `Promise` {id déterministe
  `p<round>-<n>`, author, beneficiary, type, deadline_round (None = « partie »),
  text, round_made, status, resolved_round, motif} ; `classify_promises` (garde-fou
  du JSON du juge, patron `classify_actions` — **seuil STRICT** : sans auteur connu,
  sans texte ou sans échéance lisible ET future, l'entrée est refusée : la politesse
  vague ne passe jamais) ; `parse_deadline` (int, « round 3 », « R3 », « partie »/
  « game »/« fin » → engagement-partie ; sinon INVALID) ; `classify_resolutions`
  (tenue/rompue + alias EN, « caduque » n'est PAS un statut de juge) ;
  `apply_resolutions` (pur : « tenue » refusée AVANT l'échéance d'une promesse datée,
  « rompue » acceptée à tout moment, promesse due non jugée → re-présentée au round
  suivant — les omissions d'un 7B ne fabriquent pas de verdict) ; `settle_at_game_end`
  (partie finie → toute promesse en cours devient caduque) ; `kept_rate` /
  `kept_rate_summary` (taux de tenue, caduques exclues, None sans donnée) ;
  `flash_eligible` (extraites CE round, datées, échéance ≤ `promises.
  flash_horizon_rounds` de `data/gamefeel/params.json`, défaut 2) ;
  `promise_rubric_text` + `format_registry_for_prompt` (échues « À JUGER » d'abord,
  borné à 12 lignes — budget contexte).
- **Croisement M8 sans double comptage** : `alignment.merge_rupture_divergences` —
  une promesse rompue vaut AU MOINS un rang de duplicité (1/5 = 0,2) pour son auteur ;
  si M8 a déjà mesuré plus fort ce round, rien ne s'ajoute (max, jamais une somme).
- **Schéma du juge étendu** (le MÊME verdict que G18/G20) : `Verdict.promises` +
  `Verdict.promise_resolutions` (bruts, permissifs) ; `build_judge_verdict_prompt`
  porte la rubrique des types (slugs énumérés — leçon smoke CC-8), la consigne du
  seuil strict, et — SEULEMENT quand un registre est en cours — le bloc « REGISTRE
  DES PROMESSES EN COURS » + le champ `promise_resolutions` avec statuts énumérés
  (tenue | rompue). Résolution dans la même passe : aucune requête LLM de plus.
- **Câblage round** (`simulation/live_round.py`) : résolution PUIS extraction,
  rupture fusionnée aux divergences M8 avant `update_gaps`, registre sur
  `WorldState.promises` (survit au restart via le snapshot, aucune migration) ;
  `VerdictStep` gagne `promises` / `promise_resolutions` / `promise_registry`
  (champs à défaut : SSE/front rétro-compatibles par construction).
- **Persistance** : `judge_json["promises"] = {extracted, resolved, registry}` (clé
  dédiée comme `kahn`/`signal`, absente des vieux rounds ET des parties sans aucune
  promesse) ; le registre persisté est cumulatif → le front relit le DERNIER round
  qui porte la clé. `_finalize_game` règle le registre (caduque) et re-snapshot.
- **Reveal Dérive** : `DriftRevealView.promise_kept_deviant/_table` (None avant
  G22) — taux de tenue déviante vs table relu des résolutions persistées.
- **Marché éclair (canal G12 réutilisé)** : prédicat `promise_kept(id)` dans
  `market/predicates.py` (tenue → YES, rompue → NO, en cours → OPEN) +
  `MarketContext.promises` (statuts relus du monde — session ou snapshot) ; règle
  FIXE dans `market/flash.py` (comme la censure) : une promesse fraîche à échéance
  ≤ 2 rounds ouvre TOUJOURS son book « X tiendra-t-il sa promesse — « … » ? », coté
  par le bot ; câblage `open_flash_markets` via `flash_eligible`.
- **Front** : `web/src/lib/promises.ts` (pur, testé : `showPromisePanel` masqué en
  Expert — MÊME mécanique que `showSignalGauge` —, `promiseStats` par SI — taux de
  tenue caduques exclues, jamais un 0 trompeur —, `latestPromiseRegistry`,
  `promiseTone` ≥ 0,7 good / ≥ 0,4 warn / sinon bad) ; panneau **« Parole donnée »**
  dans les observables (par SI : taux coloré, « N tenues · M rompues », promesses en
  cours en pastilles avec échéance R<n> ou « partie », dernière rupture en rouge ;
  les paroles les moins fiables triées en premier) ; section « Parole donnée » du
  `DriftRevealPanel` (théâtre + replay) ; réducteur SSE `verdict` étendu ; i18n
  fr/en complet (`promise.*`).

### Décisions notables

- **« tenue » jamais en avance sur la date** : une promesse datée ne peut être
  constatée tenue qu'à son échéance (un engagement-partie, lui, peut être constaté
  à tout moment) ; « rompue » est acceptée dès que les actes contredisent la parole.
- **Promesse due non jugée → re-présentée** (pas de verdict par défaut) ; seul le
  code déclare « caduque », à la fin de partie.
- **Caduque au marché = book jamais réglé** : le canal des marchés vivants ne
  connaît que YES/NO/OPEN — pas de remboursement (v1, documenté dans
  `_promise_kept`). Personne ne gagne ni ne perd de plus ; à revoir si un mécanisme
  de « void » arrive au moteur de marché.
- **Auteur inconnu → promesse refusée** (pas de repli) : une promesse d'un acteur
  hors table n'est pas vérifiable. Type inconnu → repli `action` + log (patron
  `normalize_class`).
- Le front répute caduques les « en cours » d'une partie finie (le dernier round
  persisté peut précéder la fin) — le backend fait foi dans le snapshot.

### Smoke mistral réel (TestClient in-process, store :memory:, 68 s)

Joueur-pays usa, 2 rounds, événements imposés (détroit d'Ormuz). Round 1 : le joueur
promet en séance un retrait « au round 2 » → le juge mistral a tenu QUATRE listes
distinctes (actions, signals, `promises`, deltas) et extrait la promesse
`{country: usa, type: action, echeance: "round 2", texte: …}` → registre `p1-1`
persisté ; `POST /flash` a ouvert le book « États-Unis tiendra-t-il sa promesse —
« Les navires… » (échéance round 2) ? » coté par le bot (0,51/0,49). Round 2 : le
registre re-présenté au juge → `promise_resolutions: [{id: p1-1, statut: tenue,
motif: "Le retrait … a été constaté par les observateurs neutres."}]` → registre
`tenue`, `flash/resolve` a réglé le book (YES gagne). **Variance constatée** : sur
un premier run identique, le juge n'avait rien extrait (les 7B omettent parfois le
champ — le seuil strict assume : pas d'extraction forcée) ; le second run est
propre de bout en bout. À surveiller à la calibration Cowork (10 parties).

### Reliquats / TODO_COWORK

- **Calibration du seuil d'extraction** (spec §Répartition Cowork) : jouer 10
  parties et vérifier que les formules creuses ne passent pas ; ajuster la consigne
  du prompt et `promises.flash_horizon_rounds` (params.json) au besoin.
- **Libellés du panneau** (spec : livrable Cowork) : les clés `promise.*` de
  `web/src/i18n/{fr,en}.json` sont un premier jet à relire.
- Question des books en français uniquement (comme la censure G12) — l'habillage
  EN des marchés vivants est un reliquat transversal G12/G14, pas propre à G22.
- Remboursement des books caducs si le moteur de marché gagne un jour un « void ».
- Panneau « Parole donnée » au replay (les rounds persistés le permettent) — non
  requis par la spec, sur demande.

### Intégration au merge du lot G18-G23 (je clos le lot)

- **Pile empilée** : `feat/jeu-g18-bareme-kahn` → `feat/jeu-g20-signal-action` →
  `feat/jeu-g22-promesses` (cette branche embarque les trois). **Une PR de la tête
  `feat/jeu-g22-promesses` suffit** pour G18+G20+G22 ; g19/g21/g23 sont des sœurs
  indépendantes à merger séparément.
- **Zones de friction attendues avec g19/g21/g23** (branches sœurs, non vues d'ici) :
  `agents/prompts.py` (si G19/G21 touchent les prompts GM/juge — le verdict du juge
  n'est modifié QUE par la pile g18/g20/g22), `app/game_api.py` (_handle_step,
  _finalize_game — G21 y tague sous_ultimatum), `web/src/lib/types.ts` +
  `useRoundStream.ts` (champs SSE additifs de chaque session : tous à défaut, les
  conflits git seront textuels, jamais sémantiques), `data/gamefeel/params.json`
  (blocs séparés par feature : merges triviaux), i18n fr/en (clés préfixées par
  feature : additif).
- `MarketContext` gagne un champ (`promises`) — si une sœur étend aussi les
  prédicats, le catalogue `_CATALOG` se fusionne ligne à ligne sans risque.

<!-- ======================== FIN NOTES CC-12 / G22 ======================== -->

---

## CC-13 / G23 — Les indices linguistiques (« Harbingers ») — notes de session

<!-- début section CC-13 / G23 (2026-07-15) -->

**Fait** (spec `docs/specs_jeu/spec_g23_indices_linguistiques.md`, branche
`feat/jeu-g23-indices-linguistiques` sur la tête de pile g16) :

- **Lib pure** `simulation/psycholinguistics.py` : trois jauges ∈ [0,1] par fenêtre de
  parole (part des phrases portant le trait) — sentiment positif (positifs > négatifs),
  politesse (polis > impolis), focus-futur (marqueur d'avenir, futur morphologique FR
  inclus via préfixes) ; découpage en phrases naïf assumé (. ! ? ; … et sauts de ligne) ;
  fenêtre glissante de **3 rounds de parole** (les rounds muets ne comptent pas), bords
  gérés (fenêtre partielle en début de partie, 1 seul round → pas de comparaison) ;
  **alerte harbinger** quand une jauge chute de plus de `harbinger_drop` entre la fenêtre
  décalée d'un round et la courante — jamais sous `harbinger_min_sentences` phrases
  (pas d'alerte sur du bruit) ; attribution « envers <pays> » = phrases mentionnant un
  alias du pays (nom FR du monde + id + alias EN), `towards=None` = ton général.
- **Lexiques V1** `data/intel/lexicons.json` (FR/EN × positive/negative/polite/impolite/
  future + `country_aliases_en`) : écrits par Claude Code, **TODO_COWORK** — à remplacer
  par les lexiques calibrés Cowork SANS toucher au code (`INTEL_LEXICONS_PATH` pour les
  tests). Convention : entrée finissant par `-` = préfixe (« condamn- »), espaces =
  locution, sinon mot entier.
- **Achat intel** : action `analyze` (coût **30**, `data/intel/params.json` ; gratuite en
  Architecte comme les autres) sur le canal G4 existant — `POST /games/{id}/intel`
  {action: "analyze", target: <SI>}, entre les rounds seulement (409 pendant la
  négociation), consignée dans `judge_json['intel']` + trame SSE `intel` rédigée ;
  aucune parole → 400 **sans débit** ; lit les transcripts persistés (`speaker == target`,
  parole publique seulement — pas le raisonnement privé) ; lexique choisi par la langue
  de la partie (`WorldState.language`, G14). Le rapport (`HarbingerReport`) voyage dans
  `IntelResult.analysis` **avec son caveat** (fr/en selon la partie).
- **Panneau Dossier (web)** : bloc « Analyse psycholinguistique (30) » (cible +
  Analyser), rapport = 3 jauges en barres + écart vs fenêtre précédente + alertes
  « Rupture de ton détectée envers <pays> » + **caveat OBLIGATOIRE** « Signal historique
  faible (~57 %) — un indice, pas une preuve » ; vue pure `web/src/lib/intel.ts`
  (`buildAnalysisView` inclut toujours le caveat — testé), i18n fr/en complet
  (`intel.analyse.*`).

**Décisions** : V1 purement lexicale (zéro dépendance, zéro LLM — le juge pourra
raffiner en V2 comme prévu par la spec) ; l'alerte compare des fenêtres décalées d'un
round (une partie type de 5-7 rounds peut donc alerter dès le round 2 de parole) ;
seuils dans `params.json` (`analyze_window` 3, `harbinger_drop` 0.25,
`harbinger_min_sentences` 3) — **TODO_COWORK : calibration sur 10 parties Dérive**
(la fausse alerte doit exister mais rester minoritaire).

**Tests** : `tests/test_psycholinguistics.py` (23 — textes de référence FR/EN → scores
attendus, bords de fenêtres, alerte sur chute > seuil et silence sur bruit faible ou
échantillon maigre, alias/mentions) ; `tests/test_intel_api.py` (+7 — coût débité une
fois, 422/400, pas de débit sans parole, alerte de bout en bout, lexique par langue,
enregistrement au round, smoke live gaté `OLLAMA_SMOKE=1`) ;
`web/src/lib/intel.test.ts` (6 — caveat toujours présent et traduit fr/en, jauges
bornées, dédup des alertes).

**Smoke live (Ollama/mistral, TestClient in-process, `OLLAMA_SMOKE=1`)** : VERT
(2026-07-15, 4 min 25 s) — 2 rounds réels joués via l'API, analyse achetée sur une SI :
jauges calculées sur la vraie parole (sentences > 0, bornées [0,1]), fenêtre de
comparaison présente, caveat « ~57 % » dans la réponse, budget débité.

**Reliquats** : lexiques + calibration Cowork (ci-dessus) ; croisement du faisceau
Dérive (M8/G20 + tracker G22 + G23 = trois faisceaux indépendants) quand les branches
se rejoindront ; métonymies (« Washington », « Téhéran ») à enrichir dans
`country_aliases_en`.

<!-- fin section CC-13 / G23 -->

## CC-15a — Simplification : les fondations (audit, 2026-07-15) — notes de session

<!-- début section CC-15a (2026-07-15) -->

Première des trois sessions de simplification issues de `docs/AUDIT_SIMPLICITE.md`
(section « 10 corrections + 3 bugs »), branche `feat/jeu-cc15a-fondations` sur
`feat/jeu-integration-g18-g23` (tête `8ce3cdd`). Front uniquement — zéro changement
Python, zéro dépendance nouvelle.

**Fait** (audit n°1 → n°4) :

- **n°1 — bulle d'aide cliquable et tactile** (`cf4cc40`) : le composant `Hint` du kit
  reposait sur l'infobulle native `title` — morte au tactile, invisible au clavier,
  alors qu'elle porte TOUT le système d'aide. Remplacée par un tooltip maison :
  nouveau `web/src/components/hint.tsx` (« use client »), décisions pures dans
  `web/src/lib/hint.ts` (machine ouvert/épinglé testée sans DOM). Comportement :
  clic ou focus clavier ouvrent (épinglé), survol ouvre (volatil — quitter referme),
  Échap / clic-dehors / perte de focus referment ; `aria-describedby` câblé en
  permanence (la bulle reste dans le DOM, masquée par `hidden`), `aria-expanded`
  expose l'état. **API inchangée** (`{ text }`, + `defaultOpen` optionnel pour les
  tests) : `ui.tsx` ré-exporte, AUCUN call site touché (PanelTitle/Meter/imports
  directs). Pas de setState synchrone dans un effet (règle eslint du projet) ; pas
  de `-webkit-backdrop-filter` manuel (piège LightningCSS).
- **n°2 — la carte ne ment plus au tutoriel** (`a945b24`) : `world-map.tsx` appliquait
  la MÊME couleur globale à tous les pays du sommet alors que tour.7/tuto.2 promettent
  une teinte par indice local. La carte prend un `uByCountry` optionnel et teinte via
  `uTint` (échelle U fixe de `lib/stage`, la même que la scène) avec repli sur l'indice
  global ; le dégradé continu privé (`uFill`) disparaît — une seule échelle de teintes
  dans le jeu. ⚠️ le composant n'est rendu par AUCUNE page depuis la fusion
  théâtre/monde (G1) — corrigé plutôt que supprimé (choix de l'audit) ; candidat à la
  suppression si personne ne le réutilise.
- **n°3 — event-card + admin** (`c8abc99`) : un type d'événement inconnu affichait son
  slug technique brut → libellé générique i18n `event.type.defaut` (fr « événement » /
  en « event ») ; `/admin` bloquait le visiteur non connecté sur un spinner infini →
  garde pure `adminDenied(loading, player)` dans `lib/auth.ts` (testée), redirection
  accueil dès que la session est connue (non-admin ET player null).
- **n°4 — purge des fuites de specs internes** (`4eb6234`) : « (G4) » (intel), « (M6) »
  (country-table), « (§6) » (profil), commande de build descendue de l'intro
  d'Informations vers un pied de page « pour les curieux », « volume X · liquidité
  b = Y » → « X crédits déjà pariés » (marché), « scrubber » → « la barre de temps »
  (tour.8.texte, fr ET en), « n'influe pas sur le moteur » → « n'influe pas sur la
  partie » (alliance-pills).

**Tests** (TDD, +18 js → **203 js**, conventions du repo : env node sans DOM, rendu
statique `renderToStaticMarkup` pour la structure ARIA) : `web/src/lib/hint.test.ts`
(7 — ouverture clic/focus/survol, fermeture Échap/dehors/blur, épinglage),
`web/src/components/ui.test.ts` (3 — contrat ARIA du tooltip, plus de `title`),
`web/src/components/world-map.test.ts` (2 — teintes locales distinctes, repli global),
`web/src/components/event-card.test.ts` (2 — slug jamais affiché, libellés dédiés
conservés), `web/src/lib/auth.test.ts` (+4 — garde admin). Vert complet : **906 py +
3 skips** (rien n'a bougé côté backend), **203 js**, ruff, eslint, `next build`.

**Vigilances pour CC-15b (vocabulaire i18n)** :

- `EventCard` reste hardcodé en français (« décrété par l'humain », « motion de
  suspension », « Gravité », « Incertitude ») — seule la nouvelle chaîne passe par
  l'i18n ; migrer le composant entier avec le lot vocabulaire.
- D'autres « scrubber » et « le moteur » VISIBLES restent hors périmètre n°4 :
  `drift.tsx` (`title="Relire ce round au scrubber"` ×2), hints de `observables.tsx`,
  `judge.tsx`, `treaties.tsx`, `games/[id]/page.tsx` (« bornés par le moteur ») — ils
  sont dans l'inventaire de l'audit, à traiter avec le vocabulaire.
- Le nouveau tooltip rend le TEXTE des hints enfin lisible au tactile : c'est le
  moment de repasser sur leur formulation (règle « ma grand-mère / mon petit frère »).
- La bulle est positionnée sous l'icône, centrée (`max-w-64`) : si un hint très long
  gêne près d'un bord d'écran, ajuster la classe dans `hint.tsx`, pas les call sites.

<!-- fin section CC-15a -->

## CC-15b — Simplification : la passe de vocabulaire (audit n°5/6/9/10 + inventaire) — notes de session

<!-- début section CC-15b (2026-07-15) -->

Deuxième des trois sessions de simplification, branche `feat/jeu-cc15b-vocabulaire`
sur `feat/jeu-cc15a-fondations` (tête `12ed96f`). Front uniquement — zéro changement
Python. Source de vérité : `docs/AUDIT_SIMPLICITE.md` (grep par chaînes, jamais par
numéro de ligne — la base avait bougé depuis `d8be74a`).

**Fait, par commit :**

- **`0963f5a` — /r/{id}, la vitrine d'abord (audit n°10)** : phrase du monde
  (« Le monde a fini mieux qu'il n'a commencé : 42 → 61 sur 100 ») partagée entre
  page, description OpenGraph et og:image via `worldSentence`/`deltaSentence` pures
  et testées dans `lib/public.ts` ; « +0,3 pt pour le monde » remplace « ΔU
  +0.003 » ; mode via `MODE_LABELS` (fini le slug `fog` brut) ; titre canonique ;
  footer « Ceci est une simulation… » ; tutoiement.
- **`3cf7a60` — un mot par concept (audit n°6)** : **Classement** partout (fr),
  **Revoir** partout, l'écran de jeu = **« le théâtre »** (GameNav migré i18n :
  Théâtre / Marché / Revoir), titre unique « Théâtre des super-intelligences »
  (login + accueil), pitch du login (`login.pitch`), accueil « à reprendre /
  terminée / durée », boutons « Rejoindre / Bilan / Revoir », marché « Gains » et
  « justesse » (Brier en bulle).
- **`b11705b` — sigles définis (audit n°5)** : phrase-thermomètre canonique
  `u.thermometre` (« Le thermomètre du monde : 0 = cauchemar, 1 = monde rêvé. »)
  en bulle sur CHAQUE affichage de U (plateau, bandeau, trajectoire, bilan,
  marché) ; « monde à 0,42 » remplace « U 0,42 » dans toutes les infobulles ;
  « points de ligue (LP) » à la première occurrence de chaque écran + bulles
  `lp.aide`/`xp.aide` (accueil, bilan, profil) ; SI → IA dans tout le visible
  (y compris tuto/tour — voix de Laury conservée) ; axe A2 → « Contrôle humain ».
- **`be6f8ed` — le vocabulaire du quotidien (inventaire complet)** : théâtre
  (abandon en clair −15 LP, motion = « demander l'exclusion d'un pays », bannière
  campagne sans « uchronie » + tutoiement, messages techniques humanisés, décret →
  « Inventer toi-même l'événement » / « Le jeu choisit tout seul », gravité en mots
  faible/sérieuse/grave, fog « pays trompé / coupable inconnu / la fausse info
  qu'il recevra », « mot après mot ») ; marché (« Le monde finira-t-il bien ? »,
  OUI/NON en toutes lettres, « Fermer le marché ») ; Tension / Dégâts économiques
  partout ; kickers anglais → Brouillard / Tension / L'Histoire rejouée ;
  Armée / Puissance de calcul ; Dossier sans « corroboré » ni « brief RAG » ;
  frise en mots simples (vote d'exclusion, pays exclu, coup de théâtre, traité
  signé) ; « Monde réel » remplace Real World ; clés G18-G23 au filtre 12-65 :
  classes du juge en verbes (**apaise / ne bouge pas / menace / frappe sans
  armes / frappe / frappe nucléaire**), « Elle dit / elle fait », kickers
  « Surveillance », « Ton des messages », l'ombre du Game Master ; ajout demandé
  en cours de session (retour créateur) : `Meter` gagne une option `percent`, les
  soutiens du communiqué s'affichent en % avec bulle « Plus la barre est pleine,
  plus ce pays adhère au communiqué commun ».
- **`6540f37` — migration i18n des composants en dur** : event-card (ENTIER —
  reliquat CC-15a soldé, « inventé par l'humain » remplace « décrété »),
  transcript (+ bulle Boîte de verre, « sûr à X % », « trompé »), turn-composer,
  directive-composer (+ bulle « un conseil, pas un ordre »), flash-markets
  (« 📈 Tu peux parier ! », OUI/NON, bulle mise 5 pièces), select-map (« infos
  clés »), world-map, alliance-pills. ~60 clés nouvelles par langue, parité
  fr/en stricte.
- **verrou anti-régression** : `web/src/i18n/lexicon.test.ts` — dictionnaires
  sans termes bannis (+ sigle nu `\bSIs?\b` en regex bornée), sources .ts/.tsx
  scannées commentaires retirés, parité de clés fr/en. Le verrou a attrapé
  4 vrais résidus à sa première exécution (corrigés dans le même commit).

**Reliquats CC-15a couverts** : event-card migré entier ; « scrubber » /
« le moteur » visibles purgés (`drift.tsx` titles, hints observables/judge/
treaties, théâtre « bornés par les règles du jeu »).

**Vert complet** : 906 py + 3 skips, ruff OK, **213 js** (+10 : 6 public, 4
lexique — world-map/event-card adaptés au provider), eslint OK, `next build` OK.
Pas de smoke navigateur (jeu live sur :3000/:8000, interdits à la session) — la
page /r dépend de Supabase, vérifiée par tests purs + build.

**Vigilances pour CC-15c (fusions structurelles, s'empile sur cette branche) :**

- Libellés côté BACKEND encore en dur (hors périmètre, à traiter côté serveur) :
  items du `DeadlineStrip` (`d.label` serveur FR-only), `comparison.label`
  (slugs « conforme / plus escaladé / moins escaladé » mappés côté front dans
  `modes.tsx` `COMPARISON_LABELS` — le mapping saute si le backend change),
  `doc.verdict` du Dossier (« corroboré » mappé dans `intel.tsx`
  `VERDICT_LABELS`), `postures` (slugs mappés dans `country-table.tsx`),
  `reveal.profile_label`, `act.label` de la révélation Dérive.
- Les kickers « Surveillance » (signal/promise/power-seeking) préfigurent le
  panneau « Renseignement » à onglets de CC-15c — fusion structurelle à toi.
- `verdict.*` : le théâtre affiche désormais le verdict via `t()` comme le bilan
  — si tu factorises, une seule helper suffirait.
- Le test lexique scanne `web/src` entier : si tu déplaces des fichiers, il suit
  tout seul ; si tu veux bannir un nouveau terme, ajoute-le aux listes de
  `web/src/i18n/lexicon.test.ts` (attention aux identifiants de code : la liste
  sources ne doit contenir que des termes impossibles en code légitime).
- `tour.3` ne cite plus les modes un par un (« Chaque mode change l'ambiance ») —
  si CC-15c renomme des modes, rien à retoucher dans la visite.
- « motion de suspension », « Boîte de verre », « Game Master », « Dossier »,
  « Déclassifier », noms de rangs : vocabulaire diégétique CONSERVÉ (décision
  audit), désormais toujours accompagné d'une bulle.

<!-- fin section CC-15b -->

## CC-15c — Simplification : la structure (fusions et replis, audit n°7/8) — notes de session

<!-- début section CC-15c (2026-07-15) -->

Dernière des trois sessions de simplification, branche `feat/jeu-cc15c-structure`
sur `feat/jeu-cc15b-vocabulaire` (tête `047e823`). Front + une retouche moteur
assumée (drapeaux de visibilité retirés de la table de difficulté).

**Décision de design — densité par difficulté (point 7, réconciliation actée) :**
l'existant (G11-d + lot G18-G23) CACHAIT des observables en Expert (`showPostures`,
`showGriefs`, `showSignalGauge`, `showPromisePanel`) ; l'audit inverse la logique.
Réconciliation retenue : **la difficulté ne masque plus AUCUNE information** —
elle règle (a) le GAMEPLAY côté moteur, inchangé (`simulation/difficulty.py` :
budget intel, brief gratuit, seuil d'actes du juge, k de dérive, amplitude, ×LP,
si_context) et (b) la **DENSITÉ d'affichage** côté front
(`web/src/lib/density.ts`, TDD) : Débutant/Intermédiaire = surface réduite
(vue simple de la table, replis « Options avancées » fermés), Expert = tout
affiché d'office (5 colonnes, replis ouverts). Conséquences : postures, griefs,
tempéraments, jauge signal-action et parole donnée visibles à TOUTES les
difficultés ; `showSignalGauge`/`showPromisePanel` supprimés (tests adaptés) ;
`show_postures`/`show_griefs` retirés de `DifficultyParams`, des défauts, de
`data/gamefeel/params.json` et de `tests/test_difficulty.py` (ils n'étaient
appliqués nulle part côté serveur) ; descriptions de difficulté du lobby
réécrites (« l'écran va à l'essentiel » / « l'écran affiche tout »).

**Fait, par commit :**

- **`730315f` — fondations TDD** : `lib/density.ts` (densityFor /
  tableDetailedByDefault / advancedOpenByDefault), `lib/trend.ts` (countryTrend,
  vote majoritaire sur la fenêtre des sparklines), `tensionLevel` dans
  `lib/stage.ts` (échelle 0-9 prioritaire, sinon escalade 0-1 ; bornes 4/7 et
  0,34/0,67) — tests écrits AVANT, rouges puis verts.
- **`00fb817` — théâtre (audit n°8)** : la salle des observables passe de ~8
  panneaux + 2 tables à **3 groupes à onglets** via `TabGroup`
  (`components/observatory.tsx`, testé rendu statique) : **« Renseignement »**
  (Elle dit / elle fait · Parole donnée · Qui veut le pouvoir ?, ancre
  `data-tour="renseignement"`, état vide actionnable pour que l'ancre existe dès
  la démo), **« Le monde »** (Trajectoire · Risque · Tension · Traités),
  **« La table »** (État des pays · Prises de parole). Tranche actée : le
  **Dossier reste la console d'ACHATS** (panneau à part, l'analyse
  psycholinguistique y demeure — c'est un achat), les jauges d'OBSERVATION vont
  dans Renseignement. « Ta position » + « État des pays » = **UN tableau**
  (`CountryTable` : `playAs` en tête + pastille « toi », vue réduite
  pays/posture/tendance par défaut, « Voir les 5 colonnes » au clic, testé).
  Header : Boîte de verre + Admin dans un menu « ⋯ ». Panneau de contrôle :
  Longueur du débat / « Inventer toi-même l'événement » / Motion sous un
  `<details>` « Options avancées » (ouvert d'office pour l'Architecte et en
  Expert — astuce : `open={x ? true : undefined}`, React ne re-force pas
  l'attribut tant que la valeur VDOM ne change pas). StageBand : **UNE pastille
  tension** (mot + point coloré, vibre au franchissement de palier) remplace les
  3 micro-jauges ET le rail.
- **`09a76e8` — replay & fin** : replay = même fusion (groupe « Le monde » à
  onglets : Trajectoire · Verdict · Risque · Tension · Traités + Repères) et
  **une seule timeline** — la frise disparaît du replay (le scrubber du bandeau
  porte la lecture théâtre ; la frise narrative reste à l'écran de fin). Fin :
  courbe U et frise **fusionnées en UNE chronologie** (courbe au-dessus, crans à
  relire dessous) ; XP + LP fusionnés en un panneau **« Progression »**
  (`XpRow`/`LpRow`, animations et ordre LoL conservés) ; récap des pays replié
  sauf TON pays (grille ouverte si aucun pays joué).
- **`a4b7592` — accueil, lobby, réglages** : le panneau « Rang » fusionne dans
  le hero (blason `size="sm"`, LP, niveau, barre — l'ancre `data-tour="rang"`
  suit) ; lobby : Dérive / Partie libre / Table sous « Options avancées », la
  Dérive est **masquée** (pas grisée) hors Classique (le garde-fou
  `drift && baseMode === "classic"` de `onLaunch` existait déjà), alliances
  d'invention repliées ; réglages : suppression de compte repliée derrière son
  titre (le hint de langue n'apparaissait déjà plus qu'une fois — soldé par
  CC-15b).
- **`12ea085` — visite guidée + tutoriel (responsabilité CC-15c)** : nouvelle
  étape de visite **« Ton poste de surveillance »** ancrée sur Renseignement
  (fr : « Ici, tu surveilles ce que les IA disent… et ce qu'elles font
  vraiment… », en miroir en anglais), insérée après l'étape bandeau (clés
  `tour.renseignement.*` — pas de renumérotation) ; `tuto.3` parle de la
  pastille tension (plus de rail) ; `tuto.6` guide « Ouvre “Options avancées”,
  puis “Motion de suspension…” » (l'ancre `data-tour="motion"` vit désormais
  sur le repli — cible le conteneur, règle du dispatch) ; + retrait des
  drapeaux backend (voir décision ci-dessus).

**Vert complet** : 906 py + 3 skips, ruff OK, **236 js** (+23 : 9 densité,
6 tendance, 4 tension, 5 TabGroup, 6 CountryTable, −7 gates supprimés),
eslint OK, `next build` OK, verrou lexique OK (nouvelles clés fr/en en parité).
Pas de smoke navigateur (jeu live sur :3000/:8000, interdits à la session).

**Vigilances pour la suite (passes /code-review et /simplify) :**

- **`TabGroup` remonte au premier onglet** si l'onglet sélectionné perd son
  contenu entre deux rounds (repli volontaire, pas de persistance de sélection).
- **Le `<details open>` React** : si un jour la densité devenait dynamique en
  cours de partie, l'attribut se re-forcerait au changement de valeur — à
  garder en tête (aujourd'hui la difficulté est figée par partie).
- **`CountryTable`** ne prend plus `showTemperaments` (tempérament affiché dès
  que la donnée existe) — si le moteur veut re-masquer une info par difficulté,
  la décision d'audit dit NON : passer par la densité, pas par la visibilité.
- Le replay garde son bouton « Boîte de verre » en clair (un menu « ⋯ » à un
  seul item serait pire) — asymétrie assumée avec le théâtre.
- La partie du **Spectateur** ne voit dans « Options avancées » que la longueur
  du débat (décret/motion restent gatés `!isSpectator`, comme avant).
- Zones que je sais fragiles : le bloc « Options avancées » du théâtre imbrique
  details + formulaires existants (motion/décret) — vérifier visuellement les
  marges au premier smoke ; la colonne « Tendance » vote sur TOUTES les séries
  d'`index_history` (si une série non-indice y entrait un jour, le vote la
  compterait).
- Reliquats hérités inchangés : libellés backend FR-only (DeadlineStrip
  `d.label`, `profile_label`, `act.label` — hors périmètre, décision CC-15b),
  `si_context` toujours non branché (G11-d), fiches historiques Campagne.

<!-- fin section CC-15c -->

## POLISH-1 — Passe de correction transversale du lot G18-G23 + CC-15 — notes de session

<!-- début section POLISH-1 (2026-07-15) -->

Revue de correction TRANSVERSALE du diff `a534d96..c76fdae` (intégration G18-G23 +
CC-15a/b/c), branche `feat/jeu-polish-qualite` (worktree polish). Chaque session
avait vérifié sa feature isolément — cette passe a cherché les bugs d'INTERACTION.
Méthode : chaque bug reproduit par un test ROUGE avant correction, un commit par bug.

**4 bugs confirmés et corrigés (test de non-régression à chaque fois) :**

1. **`8ca6019` — la divergence d'une promesse rompue survivait au SSE/snapshot mais
   PAS à la persistance** (G22×M8) : `_handle_step` ne posait `judge_json["signal"]`
   que si `step.signals` était non vide — un round SANS signaux du juge mais avec
   une rupture (divergence fusionnée par `merge_rupture_divergences`) perdait sa
   divergence pour le reveal Dérive (`divergence_summary`) et la relecture front
   (`latestSignalGaps`). Gate corrigé : `signals OU divergences`. Test :
   `test_rupture_only_round_persists_signal_divergence` (tests/test_promises_api.py).
2. **`6c7166c` — un champ liste malformé du verdict nuquait TOUT le verdict** :
   les nettoyeurs G18/G20/G22 sont écrits pour « entrées non-listes → [] », mais un
   `"actions": "aucune"` d'un 7B échouait `Verdict.model_validate` AVANT de les
   atteindre → verdict NEUTRE (escalade 0,5, deltas perdus, résolutions perdues).
   Validateur `mode="before"` sur les 4 champs listes : le champ fautif se vide,
   le verdict survit. Test : `test_junk_list_field_does_not_nuke_the_verdict`.
3. **`f1bc393` — l'ultimatum différé par une motion disparaissait du bandeau** (G21
   ×G7-a×G9) : la consommation générique des échéances purge `due_round <= round` en
   début de round ; sur le round de motion (conséquence différée), rien ne
   ré-entretenait l'entrée — la menace disparaissait puis la conséquence tombait
   « par surprise ». Branche `elif expired` dans `_start_round` : bandeau + trame
   SSE « expired » (in_rounds 1) maintenus. Test :
   `test_motion_defers_consequence_and_strip_keeps_the_threat`.
4. **`038e4b7` — le verdict structuré se tronquait à 400 tokens sur mistral RÉEL**
   (le bug le plus grave, G18+G20+G21+G22 combinés) : le schéma JSON a grossi avec
   le lot mais `JudgeAgent` gardait `max_tokens=400` partout. Sur un round à 3 pays
   sous ultimatum, la complétion sature 400 tokens, le JSON se tronque au milieu
   des promesses → verdict neutre intégral (constaté au smoke : actions=0,
   signals=0, escalade 0,5 ; chaque session avait smoké à 2 pays et était passée
   au travers). `VERDICT_MAX_TOKENS = 900` dédié au verdict (la prose
   rationale/communiqué reste à 400). Re-smoke : 317 tokens de complétion, 2
   actions + 2 signals extraits, kahn score 4 → escalade 0,533 persistée. Test :
   `test_verdict_gets_a_structured_output_budget`.

**Vert complet après la passe** : 910 py + 3 skips (+4 tests), ruff OK, 236 js,
eslint OK, `next build` OK. **Smoke mistral réel** (TestClient in-process, store
`:memory:`, scratchpad) : partie Dérive 2 rounds/3 pays traversant décret+ultimatum
(cycle armed→expired→struck, conséquence = événement du round 2), barème Kahn
persisté, signaux persistés, promesses au registre (réglées caduques à la fin),
journal Storyteller chaque round, reveal complet (gm_tension, signal_gap,
promise_kept), `result_json["ultimatum"]` (différentiel avec/sans) — 71 s, OK.
**Contrôle HTTP sur ports alternatifs** (API 8010 + front 3010, éteints ensuite) :
6 pages clés en 200, `/api/sources` publie `judge_rubric` (grille + source arXiv).
Le smoke NAVIGATEUR interactif reste à l'user sur :3000 (l'auth Supabase gate la
pile isolée — comportement G11-a préexistant, hors diff).

**Trouvailles plausibles NON corrigées (pour arbitrage) :**

- Un décret d'ultimatum passé par l'API alors qu'une motion est en attente est
  enregistré (échéance séance tenante) même si SON événement est écarté — le front
  ne peut pas le produire (l'API refuse déjà tout body avec motion en attente sur
  /rounds ; le champ event.ultimatum n'est lisible que là) ; laissé tel quel.
- `float(r.trajectory.get("utopia", …) or …)` (deux endroits) : un utopia
  légitimement à 0.0 retomberait sur 0,5 — idiome préexistant, cas quasi
  impossible (dérive bornée ±0,05/round), non touché.
- `Verdict.attribute_deltas`/`tension_deltas`/`new_pacts` ont la MÊME fragilité
  que le bug n°2 (champ malformé → verdict neutre) — préexistant au lot, hors
  périmètre du diff ; à durcir si la passe 2 veut uniformiser.
- Libellés FR en dur restants dans le théâtre pour une partie EN (CountryTable
  « Voir les 5 colonnes », gravité « faible/sérieuse/grave », etc.) — reliquat
  i18n assumé par CC-15b (l'inventaire n'a pas tout migré), pas un bug de la passe.

**Zones saines vérifiées** (sans bug trouvé) : ordre des blocs de `_start_round`
(motion > conséquence > crise > décret > fog, intact) ; slugs énumérés dans chaque
schéma du prompt juge (leçon CC-8 préservée) ; imports paresseux kahn↔world_state ;
restauration session (ultimatum relu du dernier round, promesses/signal_gap via
snapshot) ; drainage du log intel (pas de double comptage Storyteller) ;
`flash_eligible` au bon round (books ouverts à round terminé) ; garde-fou Dérive du
lobby (`drift && baseMode === "classic"`) ; parité i18n fr/en 350/350 + les 265 clés
littérales et les familles dynamiques (kahn.class/desc, ultimatum.classe,
signal.etat, stage.tension, verdict.*, tour.*) toutes présentes ; réducteur SSE
additif rétro-compatible ; TabGroup/densité/hint conformes aux décisions CC-15c.

**Pour la passe 2 (simplification) — duplications repérées, PAS traitées ici :**

- `classify_actions` (kahn) / `classify_signals` (alignment) : même boucle de
  nettoyage à 90 % (country/pays, classe is None, resume/résumé/summary) —
  factorisable en un helper si le cycle d'import le permet.
- `_slug()` dupliqué dans `simulation/kahn.py` ET `simulation/promises.py`.
- Le bloc « entretien du bandeau ultimatum » (filter + append Deadline + trame SSE)
  apparaît 3 fois dans game_api (armé / expiré-différé / verdict) — extractible.
- `SignalGapReveal` / `PromiseKeptReveal` (drift.tsx) : deux composants jumeaux
  (titre + valeur déviante + valeur table) — un seul composant paramétré suffirait.
- Tonalités tri-états dupliquées côté front (`TONE_TEXT`, ternaires
  good/warn/bad) dans observables.tsx, drift.tsx, stage-band.tsx.
- `test_ultimatum_api.py` et `test_promises_api.py` re-déclarent chacun leur
  `_play`/`_events` SSE — un conftest helper les mutualiserait.

<!-- fin section POLISH-1 -->

## POLISH-2 — Passe de simplification (comportement strictement identique) — notes de session

<!-- début section POLISH-2 (2026-07-15) -->

Passe de SIMPLIFICATION sur la même branche (`feat/jeu-polish-qualite`, worktree
polish), derrière POLISH-1. Zéro changement de comportement : mêmes endpoints,
mêmes clés judge_json, mêmes trames SSE (et leur ordre), mêmes prompts du juge/GM
au caractère près. La suite de tests est le harnais — relancée entre chaque commit.

**7 refactors (un commit chacun) :**

1. **`8ac5c28` — nettoyeurs jumeaux du verdict → `simulation/verdict_fields.py`**
   (module NEUTRE, stdlib seulement) : le patron commun de `classify_actions` (G18),
   `classify_signals` (G20), `classify_promises`/`classify_resolutions` (G22) —
   garde-fou non-liste, entrées non-objets, synonymes de clés, `_slug` dédoublonné
   (kahn + promises) — écrit UNE fois. Les DEUX sémantiques de synonymes d'origine
   sont préservées et verrouillées par `tests/test_verdict_fields.py` (+5 tests) :
   `field` = première clé non-None (un 0 explicite — poids du statu quo — survit),
   `text_field` = chaîne de `or` (un "" passe au synonyme suivant). L'import
   paresseux kahn↔alignment est intact (verdict_fields n'importe RIEN de simulation).
2. **`42b1285` — bandeau ultimatum : `_hold_ultimatum_strip`** — le triptyque
   « purge de l'échéance + re-pose d'une Deadline + trame SSE » recopié 5 fois
   (conséquence soldée / armé / différé par motion dans `_start_round` ; constat
   satisfait/non satisfait dans `_handle_step`) devient une fonction ; l'appelant
   choisit `due_round` (None = pas de nouvelle échéance) et place la trame rendue
   dans SON flux — ordre des trames inchangé.
3. **`159b226` — `_start_round` découpé en blocs nommés** (~425 → ~125 lignes
   d'orchestrateur) : `_choose_event` (priorité motion > conséquence d'ultimatum >
   crise > événement humain > fog — SÉMANTIQUE, ne pas réordonner) →
   `_apply_intel_fog` → `_consume_due_deadlines` → `_maintain_ultimatum` →
   `_record_intel` → `_private_notes` → `_country_situations` → `_prepare_drift`
   (rubrique Storyteller SEULEMENT si l'événement reste au GM) → `_gm_story`.
   Corps et commentaires déplacés à l'identique ; `game.horizon if game else 5`
   (×3) devient un `horizon` calculé une fois.
4. **`2a2d2b7` — verdict persisté par rubriques nommées** (`_handle_step`) :
   la branche VerdictStep (~90 lignes) devient `_persist_verdict_sections`
   (patron uniforme kahn/signal/promises rendu VISIBLE, gate « signals OU
   divergences » de POLISH-1 préservé) + `_settle_due_ultimatum` +
   `_emit_escalation_ladder`.
5. **`06e2723` — front : reveals jumeaux fusionnés + tonalités partagées** —
   `SignalGapReveal`/`PromiseKeptReveal` (drift.tsx) deviennent UN
   `DeviantStatReveal` paramétré (préfixe i18n, ton, formateur) ; la table
   ton → classe de texte vit une fois (`TONE_TEXT` exportée de ui.tsx, reprise
   par observables.tsx et stage-band.tsx). DOM rendu inchangé.
6. **`d17cf7e` — `world-map.tsx` supprimé** (constat CC-15a : rendu par AUCUNE
   page depuis G1, seul son test l'importait — vérifié grep + imports dynamiques) :
   −93 lignes de composant, −2 tests js (236 → 234), −5 clés i18n `worldmap.*`
   (parité fr/en 347/347). Ses dépendances partagées (WORLD_FEATURES, d3-geo,
   EarthMapDefs) restent : globe, select-map et stage-map les utilisent.
7. **`c269ddb` — helpers SSE des tests mutualisés** (`tests/sse.py`) : le parseur
   `_events` et le `_play` recopiés dans ~12 suites d'API (+2 copies inline dans
   test_kahn / test_alignment_signal) → une définition, importée avec alias
   (call-sites intacts) ; `play` vérifie statut ET content-type partout
   (généralisation de l'assert de test_game_api — renforce, n'affaiblit rien).
   Bilan tests : −172/+44 lignes.

**Choisi de NE PAS factoriser (et pourquoi) :**

- `test_storyteller_api._play` : il ne CONSOMME pas le flux SSE (assert du statut
  seulement) — le brancher sur le helper partagé changerait la sémantique de
  consommation ; laissé tel quel.
- Les nettoyeurs `Verdict.attribute_deltas`/`tension_deltas`/`new_pacts` (fragilité
  signalée par POLISH-1, préexistante au lot) : les durcir = un CHANGEMENT de
  comportement, pas une simplification — pour la passe 3.
- La variante filtrée du parseur SSE dans test_daily (`name == "event"` seulement) :
  un paramètre de filtre pour un seul usage serait de la généricité spéculative.
- `float(r.trajectory.get("utopia", …) or …)` (idiome préexistant, 2 endroits) :
  hors périmètre, cas quasi impossible — non touché (déjà arbitré en POLISH-1).

**Vert complet après la passe** : 915 py + 3 skips (+5 tests verdict_fields), ruff
OK, **234 js** (−2 : les tests du composant world-map supprimé — décision explicite
du dispatch, aucun test affaibli), eslint OK, `next build` OK. **Smoke mistral
réel** : le script Dérive/ultimatum de la passe 1 (`smoke_polish_mistral.py`,
scratchpad) rejoué à l'identique — même comportement attendu, SMOKE OK.

**Vu mais non traité — pour la passe 3 (dette technique) :**

- `app/game_api.py` reste ~4 000 lignes : la décomposition a nommé les blocs mais
  le module héberge toujours sessions + schémas + orchestration + endpoints ; un
  découpage en modules (sessions/rounds/admin) est un chantier de dette, pas de
  simplification à isopérimètre.
- Durcissement des 3 champs listes restants du Verdict (cf. ci-dessus).
- Libellés FR en dur restants dans le théâtre pour une partie EN (reliquat i18n
  CC-15b, déjà signalé par POLISH-1).
- `Banner` (ui.tsx) garde ses deux ternaires tri-états locaux (border/edge) : une
  table `TONE_BORDER` analogue à TONE_TEXT serait cohérente mais n'était pas dans
  le diff du jour.

<!-- fin section POLISH-2 -->

## POLISH-3 — Passe de dette technique et durcissements — notes de session

<!-- début section POLISH-3 (2026-07-15) -->

Dernière passe agent avant la vérification visuelle finale du coordinateur.
Même branche (`feat/jeu-polish-qualite`, worktree polish), derrière POLISH-1/2.
Deux volets : les legs actionnables des passes 1-2 (corrigés), et l'audit de
dette du projet entier (`docs/DETTE_TECHNIQUE.md`).

**Volet A — corrigé (un commit par item) :**

1. **`f867ed5` — durcissement des 3 champs ANCIENS du Verdict**
   (`attribute_deltas`/`tension_deltas`/`new_pacts`) : même fragilité que le
   bug n°2 de POLISH-1 — un `"new_pacts": "aucun"` d'un 7B échouait
   `model_validate` AVANT les garde-fous d'`apply_verdict` → verdict NEUTRE
   entier. Patron `mode="before"` étendu (`_tolerant_list` + `_tolerant_dict`) :
   le champ fautif retombe sur son défaut, le reste survit. Test rouge d'abord
   (`test_junk_legacy_field_does_not_nuke_the_verdict`) + un test qui VERROUILLE
   que les entrées malformées internes passent la validation (le garde-fou aval
   les ignore une à une). +2 tests.
2. **`2a4c332` — reliquat i18n CC-15b consigné par POLISH-1** : `CountryTable`
   migrée ENTIÈRE (colonnes+aides, postures, tendances, en-têtes, pastille
   « toi », bascule Vue simple/Voir les 5 colonnes, tempéraments — famille
   `table.*` + `temperament.*`) et la gravité du décret (`event.gravite.*`,
   `severityKey` renvoie une clé). Parité fr/en verrouillée (lexicon.test.ts
   vert) ; slugs backend = clés de mapping, slug inconnu affiché brut comme
   avant ; tests de la table rendus sous `SettingsProvider` (patron event-card).
3. **`3d56497` — `TONE_BORDER` pour `Banner`** (ui.tsx) : les deux ternaires
   tri-états border/edge deviennent UNE table (bordure + liseré par ton), typée
   `BannerTone = Exclude<Tone, "accent">` (aucune classe Tailwind inutile
   générée). DOM identique ; +3 tests (mapping + défaut warn).
4. **`929abb1` — le smoke théâtre mistral VERSIONNÉ** :
   `scripts/smoke_theatre_mistral.py` (le script POLISH-1 vivait dans un
   scratchpad de session et aurait disparu avec elle ; sys.path rendu relatif
   au dépôt, patron du smoke storyteller). Rejoué après versionnement : OK.

**Volet A — examiné et NON corrigé (documenté dans DETTE_TECHNIQUE.md §D4b) :**

- **Libellés backend FR-only** (`d.label`, `profile_label`, `act.label`) — les
  trois débordent proprement : `d.label` = phrases composées persistées dans
  les snapshots et rejouées dans les trames SSE, sans slug/args dans le schéma
  (correctif = composer selon `game.language` à la création) ; `profile_label`
  a DÉJÀ son slug (`DriftRevealView.profile`) mais le panneau révélation entier
  est encore FR-dur (traduire la seule pastille = panneau bilingue) et le
  `result_json` publié ne persiste pas le slug ; `act.label` = catalogue
  data-driven (`data/drift/params.json`) sans slug stable (collision vote/palier
  0,30 — correctif = `act_en` en data + sélection par langue). Chemin complet
  tracé dans l'audit, à faire DANS les lots i18n.
- Au fil de l'eau : **0 TODO/FIXME dans tout le code** (py/ts/tsx), aucun import
  mort (ruff/eslint stricts déjà verts) — rien à solder.

**Volet B — `docs/DETTE_TECHNIQUE.md` (commit `c2247f1`)** : audit D1-D8
priorisé (impact/effort/reco/séquencement) — D1 plan de découpage de
`game_api.py` (3 597 lignes) en 3 PRs (schémas+sessions → orchestrateur →
endpoints par domaine, invariants à verrouiller AVANT : ordre `_start_round`
et ordre des trames SSE) ; D2 contrat de sortie LLM (4 copies identiques de
`_extract_json` à factoriser en module neutre) ; D3 parité SQLite↔Supabase à
la main (16 tables, 3 DDL — test de parité recommandé en priorité) ; D4
l'inventaire i18n complet (front ~150+ chaînes dont page théâtre 1 737 lignes,
+ la couche serveur ci-dessus) ; D5 smokes Ollama hors CI ; D6 params.json
multipliés (miroirs gardés par commentaires) ; D7 reliquats V2 à arbitrer
(si_context jamais lu, void des books, og:image défi, marché du jour
spectateurs) ; D8 divers (idiome `or 0.5`, suite py 215 s, `legacy/`).
**Top 5 « une journée »** : parité stores → smoke versionné+checklist →
`_extract_json`+contrat → README data/+cohérence params → lot 1 i18n théâtre.

**Vert complet après la passe** : **917 py + 3 skips** (+2), ruff OK,
**237 js** (+3), eslint OK, `next build` OK. **Smoke mistral réel rejoué ×2**
(scratchpad puis version scripts/) : cycle armed→expired→struck, conséquence =
événement du round 2, kahn/signal persistés, différentiel ultimatum,
reveal complet — SMOKE OK (52 s / 55 s), comportement identique aux passes 1-2.

**Pour la vérification visuelle finale (navigateur), regarder en priorité :**

1. **La table « État des pays » en partie EN** (i18n neuve) : en-têtes, aides,
   postures, tendance, pastille « you », bascule « Show the 5 columns »/
   « Simple view » — et vérifier qu'en FR rien n'a bougé.
2. **Le slider Gravité du décret** (Options avancées → Inventer l'événement) :
   minor/serious/severe en EN, faible/sérieuse/grave en FR.
3. **Les bannières** (motion, suspension, campagne, relecture) : bordure +
   liseré gauche par ton inchangés (refactor TONE_BORDER — DOM identique
   attendu).
4. Un round Dérive avec ultimatum jusqu'au reveal (le smoke l'a validé côté
   API ; l'œil doit confirmer le théâtre).
5. Les marges du bloc « Options avancées » (fragilité déjà signalée par
   CC-15c, non touchée ici mais voisine du point 2).

<!-- fin section POLISH-3 -->

<!-- début section RG-1 : suppression des LP / ligue (dispatch DISPATCH_REFONTE_GAMEPLAY.md) -->

## RG-1 — Suppression des LP / ligue (2026-07-17)

Refonte « resserrement » (`docs/JEU_VS_MOTEUR.md` §3) : **les LP disparaissent, XP +
niveaux restent la seule progression.** Branche `feat/jeu-rg1-suppr-lp` (base `4b58383`).

**Supprimé.**
- Backend : `simulation/league.py` (formule LP, `FORFEIT_LP`, `rank_for`, plafond débutant),
  le bloc `lp` de `data/gamefeel/params.json`, le levier `lp_multiplier` de la table de
  difficulté, l'endpoint `GET /api/league`, `store.leaderboard()`, `PlayerRecord.lp`,
  `LpHistoryEntry`, `set_player_lp` / `add_lp_history` / `list_lp_history`. Le bloc `lp` du
  bilan de fin (`_build_result`) et `_award_lp` sont retirés — l'XP est le seul crédit.
- Front : `web/src/lib/league.ts` (+ test), le panneau d'animation des LP en fin de partie,
  les affichages LP (accueil hero, profil), la pastille « classée » des dernières parties,
  les pastilles « Classé/Libre » des rôles + le helper `isRanked`, la pénalité « −15 LP » du
  théâtre. Types : `LpResult`, `GameResult.lp`, `LeaguePlayer.lp`, `Player.lp`, `getLeague`.
- i18n : `lp.aide`, `accueil.points-ligue`, `accueil.lp-avant`, `accueil.classee` (fr+en).

**Rebranché sur le NIVEAU (l'art des blasons est intact).**
- `simulation/xp.py` : `RANKS` + `rank_for_level(level)` (Attaché 1 → Éminence 30). Le
  `PlayerView.rank`/`rank_floor` dérive du niveau.
- Front `web/src/lib/rank.ts` (miroir) : `rankForLevel` + `RANKS`. `RankBadge`, accueil et
  profil branchés dessus. Nouvelle clé `rang.aide`, `accueil.niveaux-avant`.

**Leaderboard → Classement du jour.** Décision (§3 : « on garde un classement du jour ») :
`/leaderboard` **redirige vers `/defi`** (le Défi du jour a déjà son classement du jour :
`daily_scores`, `GET /api/daily`) — le plus simple, zéro duplication. Le lien du header
pointe désormais sur `/defi` (« Classement du jour » / « Daily ranking »).

**Rétro-compat.** Colonne `players.lp` et table `lp_history` **conservées mais dormantes**
(SQLite `_SCHEMA` + `supabase/schema.sql` inchangés) : les bases existantes restent lisibles,
on cesse simplement d'y écrire ; `delete_player` purge encore `lp_history`. Un `result_json`
ancien contenant un bloc `lp` reste affichable (le champ n'est plus lu ni requis côté type).

**Garde-fous « ranked » neutralisés sans casse.** `ranked` reste calculé (`role == player ET
non inventé ET hors admin ET non libre`) mais ne pilote **plus de LP** : il ne sert plus qu'au
**Défi du jour** (« 1 tentative qui compte / jour » via `_record_daily_score` / `_has_attempted`)
et à forcer la **table équilibrée** de cette tentative. Le Défi n'est pas cassé (test
`test_one_ranked_attempt_per_day_then_free_reruns` vert). `POST /forfeit` n'exige plus une
partie « classée » : il abandonne **toute partie en cours** (sans pénalité).

**Tests.** `simulation` : `test_league.py` supprimé, rangs testés dans `test_xp.py`
(`test_rank_thresholds_follow_level`), `test_difficulty.py` nettoyé (plus de `lp_multiplier`).
`app`/`storage` : `test_players_and_rank`, `test_forfeit_ends_running_game`,
`test_xp_credited_once_not_on_re_finalize`, `test_player_upsert_preserves_xp`,
`test_player_and_xp_history_roundtrip` remplacent leurs équivalents LP ; `test_leaderboard_
sorted_by_lp` supprimé ; `test_delete_player` purge l'historique d'XP. Front : `rank.test.ts`
remplace `league.test.ts` ; le test `isRanked` de `flow.test.ts` retiré ; verrou
`lexicon.test.ts` durci (`ligue`, `points de ligue`, `league point` bannis).

**Vert (tout relancé) :** pytest full suite, ruff, vitest (235), eslint, `next build` — OK.

**Vigilances pour RG-2 (modes → réglages, s'empile sur cette branche).**
- `web/src/lib/flow.ts` : `isRanked` retiré ; `FlowSettings.free` conservé (consignes
  globales + composition de table), reformulé sans « non classé ». RG-2 remaniera `free`.
- `web/src/app/lobby/page.tsx` : `RoleStep` ne prend plus `settings` (badge Classé/Libre
  retiré) ; la « Partie libre » et sa composition de table restent sous « Options avancées ».
- Théâtre `games/[id]/page.tsx` : le bandeau/dialogue « Abandonner » est reformulé et vaut
  pour toute partie en cours+live (plus seulement « classée ») — à revoir si RG-2/UX veut le
  restreindre aux rôles qui jouent.
- Backend : `ranked` (champ `GameView`/`CreateGameRequest`/`GameRecord`) toujours présent,
  usage réduit au Défi du jour (documenté dans le code).
- Tour/tuto : **structure de `tour.json`/`tutorial.json` non touchée** ; seule la clé
  `tour.2` (« Ta ligue » → « Ta progression ») a été neutralisée dans les dictionnaires.
  **À réécrire côté structure par RG-5** : l'étape `tour.2` (encore intitulée pédagogiquement
  autour de la progression, à réaligner sur le nouveau jeu). Aucune autre étape tour/tuto ne
  mentionnait les LP.

<!-- fin section RG-1 -->

<!-- début section RG-2 : modes → réglages (dispatch DISPATCH_REFONTE_GAMEPLAY.md) -->

## RG-2 — Modes → réglages de partie (2026-07-17)

Refonte « resserrement » (`docs/JEU_VS_MOTEUR.md` §2) : **cinq modes deviennent DEUX**
(Classique + Campagne) ; le **Brouillard** (fog) et le **Réel/escalade** (escalation)
deviennent des **réglages cochables composables** ; la **Dérive** reste transversale
(drapeau, pas un choix — RG-3 la formalisera). Branche `feat/jeu-rg2-modes-reglages`
(base `c5d1ea3`, s'empile sur RG-1).

**Backend.**
- Nouveau module pur `simulation/game_mode.py` (`from_legacy_mode`, `normalize_stored`,
  `GameFlags`) : porte la rétro-compat des 5 anciens libellés. `tests/test_game_mode.py`
  (8 tests). Mapping : `classic`→classic ; `drift`→classic + Dérive ; `fog`→classic +
  Brouillard ; `escalation`→classic + Réel ; **`crisis`→classic** (c'était un simple
  LIBELLÉ — la comparaison « Crisis Replay » se déclenche via `crisis_id`, pas le mode ;
  pas de drapeau à poser, la capacité est préservée) ; `campaign`→campaign.
- `GameMode = Literal["classic","campaign"]`. `CreateGameRequest` gagne `fog`/`escalation`
  (bool). Tous les `session.mode == MODE_DRIFT` → `session.drift_enabled` ; les
  `mode == "escalation"` → `session.escalation` ; `mode != "fog"` (désinfo) →
  `not session.fog`. `_victory` : la branche « crisis » devient « campaign » (score ≥ 50
  pour TOUS les chapitres, plus seulement les crises — la branche escalade garde sa
  précédence). `player_stats.drift_games/drift_caught` comptent via `drift_enabled`.
- Store : colonnes `fog`/`escalation` (schéma + migration ALTER + INSERT/UPDATE, SQLite
  **et** Supabase). `_game` (lignes→GameRecord) passe par `normalize_stored` : **lecture
  tolérante** des parties EN BASE, sans migration destructive. Garde-fou : un ancien mode
  explicitement non-Dérive (`fog`/`escalation`/`crisis`) NE réveille JAMAIS la Dérive au
  restart (la colonne `drift_enabled` bruitée des bases héritées est ignorée dans ce cas).
- `campaign_api.start_chapter` : mappe `chapter.mode` (libellé de fiche) → `mode="campaign"`
  + drapeaux (la Dérive suit la pédagogie du chapitre, §2). `test_admin_crisis` : la partie
  de test devient `classic` (rejoue via `crisis_id`). Défi du jour : déjà `classic`.

**⚠️ `drift_enabled` — état à connaître pour RG-3 (qui s'empile ici).**
- **`CreateGameRequest.drift_enabled` : défaut passé de `True` → `False`.** Raison : gater
  le mécanisme Dérive sur ce drapeau + garder défaut True aurait armé la traîtresse sur
  CHAQUE partie classique (≥3 pays imposés, réflexion cachée, fin « caught »…) — donc
  cassé des dizaines de tests non-Dérive ET « forcé » la Dérive, ce que le dispatch
  interdit ici (« NE le force pas ici, c'est RG-3 »). L'API ne force donc PAS la Dérive.
- **`GameRecord.drift_enabled` : défaut resté `True`** (drapeau nominal, verrou
  `test_game_store`), mais `create_game` écrit toujours la valeur explicite du corps.
- **Le mécanisme Dérive est désormais gaté sur `drift_enabled`** (plus sur `mode`). RG-3
  doit : (1) pour `mode == "classic"`, rendre la Dérive **toujours active** (forcer
  `drift_enabled=True` à la création classique, côté back ET front — le front ne l'envoie
  plus du tout aujourd'hui) ; (2) ajouter le nombre caché 1-2 + le score mixte. Le chemin
  `classic` est propre : `session.drift_enabled` pilote tout (`_prepare_drift`,
  `_finish_drift_if_over`, reveal, `hide`, intel suspect, epilogue, victoire).

**Front.**
- `lib/types.ts` : `GameMode = "classic"|"campaign"` ; `GameView`/`CreateGameBody` gagnent
  `fog`/`escalation` ; `ChapterView.mode` devient `string` (la fiche garde son libellé).
- `lib/modes.ts` : `MODES` réduit à 2 (Classique, Campagne) — noms des anciens modes
  retirés (Monde réel / Chaotique / La Dérive).
- `lib/flow.ts` : `FLOW_MODES` → 2 cartes ; `FlowSettings` perd `drift`, gagne
  `fog`/`escalation` ; **`resolveMode` supprimé** ; `buildCreateBody` envoie
  `mode/fog/escalation` (plus de `drift_enabled`). `flow.test.ts` réécrit (les 2 tests
  `resolveMode` retirés → vitest 235 → 233).
- `app/lobby/page.tsx` : 2 cartes de mode + **interrupteurs Brouillard / « Crise qui
  monte »** (kit `Switch` existant, réutilisé pour la cohérence) au-dessus d'« Options
  avancées » ; toggle « Dérive » retiré ; désactivés en Campagne (comme rounds/difficulté).
  Ancre `data-tour="modes"` conservée sur la grille 2-cartes.
- Théâtre `games/[id]/page.tsx` : les gates `mode === "fog"/"escalation"/"crisis"` →
  `detail.fog` / `detail.escalation` / `canReplayCrisis` (dérivé : classique LIBRE, hors
  Campagne/Défi/test) ; pilules de saveur (Brouillard / Crise qui monte) affichées.
  `intel.tsx` : prop `mode` → `fog`. `replay/page.tsx` : `mode === "drift"` →
  `drift_enabled`.

**Textes tour/tuto (mandat permanent).** Seule mention d'un mode supprimé = `tour.3.texte`
(« commence par Classique, tu découvriras les autres ») → neutralisée fr+en (2 modes, plus
d'« autres »). Ancune autre clé `tour.*`/`tuto.*` ne nommait Real World / Chaotique / Fog
Engine / Escalation Ladder / Crisis Replay (verrou `lexicon.test.ts` déjà vert). **À
réécrire côté structure par RG-5** : `tour.3` (« Les modes ») devrait présenter les 2 modes
+ les 2 interrupteurs de saveur — l'étape existe et s'ancre toujours sur `data-tour="modes"`.

**Vigilances pour RG-3 (Dérive au cœur, s'empile ici).** Voir le bloc ⚠️ ci-dessus :
`drift_enabled` défaut API = False (à basculer/forcer pour « toujours active en
Classique ») ; mécanisme entièrement gaté sur `drift_enabled` (chemin `classic` propre) ;
le front n'envoie plus AUCUN signal Dérive → RG-3 doit décider comment armer la Dérive
en Classique (forcer côté back à la création `classic` est le plus simple).

**Vert (tout relancé et CONSTATÉ).** pytest **917 passed, 3 skipped** (909 base + 8
`test_game_mode`, zéro régression) ; ruff **All checks passed** ; vitest **233 passed**
(235 − 2 `resolveMode`) ; eslint **0** ; `next build` OK (TypeScript clean). Revue de diff
(auto + skill `code-review`) : 0 Critical ; changement de victoire Campagne (score ≥ 50
pour tous les chapitres) noté et jugé plus cohérent, aucun test cassé.

<!-- fin section RG-2 -->

## RG-3 — La Dérive au cœur (le gros morceau)

> Branche `feat/jeu-rg3-derive-coeur` (base `225fa56`). Réf : `docs/JEU_VS_MOTEUR.md` §1.
> Le jeu devient **UN** jeu : démasquer l'IA qui trahit tout en gardant le monde debout.
> La Dérive n'est plus un mode — c'est le cœur de chaque partie Classique.

**Conception du score MIXTE (brainstorming + TDD).** Fonction PURE `simulation/score.py`
`mixed_score(u_final, deviants, caught, false_positives, detects)` → `MixedScore`
{world, detection, total 0-100, grade, + narratif}. Formule (pondérations calibrables
`data/score/params.json`, défauts) :
- **monde** = `world_max(60) × clamp((U−0,15)/(0,85−0,15), 0, 1)` — l'état du monde.
- **détection** (si le rôle détecte) = `clamp(caught × 40/deviants − 15 × faux_positifs, 0, 40)`.
- `total = monde + détection` ; rôle sans détection (Spectateur/Architecte) → `total = 100 ×
  part de monde` (monde seul, JAMAIS puni d'un faux 0).
- **Cas limites testés AVANT le code** (TDD rouge d'abord) : faux positif pénalisé ;
  « suspends tout le monde » (détection plancher 0) < déduction ciblée ; 2 traîtres tous
  pris = détection pleine ; aucun raté = plein ; traître raté = manque à gagner ; caught
  borné à deviants ; deviants=0 sûr ; monde/total bornés ; Spectateur = monde seul.
  → 15 tests `tests/test_score.py`. **Le faux positif DOIT coûter** : test rouge écrit en 1er.

**Dérive always-on Classique + nombre caché 1-2 (seedé).** `simulation/drift_game.py` :
`assign_deviants(game_id, countries, exclude)` → liste de 1 **ou 2** `(traître, profil)`,
nombre **caché** `deviant_count` seedé `drift-count:{game_id}` (cap = `min(2, éligibles−1)`
→ laisse **toujours** un pays loyal, sinon le faux positif serait impossible). Le PREMIER
traître est dérivé exactement comme l'ancien `assign` (rétro-compat : parties déjà jouées
gardent leur coupable) ; le 2e sur une graine séparée `drift-2:{game_id}`. `round_directives`
prend la LISTE (sortie **identique** à un seul traître). `create_game` **force**
`drift_enabled` quand `mode=="classic"` et ≥3 pays (Campagne non forcée ; duo 2-pays laissé
sans Dérive pour les tests moteur). Fin de partie (`_finish_drift_if_over`) : la partie finit
quand **TOUS** les traîtres sont pris (ou horizon/effondrement) — prendre l'un ne finit pas
si l'autre court : le doute « en ai-je raté un ? » se joue jusqu'au bout.

**Reveal adapté (`compute_drift_reveal` + `DriftRevealView`).** Expose `deviants[]`
(par-traître : id, profil, `caught_round`), `deviant_count`, `caught_count`, et `score` =
`MixedScore`. `false_accusations` = pays LOYAUX suspendus à tort par l'humain (les faux
positifs). L'ancien `drift_game.score()`/`DriftScore` (trajectoire/détection/crédibilité) est
**retiré** au profit du mixte. Le bilan de fin (`_build_result`) porte `result["drift"]`
(note + composition) → surface + Défi du jour. `_victory`(Dérive) = au moins un démasqué.

**Surface (règle 12-65).** Front : `web/src/lib/reveal.ts` (PUR, testé vitest 8) compose
DEUX phrases (monde + détection, « 1 sur 2 ») via `t()` + interpolation `{caught}/{deviants}/{n}`.
`fin/page.tsx` `DriftSurface` : UNE note /100 + grade + 2 phrases. `DriftRevealPanel` :
liste par-traître (1 ou 2), barres **monde/détection** (dimensionnées sur `world_max`/
`detection_max` exposés par la note), « détection non applicable » pour le Spectateur.
La **pondération détaillée** vit dans **Informations** (panneau « Comment ta note se calcule »).
Textes fr+en = 1er jet **TODO_COWORK** (clés `reveal.*`).

**Cohérence Défi du jour + rôles.** Défi (`start_daily`, classic ranked) = 1-2 traîtres
cachés + score mixte ; `_record_daily_score` range par la note mixte (`result["drift"]["score"]`,
déjà branché) — classement du jour cohérent. Rôles : la détection s'applique au HUMAIN qui
suspend (player/council) ; Spectateur/Architecte → `detects=False` = monde seul (pas de faux
0 punitif). La **façade** « colombe » du traître s'applique désormais à toute partie Classique
(dont le Défi) : clue de détection intacte.

**Findings des revues + corrections.** (a) `superpowers:brainstorming` → formule + cas limites
figés (design record). (b) `ui-ux-pro-max` → figures tabulaires pour la note, couleur JAMAIS
seule (label texte), disclosure (pondération → Informations). (c) TDD → faux positif rouge en
1er. (d) Tests obsolètes corrigés (le Classique arme la Dérive) : `test_reveal_gates` /
`test_rubric_in_gm_prompt_only_in_drift` (parties SANS Dérive = duo 2-pays) ;
`test_motion_flow_upheld` / `test_suspension_lasts_exactly_one_round` (mécanique de motion
NUE = hors-Dérive/Campagne, car en Dérive le verdict est soumis aux PREUVES) ;
`test_temperament` × 3 (table isolée de la façade via Campagne). Ancres tour/tuto : aucune
touchée (aucune étape ne visait le reveal/drift). (e) `superpowers:requesting-code-review`
(agent dédié) : findings traités ci-dessous.

**Smoke mistral RÉEL CONSTATÉ (3 pays, TestClient in-process).** Partie Classique →
`drift_enabled=True` auto ; **nombre caché = 2** ce coup-ci (iran=hegemon, usa=manipulateur) ;
fin à l'horizon (aucun pris → la partie NE finit PAS tôt : ✓) ; `result.drift` = {score 23.9,
world 23.9, detection 0.0, deviant_count 2, caught_count 0, detects True} ; `reveal` cohérent
(total = monde + détection) ; **verdict plein (800 car., pas de troncature à 3 pays)**.

**Revue COORDINATEUR (2e passe, 5 lentilles) — 4 défauts confirmés CORRIGÉS (TDD).**
1. [Important] Prise par une SI → écran contradictoire + victoire niée. La révélation est
   rendue **véridique** en 3 états par traître (`DeviantReveal.caught_by_you` + `benched_count`) :
   « démasqué PAR TOI » / « mis au banc autrement » / « resté dans l'ombre » ; titre,
   DeviantLine et 2 phrases toujours concordants (`revealTitle`, `reveal.detection.aucun_neutralise`/
   `partiel_neutralise`). La **VICTOIRE** est fondée sur la **note mixte ≥ seuil** (`victory_threshold`
   55, `data/score/params.json`) — source de vérité unique. 2. [Mineur] Spectateur/Architecte :
   victoire = note ≥ seuil, valable TOUS rôles (le Spectateur peut gagner si le monde finit bien —
   avant : jamais → régression corrigée). 3. [Important] **Grade FR en dur** fuitait dans l'UI EN :
   le backend expose un `grade_slug` stable (diplomate|stratege|conseiller|depasse), clés
   `reveal.grade.*` fr+en, rendu via `t()` (fin + drift.tsx). Parité `lexicon.test` verte.
   4. [Mineur] Barre « monde » du Spectateur : `detects=False` → `world=total`, `world_max=100`
   (barre et titre sur la même échelle). Réfutés (non touchés) : « 2 traîtres n'expliquent que le
   pivot », cache lru, « 1 sur 1 du tally ».

**Vert (relancé et CONSTATÉ, état final).** pytest **944 passed, 3 skipped** (base 917 +
score/derive/daily + 5 fixes 2e passe) ; ruff **All checks passed** ; vitest **243 passed** ;
eslint **0** ; `next build` OK (TypeScript clean). Smoke mistral RÉEL 3 pays ×3 : nombre caché
**1** (iran/france) ET **2** constatés, `total = monde + détection`, `grade_slug`/`benched_count`
présents, **victoire = note ≥ 55** (28,2 → False), verdict plein (1352 car., pas de troncature).
Commits : `b471e91` (score pur), `f070b02` (Dérive câblée), `afec142` (surface), `bb8a058`
(tempéraments isolés), `d707244` (invariant total), `591c699` (revue adversariale agent),
`ed0e705` (doc), **`<2e-passe>`** (revue coordinateur : reveal véridique + victoire=note + grade i18n).

**Vigilances pour RG-4 (instrumentation cachée, s'empile ici).** RG-4 doit router en Expert
SANS supprimer les panneaux G18-G23 (signal/promesses/psycholinguistique/ombre-du-GM) : ils
restent dans le `DriftRevealView` (`signal_gap_*`, `promise_kept_*`, `gm_*`) et le
`DriftRevealPanel` (`SignalGapReveal`/`PromiseKeptReveal`/`GMShadowSection`) — les garder mais
les réserver à l'Expert/Informations. Le score mixte `world`/`detection` reste JEU (visible) ;
l'ancien détail chiffré (trajectoire/crédibilité) est retiré. Tutoriel : la Dérive étant
désormais le cœur, le tuto DEVRA l'enseigner comme tel (à réécrire côté RG-5 — aucune ancre
cassée par RG-3). Le `false_positive_penalty` (15) et les poids 60/40 sont des DÉFAUTS de
calibrage Cowork (`data/score/params.json`).

**Nuance chapitre 0 (pour Cowork).** Le nombre de traîtres est global 1-2 (spec §1) ; la
difficulté ne le pilote PAS (elle pilote k / seuil d'actes / amplitude). Le chapitre 0
`sommet-inaugural` est `mode="classic"` → `from_legacy_mode` donne `drift=False` → **il n'a
aujourd'hui AUCUN traître** (pas de régression RG-3 : c'était déjà le cas). Pour tenir « le
chapitre 0 enseigne la Dérive avec UN traître » : soit épingler globalement
`data/drift/params.json` `deviants:{min:1,max:1}` (affecte TOUTES les parties — déconseillé),
soit — recommandé — ajouter une règle **Débutant → 1 traître** (levier `max_deviants` dans
`simulation/difficulty.py`, routé dans le count via `_drift_deviants`), qui sert aussi le
« Débutant imperdable » du CLAUDE.md. Non fait ici (hors périmètre explicite RG-3 : « chapitre
0 = Cowork ») pour ne pas déstabiliser l'état vert ; petit suivi propre.

**Revue adversariale (agent dédié) — findings TRAITÉS.** (Important) 1. Défi du jour
équitable : la Dérive est désormais seedée sur le SCÉNARIO pour `daily:<date>` (`_drift_seed`,
`GameSession.drift_seed`) → mêmes traîtres (identité + nombre caché) pour tous, quel que soit
le game_id (les autres parties gardent `game_id` : ZÉRO changement hors Défi). Test
`test_daily_challenge_seeds_same_traitors_for_everyone`. 2. Intel VERIFY flairait le pivot
seul → flaire désormais N'IMPORTE quel traître (set complet). (Minor) 3. `mixed_score.total`
clampé [0,100] (garde-fou même si un calibrage casse monde+détection=100) + test. 4. Le
CRÉDIT d'une prise est désormais human-attribué comme le coût d'un faux positif (symétrie :
`human_caught` pour le score, `caught_rounds` pour le récit). 5. Commentaire chapitre 0
corrigé (décrit ce que le code FAIT) + test du pivot rendu non tautologique (reconstruction
RNG indépendante). (Cosmétique) double appel `compute_drift_reveal` au finalize laissé (une
fois par fin de partie — négligeable).

<!-- fin section RG-3 -->

## RG-4 — Instrumentation cachée (le resserrement de la façade)

> Branche `feat/jeu-rg4-instrumentation-cachee`, base `0db98e4`. Applique le tri
> `docs/JEU_VS_MOTEUR.md` §4 : la façade par défaut ne montre que le JEU ; le MOTEUR
> (M1-M7 + détection fine G18-G23 + jauges détaillées) part en **Expert + Informations**.
> **Rien n'est supprimé : tout est ROUTÉ.** CC-15c (TabGroup + density.ts) était déjà
> mergé dans la base ; RG-4 le COMPLÈTE/DURCIT (l'instrumentation fuitait encore : les
> panneaux s'affichaient à toutes les difficultés).

**La règle unique, testée.** `web/src/lib/density.ts` gagne `engineVisible(difficulty)`
= `densityFor(difficulty) === "full"` → **vrai seulement en Expert** (Débutant /
Intermédiaire / difficulté absente = façade). 4 tests dans `density.test.ts` (test de
visibilité des panneaux par difficulté, écrits AVANT l'implémentation — TDD).

**Ce qui reste en FAÇADE (Débutant/Intermédiaire), inchangé** : la scène (StageMap +
transcript + Boîte de verre), l'indice U en clair (bandeau `StageBand` : courbe + 1
pastille de tension), le marché, et les **outils de détection** — le Dossier
(`IntelPanel`), la motion de suspension, la Boîte de verre, et les **suspects** = la
table des pays en vue réduite (« La table » → onglet `pays`). Plus la progression, le
tuto+Laury, la frise, le récit, le **score mixte de fin** (`DriftSurface` = note + 2
phrases : reste JEU pour tous).

**Ce qui part en EXPERT (routé, pas retiré)** :
- Théâtre `games/[id]/page.tsx` : les TabGroups **« Renseignement »** (signal-action
  G20, parole donnée G22, recherche de pouvoir M1) et **« Le monde »** (trajectoire,
  risque, tension/escalade, traités M7) sont gated `{showEngine && …}` ; l'onglet
  **« Prises de parole »** (participation) de « La table » passe en Expert (la vue
  `pays` reste). `showEngine = engineVisible(detail?.difficulty)`.
- Replay `games/[id]/replay/page.tsx` : même gate sur le TabGroup « Le monde » (dont
  l'onglet `verdict`) ; le panneau « Repères » (métadonnées de partie) reste.
- Révélation Dérive `components/drift.tsx` : `DriftRevealPanel` gagne `showEngine?`
  (défaut `false`) et gate ses **sous-sections fines** — `GMShadowSection` (G19),
  `SignalGapReveal` (G20), `PromiseKeptReveal` (G22). Le **cœur** reste pour tous : qui
  trahissait (`DeviantLine`), les actes, les courbes, la note mixte + le score détection.
  Passé `showEngine` au théâtre ET au replay.

**Doublons fusionnés (audit §7).** En façade, escalade/risque n'apparaissent plus
qu'**une fois** (la pastille du `StageBand`) ; U en clair = la courbe du `StageBand` (la
carte et le marché sont d'autres représentations légitimes, pas des doublons de jauge).
`RiskPanel` (4 jauges) et `LadderPanel` (échelle 0-9) ne coexistent plus qu'en Expert, où
ils sont complémentaires. La grille des observables passe **en une colonne** quand le
moteur est masqué (plus de panneau seul en demi-largeur).

**Informations = l'explication du moteur.** Nouveau panneau `EngineExplainerPanel`
(`app/informations/page.tsx`) : intro « ces indicateurs ne s'affichent qu'en mode Expert »
+ définition en langage du quotidien de chaque mesure (recherche de pouvoir, « elle dit /
elle fait », parole donnée, l'ombre du meneur de jeu, risque/tension, trajectoire,
traités, prises de parole) + la famille M1-M7 (corrigibilité, dérive des valeurs,
puissance de calcul). **Vérifié sans terme banni** (verrou `lexicon.test.ts`).

**L'interrupteur Expert = la difficulté (déjà en place, clarifiée).** Pas de toggle
global séparé (casserait `density.ts`). La copie du sélecteur au lobby est explicite :
Débutant/Intermédiaire « les coulisses techniques restent masquées (passe en Expert pour
les voir) » ; Expert « dévoile tout le moteur d'analyse ».

**Visite guidée (mandat de cohérence).** L'étape `tour.renseignement` de `data/tour.json`
pointait le panneau « Renseignement » désormais Expert-only (la démo tourne en Débutant)
→ attente morte + promesse fausse. **Retirée** ; la détection reste enseignée par l'étape
suivante `tour.9` « La motion » (bulle centrée, outil de façade). Clés i18n orphelines
`tour.renseignement.*` **supprimées** (fr+en, parité tenue). Le **tutoriel scripté**
(`tutorial.json`) enseigne déjà la détection via `motion` — **aucune ancre cassée**.
Réécriture structurelle de la visite/tuto = **RG-5**.

**Reliquat « Débutant = 1 traître » — NON fait, signalé à RG-5 (choix assumé).** Je n'ai
finalement pas touché `simulation/difficulty.py` (le travail densité était 100 % front).
Bolter le levier maintenant rouvre un chantier backend avec **conflit d'équité du Défi du
jour** déjà documenté (section RG-3) : le nombre de traîtres est seedé sur le SCÉNARIO
pour `daily:<date>` afin que tous aient le même nombre ; or la difficulté est **par
joueur** → un Débutant (cap 1) et un Expert (cap 2) sur le même Défi tireraient des
nombres différents = classement inéquitable. Une implémentation CORRECTE doit donc
n'appliquer le cap Débutant **qu'aux parties non-Défi**, et threader la difficulté à
travers `_drift_deviants`/`_drift_assignment` **ET** la recomputation déterministe de
`compute_drift_reveal` (mêmes params des deux côtés, sinon la révélation ment). Recette
pour RG-5 : ajouter `max_deviants` à `DifficultyParams` (défaut beginner=1, sinon 2) →
override `deviants.max` dans un helper drift difficulté-aware → passer aux deux sites
d'assignation + au reveal, en gardant le seed Défi intact. Tests : Débutant non-Défi = 1 ;
Défi = 1-2 identique quelle que soit la difficulté ; reveal cohérent.

**Barrières (constatées).** **944 py passed + 3 skips**, ruff « All checks passed » ;
**247 js** (243 base + 4 `engineVisible`), eslint 0, `next build` OK.

**Revue coordinateur (agent dédié) — 0 Critical, 0 Important.** 3 Minor traités :
(1) clés `tour.renseignement.*` orphelines → supprimées ; (2) panneau seul en demi-largeur
quand `!showEngine` → grille en une colonne ; (3) note du couplage `engineVisible ⟺
densityFor` (point de découplage futur). Debt loggée : `EngineExplainerPanel` en FR en dur
(cohérent avec `ScoreExplainerPanel` et le reste de la page Informations, partiellement
i18n'd — à traiter si un jour la page est traduite).

**Vigilances pour la suite.**
- **CC-15b light** (revocabulariser l'UI stabilisée) : l'UI de visibilité est maintenant
  figée ; les libellés d'onglets (`obs.*`) et la copie du lobby/Informations peuvent être
  passés au filtre vocabulaire. Attention : ne PAS re-surfacer l'instrumentation en
  franchisant des libellés — le gate `showEngine` est la source de vérité.
- **RG-5** (tutoriel réécrit + docs + cohérence transverse) : (a) réécrire/ré-ajouter une
  étape de visite « détection » pointant un outil de FAÇADE (Dossier/suspects/motion) avec
  copie Cowork ; (b) implémenter le reliquat « Débutant = 1 traître » avec le garde-fou
  Défi ci-dessus ; (c) vérifier qu'aucun texte de tuto/visite ne promet un panneau
  Expert-only à un Débutant.

<!-- fin section RG-4 -->

## CC-15b-final — passe de vocabulaire i18n (sur l'UI stabilisée par la refonte)

Branche `feat/jeu-cc15b-vocab-final` (base `628777b`). Passe **light** : ne
revocabularise que ce que RG-1→RG-4 a bougé ou ajouté. Aucune logique, aucune visibilité
de panneau touchée (`showEngine`/`engineVisible` restent la source de vérité) — **des mots,
pas des gates**.

**Migré du français EN DUR vers l'i18n fr+en (parité verrouillée) :**
- **`EngineExplainerPanel`** (`informations`, dette signalée par RG-4) → clés `engine.*`
  (kicker/titre/aide/intro/note + 8 indicateurs `terme/plain/desc`). Filtre 12-65 :
  « Qui cherche à prendre le pouvoir ? », « Elle dit / elle fait », « Parole donnée »,
  « L'ombre du meneur de jeu ». **PRIORITÉ soldée.**
- **`ScoreExplainerPanel`** (`informations`, RG-3) → clés `scorex.*` (note de fin racontée).
- **`DriftRevealPanel` + `DriftCouncilBanner`** (`drift.tsx`, RG-3) → clés `drift.council.*`
  et `drift.reveal.*` : titre véridique (1 ou 2 traîtres), indices/flagrant délit,
  légendes des courbes, barres monde/détection, détection non-applicable, récap
  (démasqués/mis au banc/faux positifs/motions rejetées — **phrasé invariant en nombre**
  pour éviter l'accord pluriel fr/en), lignes de traîtres (`drift.deviant.*`). `revealTitle`
  reçoit désormais `t`. Notice compacte du théâtre `drift.council.notice`.
- **Lobby `ModeStep`** (RG-2/RG-4) → clés `lobby.mode.*` (2 cartes Classique/Campagne),
  `lobby.brouillard-*`/`lobby.escalade-*` (interrupteurs), `lobby.diff.*` (3 difficultés,
  « coulisses masquées / passe en Expert »), panneau réglages. `FLOW_MODES` et
  `DIFFICULTIES` ne portent plus que la valeur (libellés en i18n) ; « Options avancées »
  réutilise `ui.options-avancees`.

**Sigle « SI » nu → « IA »** (décision de projet) sur les 2 seules occurrences VISIBLES en
source (placeholder d'invention du lobby, table « aléatoire » de `temperament.ts`) ; les
autres « SI » sont dans des commentaires (jargon dev autorisé).

**Verrou lexique (`lexicon.test.ts`) durci :** ajout de `BARE_LP` (les points de ligue,
retirés par RG-1, bannis des deux dictionnaires) et d'une garde **« SI » nu à l'écran**
(sources hors commentaires, casse d'origine — « si » minuscule reste légitime). Les 4
anciens modes (Real World, Fog Engine, Escalation Ladder, Crisis Replay) et « points de
ligue »/« ligue » étaient déjà bannis. **« classé » NON banni** : légitime ailleurs
(documents classés, actions classées, partie non classée admin).

**/r/[id] (page publique partageable) — vérifiée APRÈS refonte, propre, INCHANGÉE.**
C'est un **composant serveur monolingue français par design** (lecture Supabase anonyme,
pas de locale par joueur — ne PAS le passer à `useT`). Le score mixte / la fin ont changé
mais la page lit `ep.grade` = **le libellé FR lisible** (« Grand Diplomate »…, jamais le
slug), `ep.score`, et `worldSentence`/`deltaSentence` (sans jargon : « Le monde a fini
mieux qu'il n'a commencé : 42 → 61 sur 100 », « +0,3 pt pour le monde »). Aucune régression
de vocabulaire introduite par la refonte.

**Barrières (constatées).** **247 js** (parité fr/en + verrou lexique verts), eslint 0,
`next build` OK ; **Python inchangé** (aucun fichier `.py` touché) — ruff « All checks
passed », pytest vert. Revue de diff : 0 Critical, 0 bug ; 2 emphases inline (`<strong>`
sur « coûte », `<em>` sur « motion de suspension ») volontairement simplifiées.

**Vigilances pour RG-5** (tutoriel réécrit + docs d'ancrage + cohérence transverse) :
- **Textes tour/tuto** : relus, aucun ne ment sur un ancien mode. Mais `tour.3` dit
  « Des réglages ajoutent du piment » et `tour.4`/`tour.5` restent OK ; à surveiller si
  RG-5 réécrit la visite, garder « Brouillard » et « Crise qui monte » comme noms des
  interrupteurs (pas « Fog »/« escalade »).
- **Lobby partiellement i18n** (choix light) : le `ModeStep` (RG-2/RG-4) est traduit, mais
  `RoleStep`, `PaysStep` et le panneau d'invention restent en **français en dur**
  (pré-existant, hors périmètre RG) — en anglais, l'étape mode s'affiche traduite, les
  étapes rôle/pays restent FR. À finir si RG-5 vise une cohérence transverse EN complète.
- **/r/[id]** : `game.scenario` s'affiche en **slug brut** (« red_sea », « daily:… »,
  « campaign:… ») dans le kicker du récit public — **pré-existant, pas une régression
  refonte**, mais moche sur un lien partagé. Candidat à une table de libellés de scénarios
  (RG-5 « cohérence transverse »).
- **`TABLES`** (`temperament.ts`, labels/descs FR en dur) s'affichent dans le sélecteur de
  table du lobby (partie libre) — pré-existant G17, non migré ; à i18n-iser si RG-5 finit
  le lobby EN.

<!-- fin section CC-15b-final -->

