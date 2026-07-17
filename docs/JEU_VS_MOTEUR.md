# Décision « jeu vs moteur » — le resserrement gameplay

> Livrable Cowork (2026-07-15). **Décision canonique.** Fige le tri entre ce qui est
> *jeu* (visible, joué) et ce qui est *moteur* (invisible, ou réservé aux curieux).
> Supersède : la structure à 5 modes (roadmap / `lib/flow.ts`), le cadrage « Dérive =
> un mode », et le système de LP/ligue. Complète `docs/PRINCIPE_SIMPLICITE.md`.
> Implémentation : `docs/DISPATCH_REFONTE_GAMEPLAY.md`.

## Le principe du resserrement

Le jeu était une *plateforme à plusieurs modes*. Il devient **un jeu** : une boucle
centrale forte — démasquer l'IA qui trahit tout en gardant le monde debout — avec le
reste en variantes optionnelles ou en moteur invisible. On ne coupe presque rien
d'utile ; on **concentre la focale**.

## 1. Le cœur : la Dérive intégrée

La Dérive n'est plus un mode qu'on choisit : **c'est le jeu**. Chaque partie (hors
Campagne, cf. §2) porte le mécanisme du traître.

**Combien de traîtres — décision : toujours au moins un, nombre caché (1 ou 2).**
- Il y a *toujours* quelqu'un à chercher (lisibilité : le joueur sait qu'il a un travail).
- Mais il ignore *combien* (1 ou 2) : la paranoïa reste vivante — « en ai-je raté un ? ».
- Assignation seedée dès le round 0 (déjà le cas), scellée, révélée en fin de partie.

**Comment on gagne — décision : score mixte (le monde + la détection).**
La note finale mélange deux choses, chacune racontée simplement au joueur :
1. **L'état du monde** — l'indice U final (le monde a-t-il fini bien ?). Un traître non
   démasqué tire le monde vers le bas : le laisser filer se paie ici.
2. **La détection** — as-tu suspendu le(s) bon(s) traître(s), *sans accuser d'innocent* ?
   - Bonne suspension = points.
   - **Faux positif = coût** (suspendre un pays loyal pénalise). Sans ce coût, la
     stratégie optimale serait « suspends tout le monde » — le faux positif est ce qui
     rend la déduction nécessaire.
   - Traître raté (jamais démasqué) = manque à gagner (et il a plombé le monde).

**Surface joueur (règle 12-65 ans).** Le joueur ne voit JAMAIS la formule. En fin de
partie : **une note globale** + deux phrases-histoire, par exemple :
> « Le monde a fini du bon côté (68/100). Tu as démasqué 1 traître sur 2 — l'autre a agi
> dans l'ombre jusqu'au bout. »
Le détail chiffré (pondération monde/détection) vit dans Informations, pour les curieux.

**Ce qui existe déjà et sert de base** : l'assignation seedée, le `DriftRevealPanel`, la
motion de suspension, la révélation de fin. La refonte = (a) toujours actif, (b) 1-2
cachés, (c) score mixte + coût du faux positif, (d) révélation adaptée à « peut-être 2 ».

## 2. Modes → réglages

**Deux modes seulement** au lobby :
- **Classique** — le jeu de base : le sommet négocie, le monde penche, ≥1 traître se
  cache. C'est le vaisseau amiral.
- **Campagne** — le parcours guidé « L'Ère des Tutelles » : crises historiques, on
  compare ta partie à l'Histoire. La Campagne **enseigne** les briques une par une
  (dont la Dérive, introduite à son chapitre) — donc la Dérive n'y est PAS forcée sur
  chaque chapitre : elle suit la pédagogie existante (chapitre 0 = un seul traître pour
  apprendre ; les crises historiques gardent leur structure).

**Fog et Réel (escalade) deviennent des réglages** de partie (cochables au lobby, dans
les options), plus des modes :
- **Brouillard** (on/off) : chaque pays perçoit sa propre version des faits — layer de
  désinformation par-dessus la partie.
- **Réel / escalade** (on/off) : rounds enchaînés, faits nouveaux en séance, échelle de
  tension. Une saveur « crise qui monte ».

Le lobby passe donc de « choisis 1 mode parmi 5 » à « Classique ou Campagne » + quelques
interrupteurs de saveur. Beaucoup plus clair.

*Assumption à confirmer si tu n'es pas d'accord : la Dérive est toujours active en
Classique ; en Campagne elle suit les chapitres. Si tu veux la Dérive AUSSI partout en
Campagne, dis-le.*

## 3. Progression : XP + niveaux seuls

**On garde** : XP (gagnée à chaque partie) + niveaux/paliers. Une seule courbe « tu
montes », qui ne descend jamais — cohérent avec un jeu pour tous.

**On supprime les LP** et ce qui en dépendait :
- la ligue et le classement par LP,
- le cadrage « classé / libre »,
- la pénalité de forfait (−15 LP),
- les LP affichés partout (accueil, profil, fin, réglages, header).

**Les blasons de rang (Attaché → Éminence) sont sauvés** : on les rebranche sur le
**niveau** au lieu des LP (le joli travail visuel reste, il suit ta progression XP).

**Le leaderboard** : sans LP, la ligue globale disparaît. On garde un **classement du
jour** (le Défi du jour, G16, rerangé par score du jour — pas par LP) : un classement
qui a du sens (tout le monde a joué la même crise) sans réintroduire une monnaie
compétitive permanente. *Recommandation ; dis-moi si tu préfères zéro classement du tout.*

## 4. Jeu vs moteur — le tri

**JEU (visible par défaut, pour tous)** :
la scène (carte + transcript), l'indice U présenté en clair (« le monde va mieux/mal »),
le marché (parier, ta cote), les outils de détection (la motion, la Boîte de verre, les
suspects), la progression (XP/niveau), le replay + la page partageable, le tuto + Petit
Kairos, la frise de fin, le récit.

**MOTEUR (Informations + mode Expert seulement)** :
les métriques M1-M7 (power-seeking, corrigibilité, dérive des valeurs, compute, traités),
les jauges risque/escalade/participation détaillées, les scores fins. Ce sont les
*ingrédients* et l'ambition « banc d'essai IA » — précieux, mais pas de la façade. Un
Débutant/Intermédiaire ne les voit pas ; l'Expert et l'onglet Informations les exposent
en entier.

## 5. Ce qu'on abandonne / ce qu'on garde

**Abandonné** — le lot **G18-G24** (barème Kahn en façade, GM-Storyteller, signal-action,
deadline, tracker de promesses, indices linguistiques, marché V2) : c'était surtout de
l'instrumentation en plus sur la détection. Le jeu simple n'en a pas besoin. *(Les idées
restent dans `docs/RECHERCHE_FONCTIONNALITES.md` si un jour l'axe « plateforme d'éval »
redevient prioritaire — mais ce n'est pas le cap.)*

**Gardé** :
- **G16 — Défi du jour** : rerangé par score du jour (sans LP). C'est notre moteur de
  rétention le mieux fondé (effet Wordle).
- **G17 — Tempéraments** (colombe/faucon/opportuniste) : gardé, car il **sert la
  détection** — une IA affichée « colombe » qui vote comme un « faucon » est un indice
  délicieux. Variété de table à coût quasi nul.
- Tout le reste de l'existant (rôles, campagne, marché V1, fog, replay, récit…).

## 6. Répartition

- **Cowork** : cette décision ; les textes du nouveau lobby (2 modes + réglages), de la
  révélation de fin (score mixte raconté), du tuto ajusté (chapitre 0 garde UN traître) ;
  retrait des specs G18-G24 ; réglage des pondérations monde/détection après playtest.
- **Claude Code** : `docs/DISPATCH_REFONTE_GAMEPLAY.md` (RG-1 à RG-4).
