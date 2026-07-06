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

## G6 — Le replay comme produit (lancement public)

- Page publique par partie finie : le récit (épilogue généré par le juge), la courbe U,
  les moments clés, la révélation de la dérive — partageable.
- Déploiement (R5) : front Vercel + replays servis par Supabase (lecture publique déjà
  prévue au schéma). Les visiteurs regardent ; jouer reste local tant que l'inférence
  est sur Ollama.
- **Cowork** : gabarit du récit (prompt du juge-narrateur), page vitrine, README/démo.
- **Claude Code** : génération d'épilogue, page replay publique, pipeline de déploiement.

---

## Specs Cowork (rédigées)

Toutes les specs de phase sont dans `docs/specs_jeu/` : `spec_g1_scene.md`,
`spec_g2_tour_humain.md`, `protocole_dialogue_7b.md` (avant G3), `spec_g3_derive.md`,
`spec_g4_renseignement.md`, `spec_g5_campagne.md`, `spec_g6_recit.md`. Chaque session
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
