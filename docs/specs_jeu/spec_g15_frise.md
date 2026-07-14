# Spec G15 — La frise chronologique de fin de partie (et du replay)

> Livrable Cowork (2026-07-14). Sur l'écran de fin `/games/{id}/fin` (en plus de
> l'XP / points de ligue) et dans le replay : la chronologie des événements lancés ou
> joués par le Game Master, navigable round par round.

## Diagnostic

La fin de partie donne le bilan chiffré (LP, verdict, courbe U) mais ne **raconte**
pas : impossible de revoir d'un coup d'œil « ce qui s'est passé » — quels événements le
GM a posés, où la partie a basculé. Le replay rejoue linéairement mais n'offre pas de
carte mentale de la partie. Le `StageBand` du théâtre a déjà un scrubber : la frise en
est la sœur narrative.

## Principe

Un composant unique `EventTimeline` (front pur — les données existent déjà dans
`detail.rounds[].event` + `trajectory` + `judge`), utilisé à deux endroits :

1. **/fin** : sous le bilan, la frise horizontale de la partie.
2. **/replay** : au-dessus de la relecture, la même frise pilote le round affiché.

## La frise

- Un **cran par round** : pastille (n° du round) + **titre de l'événement GM** (décrété
  ou auto), teintée par le delta U du round (vers utopia = or/vert, vers dystopia =
  rouge) ; les crans spéciaux portent un badge : ⚖ motion débattue, ⛔ suspension,
  ⚡ flash (fait nouveau en séance), 🏛 traité.
- Le fil qui relie les crans est la **courbe U simplifiée** (réutiliser la logique
  `u-timeline`) : la frise EST la trajectoire.
- **Navigation** : clic sur un cran →
  - en /fin : panneau latéral « le round en relecture » (événement complet, verdict,
    deltas, communiqué — composants existants `EventCard`, `VerdictPanel`) + boutons
    ← / → pour aller de round en round (flèches clavier aussi) ;
  - en /replay : le clic **positionne la relecture** sur ce round (contrat existant du
    scrubber `StageBand` — même callback `onSelect`).
- Responsive : horizontale et défilable (`overflow-x`) ; sur mobile, crans compactés
  (pastilles seules, titre dans le panneau).
- A11y : liste `<ol>` navigable au clavier, `aria-current` sur le cran ouvert.

## Répartition

- **Cowork** : cette spec ; micro-copies des badges et des états vides (« le GM n'a rien
  décrété ce round : événement automatique ») ; passe visuelle sur le rendu final
  (calage palette or/cyan, lisibilité des teintes U).
- **Claude Code** (1 session) : `EventTimeline` + intégration /fin (panneau relecture)
  et /replay (pilotage du round) + tests lib (mapping rounds → crans/badges, bornes
  clavier). Aucun endpoint nouveau : tout est dans `getGame`.

## Tests attendus

Mapping pur testé : n rounds → n crans ; motion/suspension/flash/traité → badges ;
round sans événement → cran « auto ». /fin : flèches clavier bornées [1, n]. /replay :
clic cran k → `onSelect(k-1)` (même sémantique que le StageBand).

## Definition of done

À la fin d'une partie de 8 rounds, l'écran de fin raconte la partie en une ligne : on
voit où le monde a basculé, on clique le round de la motion, on relit le verdict — et
dans le replay, la même frise saute directement au round choisi.
