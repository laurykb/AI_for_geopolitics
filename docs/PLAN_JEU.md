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
