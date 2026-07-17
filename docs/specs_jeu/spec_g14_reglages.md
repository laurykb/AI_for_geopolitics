# Spec G14 — Réglages utilisateur (langue · confort · compte)

> Livrable Cowork (2026-07-14). Page `/reglages` hors admin, accessible depuis le header
> (avatar) — trois panneaux : Langue, Confort & performances, Compte.

## Diagnostic

Aucun réglage utilisateur n'existe : la langue est le français en dur (UI **et**
dialogues des SI), le décor spatial (étoiles, nébuleuse, carte d3, animations de scène)
tourne à plein même sur les petites machines, et un joueur ne peut ni changer son mot de
passe ni supprimer son compte.

## Principe

Une page unique `/reglages`, trois panneaux, chaque réglage appliqué immédiatement et
persisté (profil côté backend quand il existe, localStorage en repli). La mascotte G13 y
prend ses ordres (« compagnon : on/off », « relancer la visite »).

## 1. Langue

- **UI** : dictionnaires `web/src/i18n/{fr,en}.json` + petit hook `useT()` (clé →
  chaîne). Pas de framework i18n tant que 2 langues suffisent (« simplicité d'abord »).
  Le français reste la langue source ; l'anglais est la première cible.
- **Dialogues** : la langue voyage jusqu'au moteur — `POST /api/games` gagne
  `language: "fr" | "en"`, stockée sur la partie ; les prompts (agents, GM, juge,
  narrateur) prennent une consigne de langue ; le RAG répond dans la langue de la
  partie. **Une partie garde sa langue de création** (pas de mélange mi-partie).
- Sélecteur : « Langue du jeu » (UI) + note claire : « les nouvelles parties seront
  jouées dans cette langue ; les parties existantes gardent la leur ».

## 2. Confort & performances

Un seul état `perf: "plein" | "confort" | "léger"` + dérogations fines :

| Réglage | plein | confort | léger |
|---------|-------|---------|-------|
| Étoiles/nébuleuse/lune du décor | ✔ | ✔ statiques (pas de twinkle/shoot) | ✘ (fond uni) |
| Animations de scène (pulses, breathe, intro-zoom, transitions lobby) | ✔ | réduites (durées ÷2, pas de zoom) | ✘ |
| Carte : halos, chemins U animés | ✔ | ✔ | simplifiés (aplats) |
| Flou de verre (`backdrop-blur`) | ✔ | ✔ | ✘ (surfaces opaques) |
| Résolution de rendu de la carte | 1x | 1x | 0.75x (viewBox réduit) |

- Implémentation : une classe sur `<html>` (`perf-confort` / `perf-leger`) + variantes
  CSS dans `globals.css` — les composants n'en savent rien. `prefers-reduced-motion`
  impose au minimum « confort ».
- Toggle dédié « désactiver toutes les animations » = raccourci vers le comportement
  reduced-motion existant (déjà couvert par les media queries : on le force par la
  classe).

## 3. Compte

- **Changer le mot de passe** : ancien + nouveau ×2, via l'API d'auth existante
  (`lib/auth.ts`) ; messages d'erreur humanisés ; jamais le mot de passe en clair dans
  un state persisté.
- **Supprimer le compte** : `ConfirmDialog` du kit (« irréversible : parties anonymisées,
  LP effacés ») + saisie du pseudo pour confirmer → `DELETE /api/players/{id}` (backend :
  anonymiser `owner_id` des parties publiées, purger le reste) → déconnexion → **retour
  à la page d'accueil** (`/`).

## Répartition

- **Cowork** : cette spec ; extraction des chaînes FR + traduction EN des dictionnaires
  (gros volume, itératif) ; relecture des consignes de langue des prompts.
- **Claude Code** (2 sessions) :
  1. Front : page `/reglages`, hook `useT` + dictionnaires branchés sur ~5 pages
     pilotes (accueil, lobby, header, fin, réglages), classes perf dans `globals.css`,
     compte (2 formulaires + flux de suppression).
  2. Backend : `language` sur la partie + consigne de langue dans les prompts (agents,
     GM, juge, narrateur), endpoints mot de passe / suppression + anonymisation. Tests
     pytest : création avec langue, prompt contient la consigne, suppression anonymise.

## Tests attendus

Front : useT retombe sur la clé FR si l'EN manque ; la classe perf change sans reload ;
suppression → redirection accueil + session purgée. Backend : partie EN → prompts EN ;
suppression → parties publiées conservées anonymes, le reste purgé.

## Definition of done

Un joueur passe le jeu en anglais, lance une partie : les SI négocient en anglais ; un
portable modeste en mode « léger » tient le théâtre fluide (pas de blur, pas de
particules) ; changer de mot de passe et supprimer son compte se font sans quitter la
page — et la suppression ramène à l'accueil.
