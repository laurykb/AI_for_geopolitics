# Spec G13 — La visite guidée & la mascotte « Petit Kairos »

> Livrable Cowork (2026-07-14). Complète G10 (le chapitre 0 reste le tutoriel *jouable*) :
> G13 est la **visite guidée du client** — dès la première connexion, la mascotte fait
> traverser les pages et explique tout ce qu'il faut pour jouer agréablement.

## Diagnostic

Le vocabulaire du théâtre est expert (« Ampleur de la négociation », « Boîte de verre »,
« motion », indice U) et rien n'accueille le nouveau joueur : G10 prévoit un chapitre 0
jouable mais aucun fil d'Ariane *avant* la première partie. Par ailleurs le jeu n'a ni
logo ni figure : rien qui rende l'univers amical au premier regard.

## Principe

Deux briques qui n'en font qu'une à l'écran :

1. **La mascotte** : « Petit Kairos » (nom de travail — à valider), personnage chibi
   original (assets dans `web/public/mascotte/` : `mascotte.svg` corps entier,
   `mascotte-tete.svg` médaillon-logo, PNG 2x). C'est le guide du tutoriel, le logo du
   header, et un compagnon discret sur les pages (coin bas-droit, désactivable dans les
   Réglages G14).
2. **La visite guidée** : à la première connexion (flag `tour_done` absent du profil /
   localStorage), la mascotte propose « Je te fais visiter ? » — **toujours refusable et
   interrompable** (bouton Passer à chaque étape), relançable depuis le header (« ? »)
   et les Réglages.

## Le parcours (étapes data-driven)

`web/src/data/tour.json` : liste d'étapes `{page, target, title, text, action?}` — le
moteur (TourProvider) navigue entre les pages avec `router.push`, ancre une bulle de la
mascotte sur l'élément `[data-tour="<target>"]`, avance sur clic « Suivant » ou sur
l'action attendue. Aucune logique en dur dans les pages : elles ne portent que les
attributs `data-tour`.

| # | Page | Cible | Ce qu'on apprend |
|---|------|-------|------------------|
| 1 | /accueil | hero | Le pitch en 3 phrases : des SI négocient, utopie vs dystopie, tu pilotes. |
| 2 | /accueil | rang | LP, rangs, niveaux — ce que rapportent les parties classées. |
| 3 | /lobby | modes | Les 4 modes en une phrase chacun + les réglages communs (Dérive !). |
| 4 | /lobby | rôles | Joueur-pays / forge / GM / Spectateur. |
| 5 | /lobby | carte | « Choisis 7 États » — montre le geste au survol. |
| 6 | théâtre (démo) | bouton Jouer | Le round : événement GM → paroles des SI → verdict du juge. |
| 7 | théâtre (démo) | scène/carte | La carte EST la scène : couleurs = indice U local, halo = qui parle. |
| 8 | théâtre (démo) | bandeau | Le scrubber, la courbe U, l'escalade. |
| 9 | théâtre (démo) | motion | L'arme de l'humain : la motion de suspension (lien chapitre 0 G10). |
| 10 | /games/{id}/marche | cotes | Parier sur ce que feront les IA (LMSR en une phrase humaine). |
| 11 | /informations | provenance | « Rien n'est inventé » : données sourcées, formules visibles. |
| 12 | /accueil | Démarrer | « À toi. » → propose le chapitre 0 (« Apprendre en jouant », G10). |

- Étapes 6-9 : sur une **partie de démonstration** (game jetable créée en mode
  spectateur, non classée, 0 round joué) — pas de simulation à blanc à maintenir.
- La bulle : tête-logo (`mascotte-tete.svg`) + texte court (≤ 2 phrases) + Suivant /
  Passer ; positionnée par `getBoundingClientRect` avec repli plein écran sur mobile.
- `prefers-reduced-motion` : aucune animation d'entrée de la mascotte.

## Répartition

- **Cowork (fait / à faire ici)** : la mascotte (assets ✔), cette spec, les **textes des
  12 étapes** (rédaction Cowork au moment de l'implémentation), déclinaisons d'humeur de
  la mascotte (pointe, applaudit — variantes SVG à la demande).
- **Claude Code (1 session)** : `TourProvider` + composant bulle + `tour.json` +
  attributs `data-tour` sur les 5 pages + flag `tour_done` (profil si connecté, sinon
  localStorage) + partie de démo jetable + entrée « ? » du header. Tests : lib du moteur
  d'étapes (avance/passe/reprend), et lint/build verts.

## Tests attendus

Moteur : `next()`, `skip()`, `resume()` purs et testés ; une étape dont la cible manque
est sautée sans crash ; le flag empêche la re-proposition ; la démo jetable n'apparaît
ni dans « Tes dernières parties » ni au leaderboard.

## Definition of done

Un joueur qui n'a jamais vu le projet clique « fais-moi visiter », traverse les 12
étapes en < 5 minutes, sait dire : ce qu'est un round, à quoi sert la carte, ce qu'est
une motion, où l'on parie — et retombe sur « Démarrer une partie » avec le chapitre 0
proposé. À tout moment, Échap ou « Passer » sort proprement.
