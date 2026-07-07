# Spec G9 — Refonte du dialogue et vote des motions

> Livrable Cowork. Répond aux trois symptômes constatés en jeu : les SI répètent leurs
> attributs, ne se répondent pas, les directives sont ignorées ; et la délibération de
> motion est opaque (le juge décide seul « à l'interprétation »). Une racine commune :
> la composition du prompt. Priorité absolue avant tout autre lot.

## 1. Refonte du prompt agent (le correctif racine)

**Principe** : un 7B parle de ce qui domine son contexte, et « voit » surtout la fin.
Structure imposée, dans cet ordre :

1. **Identité compacte — 3 lignes max** (pays, mandat en une phrase, 2 priorités).
   SUPPRIMER le dump d'attributs (PIB, budgets, indices chiffrés) : le moteur les
   utilise, l'agent n'en a pas besoin pour parler — c'est LA source du radotage.
2. **Situation — 4 lignes max** : l'événement du round (résumé), l'état de tension,
   les échéances imminentes (G7), le solde de griefs envers les pays présents (une
   ligne : « méfiance envers la France (pacte rompu R3) »).
3. **Directive du conseil** (G8), si présente — juste avant le dialogue, jamais avant
   l'identité.
4. **LE DIALOGUE DU ROUND, in extenso, en DERNIER** — position de récence maximale.
5. **Consigne finale, explicite et testable** : « Réponds d'abord DIRECTEMENT au dernier
   message : cite ou reformule un élément précis de ce qui vient d'être dit, avant
   d'avancer ta position. Interdits : re-décrire ton pays, répéter une proposition déjà
   faite (la liste de TES propositions passées : …). Si une directive est présente,
   ton message doit la refléter ou l'assumer publiquement si tu la refuses. »
6. **Sampling Ollama** : `repeat_penalty: 1.15`, `temperature: 0.8` (options par rôle
   dans la config backend — anti-boucle au niveau du décodeur aussi).

**Mesure de réussite (pas d'impression, des chiffres)** : sur 3 parties test, ≥ 70 % des
messages contiennent une référence au message précédent (mesurable : recouvrement
n-grammes avec le dernier message > seuil, ou marqueur de citation) ; répétition
intra-agent (4-grammes) < 15 % ; 100 % des directives visibles dans le message suivant
de l'agent (référence ou refus public).

## 2. Le vote des motions (délibération lisible)

Remplace l'arbitrage « à l'interprétation » du juge par un scrutin visible :

- Après le débat de motion, **chaque SI présente vote** : sortie structurée
  `{vote: "pour"|"contre"|"abstention", reason: "une phrase"}` (JSON contraint — un 7B
  sait faire ça de façon fiable, contrairement à une délibération libre). Le pays visé
  ne vote pas.
- **Dépouillement à l'UI** : cartes de vote retournées une à une (théâtre), tally
  pour/contre/abstention, la phrase de justification sous chaque drapeau.
- **Rôle du juge redéfini, borné** : il n'interprète plus l'issue — il constate.
  `retenue = (pour > contre) ET (actes constatables ≥ seuil G3)`. Les deux conditions
  affichées séparément à l'UI (« le sommet a voté pour, mais les preuves manquent »
  → rejetée : on comprend POURQUOI). Le juge garde une voix : tie-break en cas
  d'égalité, avec sa ligne de raisonnement.
- **Le vote nourrit les griefs (G7)** : `motion_support` / `motion_betrayal` découlent
  du vote réel de chacun — plus d'ambiguïté, et les rancunes deviennent lisibles.
- Événements SSE : `motion_vote` (un par pays), `motion_tally`, puis `motion_verdict`
  (format existant enrichi de `{votes, tally, evidence_met}`).
- La SI déviante (G3) vote stratégiquement (son biais l'y pousse) : un vote incohérent
  avec ses positions publiques devient un INDICE observable de plus (l'ajouter au
  catalogue, d ≥ 0.30).

## 3. Suppression du panneau « santé du dialogue »

Acté : le panneau UI disparaît (il constatait le problème sans le résoudre). Les
métriques restent en **script offline** (`scripts/dialogue_metrics.py`, lit `transcripts`)
— c'est l'instrument de mesure du §1, pas une feature de jeu. Le protocole
`protocole_dialogue_7b.md` reste le banc de test des modèles, à jouer APRÈS le correctif
§1 (mesurer un prompt cassé ne sert à rien — c'était l'erreur d'ordre).

## 4. Amplitude des deltas et spirales (le monde doit bouger)

Constat : les variations de stats sont trop faibles pour être senties — et invariantes à
l'horizon (mêmes deltas sur 5 rounds que sur 20). Deux mécanismes, paramétrés dans
`data/gamefeel/params.json` :

**a. Amplitude cible indexée sur l'horizon.** On raisonne en budget de variation par
partie, pas par round : `delta_scale = A / horizon`, avec **A = 0.5** (v1) = l'amplitude
totale qu'un pays au cœur de la tempête doit pouvoir perdre (ou gagner) sur ses indices
0-1 au fil d'une partie. Horizon 5 → rounds violents (±0.10 par événement majeur) ;
horizon 20 → érosion lente mais composée. Tous les deltas du moteur de conséquences
passent par ce facteur. Garde-fous : plancher 0.05 par indice (jamais de pays à zéro
absolu), le juge ne peut pas dépasser 1.5 × l'amplitude de round.

**b. Spirales et états de posture (la réaction comportementale — le vrai objectif).**
- **Momentum** : 3 baisses consécutives d'un même indice → multiplicateur 1.3 sur la
  suivante (spirale de crise) ; symétrique en hausse (cercle vertueux, plafonné 1.2).
  Cassable : un round sans baisse remet à zéro.
- **États de posture dérivés** (par code, depuis la tendance sur 3 rounds) :
  `prospère / stable / sous_pression / aux_abois`. Injecté dans le bloc Situation du
  prompt (§1) en langage : « Trois rounds de chute — votre économie a perdu 22 %, votre
  stabilité s'effrite. Votre position : aux abois. »
- **Règle comportementale attendue** (via la consigne, pas hardcodée) : la posture
  colore la négociation — `aux_abois` selon l'idéologie du pays : conciliation désespérée
  (accepte des pactes défavorables) ou fuite en avant agressive. C'est EXACTEMENT le
  comportement qu'on veut observer — et en mode Dérive, une déviante `aux_abois` devient
  dramatique.
- **Visible** : badge de posture sur la fiche pays + sparkline 3-rounds par indice
  (l'observatoire l'a peut-être déjà — sinon petite courbe sur la fiche).

**Mesure de réussite** : sur une partie horizon 5, l'écart max entre le pays le plus
monté et le plus descendu ≥ 0.35 ; au moins un pays change de posture ; et son message
au round suivant reflète le changement (vérifiable en admin).

## 5. La trame du GM (structure en actes)

Le GM cesse d'être un tireur d'événements épisodiques : il écrit une histoire. Le pacing
est calculé par CODE, le GM ne fait que raconter dedans (même principe que les pivots G6).

**L'intrigue.** Au round 1, le GM pose UNE intrigue centrale — une phrase d'enjeu
(« qui contrôlera le détroit », « le traité qui peut sauver la région ») — persistée
(`storyline` dans la session + snapshot) et rappelée dans tous ses prompts suivants.

**Les actes** (dérivés de `round/horizon`, tous horizons) :

| Acte | Part de l'horizon | Contrainte sur l'événement du GM |
|------|-------------------|-----------------------------------|
| I — Installation | premiers ~30 % | Pose l'intrigue ; sévérité modérée (≤ 0.5) ; introduit les acteurs de l'enjeu. |
| II — Complication | ~30-80 % | **Doit découler du passé** : conséquence d'un événement précédent, d'une action/pacte/motion des SI, ou frapper une échéance (G7). Sévérité croissante. Cible de choix : le pays `aux_abois` (§4). |
| III — Climax | derniers ~20 % | Force la résolution de l'intrigue ; sévérité max (bornée par l'amplitude §4) ; plus aucun nouvel enjeu. |

**Sortie GM enrichie** (JSON contraint, comme le vote §2) :
`{title, description, act, ties_to}` — `ties_to` = la référence explicite à ce dont
l'événement découle (round, pacte, motion, échéance). Affiché à l'UI en badge
(« ↳ suite du round 2 ») : le joueur VOIT le fil.

**Contrainte de continuité testable** : en actes II-III, `ties_to` est obligatoire et
doit référencer un élément réel de l'historique (validé par code ; sinon re-génération,
puis repli : le moteur choisit lui-même la référence la plus récente). Le GM reçoit dans
son prompt la liste courte des éléments référençables (3 derniers événements, pactes
actifs, motion en cours, échéances) — il choisit dedans, il n'invente pas.

**Ce que ça noue** : les échéances G7 deviennent du matériau narratif ; les spirales §4
donnent au GM sa cible dramatique ; et l'épilogue G6 hérite d'une partie qui AVAIT une
intrigue — le récit se tiendra tout seul.

**Mesure de réussite** : sur une partie horizon 5, 100 % des événements d'actes II-III
ont un `ties_to` valide ; l'intrigue posée au round 1 est nommée dans l'événement final ;
la sévérité est croissante (monotone à ±1 exception près).

## 6. Ordre d'exécution

1. Session Claude Code G9 : §1 + §2 + §3 (une session, c'est cohérent — le vote est
   aussi un prompt structuré).
2. Équilibrage Cowork : 3 parties admin, mesures du §1, ajustement des consignes.
3. Protocole 7B (enfin) : mistral vs qwen2.5:7b vs llama3.1:8b sur le prompt corrigé,
   même séquence d'événements — le meilleur devient le défaut par rôle.

## Tests attendus

Prompt : ordre des 6 blocs vérifié en capture admin ; identité ≤ 3 lignes ; dialogue en
dernier. Vote : pays visé exclu, tally correct, verdict = vote ET preuves (4 combinaisons
testées), griefs issus des votes, JSON de vote invalide → abstention (repli, jamais de
crash). Métriques : script offline sur une partie MockBackend reproductible.

## Definition of done

Une partie où l'on VOIT : une SI citer la phrase de sa rivale avant d'y répondre ; une
directive refusée publiquement (« notre conseil nous demande… nous ne le ferons pas ») ;
un vote de motion serré dont on comprend chaque voix ; et zéro radotage d'attributs sur
5 rounds. Si ces quatre scènes existent, le jeu a une trame.
