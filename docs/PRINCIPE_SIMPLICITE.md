# Principe transversal — « Jouable de 12 à 65 ans »

> Règle de design non négociable (Laury, 2026-07-15). S'applique à TOUTE spec et TOUTE
> session Claude Code, au même titre que « simplicité d'abord » du CLAUDE.md. Les specs
> G16-G24 sont à lire À TRAVERS ce filtre.

## Le principe

Le jeu doit être jouable et agréable pour un joueur de 12 ans comme de 65 ans, sans
manuel. La sophistication vit dans le MOTEUR (invisible) ; la SURFACE (ce que le joueur
voit et manipule) reste minimale.

## Les trois règles

### 1. Moteur complexe autorisé, surface complexe interdite

Toute mécanique se juge sur ce qu'elle AFFICHE, pas sur ce qu'elle calcule. Un AMM
liquidity-sensitive est invisible (le joueur voit « Cote : 62 % » et un bouton
Parier) : autorisé. Trois nouvelles jauges par pays dans le théâtre : c'est de la
surface — soumis au budget ci-dessous.

Test d'acceptation de toute feature : **elle doit s'expliquer en UNE phrase qu'un
enfant de 12 ans comprend.**
- Parier : « Tu paries des points sur la fin du monde ou son salut. »
- Motion : « Tu accuses une IA, tout le monde vote. »
- Score de prophète : « Plus tu devines juste et tôt, plus tu gagnes. »
- Si la phrase n'existe pas, la feature n'est pas prête.

### 2. Le budget de surface

- **Écran théâtre par défaut (Débutant comme Intermédiaire)** : la carte, le
  transcript, le bouton Jouer, le bandeau du bas — et AU PLUS 3 panneaux d'observables
  visibles. Tout le reste vit derrière « Voir plus » (disclosure) ou en mode Expert.
- **Chaque nouveau panneau doit en cacher un autre** (ou se fondre dans un existant).
  On n'ajoute jamais net : signal-action (G20), promesses (G22), analyse linguistique
  (G23) se présentent comme UN SEUL panneau « Renseignement » à onglets, pas trois
  boîtes de plus.
- **Un chiffre par concept.** Le joueur voit un « score de prophète » (0-100), pas
  Baseline + Peer + coverage ; il voit « fiable / douteux / trompeur » sur une SI, pas
  une divergence signée. Les détails restent accessibles (bulle « ? », page
  Informations) pour les 24 ans curieux — jamais imposés.

### 3. Le vocabulaire du quotidien

Chaque terme visible passe le filtre « ma grand-mère / mon petit frère » : on écrit
« Le monde va mieux / va mal » avant « indice U », « Elle ment ? » avant « divergence
signal-action », « Parole tenue » avant « taux de trahison ». Le jargon précis vit
dans les bulles d'aide et l'onglet Informations — jamais en premier mot. La mascotte
et la visite guidée (G13) sont le canal officiel d'explication : si une feature a
besoin d'être expliquée, c'est une bulle de Petit Kairos, pas un paragraphe d'UI.

## Application immédiate aux specs en attente

- **G18 (barème du juge)** : moteur pur — rien ne change pour le joueur, le
  VerdictPanel gagne au plus un mot par action (« apaise » / « menace » / « frappe »).
- **G19 (GM-Storyteller)** : invisible par définition. RAS.
- **G20 + G22 + G23** : leurs affichages FUSIONNENT dans le panneau « Renseignement »
  existant (onglets), avec des libellés du quotidien (« Elle dit / elle fait »,
  « Parole donnée », « Ton des messages ») et un seul niveau de détail par défaut.
  Pas trois panneaux nouveaux.
- **G21 (deadline)** : déjà simple (« plus que 2 rounds pour répondre ») — le volet
  « différentiel d'éval » du bilan passe derrière une disclosure.
- **G24 (marché V2)** : brique 1 (liquidité) invisible ; brique 2 réduite EN SURFACE à
  un seul « score de prophète » 0-100 + rang de table (détails en bulle) ; brique 3
  (cote cachée en début de partie) est une SIMPLIFICATION pour le joueur (« parie ton
  intuition, la cote se révèle au round 3 »).
- **G16/G17** : déjà conformes (un bouton « Sommet du jour », des pastilles 🕊/🦅).

## Garde-fou de process

Toute session Claude Code sur une feature à surface UI cite ce document et applique le
budget. Tout playtest inclut la question : « un joueur de 12 ans comprend-il l'écran
sans aide ? » — si non, on retire de la surface avant d'ajouter quoi que ce soit.
