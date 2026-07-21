# Runbook — Refonte théâtre-globe (dispatch Cowork ⇄ Claude Code)

> **Contrat** : [`spec_theatre_globe.md`](spec_theatre_globe.md) (les décisions) +
> [`prototypes/theatre-globe.html`](prototypes/theatre-globe.html) (la référence visuelle et
> comportementale — l'ouvrir dans un navigateur, il est autonome ; touches **V** = 2D⇄3D,
> **L** = Laboratoire).
> Document **vivant** : cocher les cases au fil des commits. *Actif tant que la v1 du
> théâtre-globe n'est pas mergée.*

## Règles communes (non négociables)

- **JAMAIS de code copié de worldmonitor (AGPL-3.0)** — inspiration visuelle uniquement.
  La seule référence de code est notre prototype maison.
- Une seule dépendance front nouvelle : **`three`** (+ `@types/three`). Rien d'autre.
- **Aucune animation pilotée par `setState` React** : tout vit dans la boucle three / canvas.
- **Full-three** (décision 2026-07-21) : une seule scène pour les deux vues (le 2D = monde
  déplié). Texte en DOM (transcript, fiche, bulle) ; étiquettes courtes en sprites et bloom
  sélectif = v1.5, sous protocole perf.
- Chaque étape se termine par : tests verts (`pytest -q` / `npm test -- --run`), `ruff` propre,
  **commit atomique** conventionnel (`feat(globe): …`), fins de ligne LF (`.gitattributes`).
- Budget perf (la 2060S est partagée avec Ollama) : pixelRatio ≤ 1.5 en partie, `low-power`,
  pause si `document.hidden` ; **protocole spec §5** : tokens/s Ollama globe ON vs OFF,
  perte acceptée ≤ ~8 %.

## Partage des rôles

| Qui | Quoi | Pourquoi |
|---|---|---|
| **Cowork** | passes **C1-C3** : backend géoloc, briques front pures, socle suspicion | travail hors-app, testable hors ligne |
| **Claude Code** | étapes **S0-S9** : intégration dans l'app qui tourne | il voit l'app tourner et itère avec Laury |

**Anti-conflits** — Cowork ne touche pas `web/src/components/**` ; Claude Code ne touche pas
`simulation/geo.py`, `data/geo/**`, `web/src/lib/globe-view.ts` (livrables Cowork).
`stage-map.tsx` appartient à Claude Code.

## Passes Cowork

### C1 — Géolocalisation des événements (backend) — ✅ livré (2026-07-21)
- [x] `data/geo/gazetteer.json` : ~150 lieux stratégiques (détroits, mers, canaux, capitales,
  régions), clés **minuscules sans accents** + alias.
- [x] `simulation/geo.py` : `resolve_location(location_text, actors) -> (lon, lat, precision)` —
  cherche le gazetteer dans `event.location`, **repli déterministe** sur le barycentre des
  capitales des acteurs. Zéro réseau.
- [x] `GeoEvent` : champs **additifs** `geo_lon`, `geo_lat`, `geo_precision: "place"|"actors"|None`
  (rétro-compat totale) + enrichissement à l'émission de l'événement.
- [x] Prompt GM : exiger « Lieu : <ville/détroit/région précise> ».
- [x] Tests pytest hors ligne (gazetteer, repli, rétro-compat vieux rounds).
- **Contrat** : la trame SSE `event` porte déjà l'objet complet — rien à changer côté flux.

### C2 — Briques front pures — ✅ livré (2026-07-21)
- [x] `web/src/lib/globe-view.ts` : mapping état de jeu → props scène
  `{countries, uByCountry, speaking, thinking, pulse, misled, suspended, eventGeo, arc}`
  (dérivé de `LiveRound`/`GameDetail`, même esprit que `stage-view.ts`) + tests vitest.
- [x] `web/src/components/globe/flags.ts` : drapeaux canvas simplifiés des **33 pays du
  roster** (pur, testable) + test.

### C3 — Socle carnet de suspicion (backend)
- [ ] Épingles `{pays → 0-3, round}` dans `extras` du snapshot (additif), endpoint léger.
- [ ] Part **calibration** du score mixte (spec §4 bis : suspicion juste et précoce récompensée,
  faux positif coûteux) + tests.

### C4 — Kit UI futuriste — ✅ livré (2026-07-21)
- [x] `web/src/styles/theatre-kit.css` : tokens + composants (chanfreins, panneaux néon,
  CTA ambre, interrupteurs, onglets, casting, cartes de mode, balayage, scanlines,
  `prefers-reduced-motion`) — extraits du prototype, à adopter par S10.

## Étapes Claude Code

- [x] **S0** — Lire la spec, ouvrir le prototype dans un navigateur. `npm i three @types/three`
  (web/). Commit `chore`. *(fait 2026-07-21, `0033b20`)*
- [x] **S1** — `GlobeStage` client-only (`dynamic(() => …, {ssr:false})`) : globe + **texture
  canvas peinte** (palette planète futuriste, spec §1) + caméra orbitale (drag/molette/fly-to)
  + picking pays. Parité visuelle avec le prototype, **sans robots d'abord**.
  *(fait 2026-07-21, `8e6df20` — vérifié live, atelier `/dev/globe`)*
- [x] **S2** — Délégués humanoïdes + drone GM + entité Juge + arcs + anneau d'événement :
  transposer le prototype dans les modules de la spec §2 (`texture.ts`, `robots.ts`,
  `camera.ts`, `picking.ts`…). *(fait 2026-07-21, `e00caf1` — vérifié live)*
- [x] **S3** — **Le dépliage 2D⇄3D** (full-three, spec §5) : morph sphère⇄plan transposé du
  prototype (shader `uFlat`, ancres lerp/slerp, caméra oblique tactique, plan de picking)
  derrière `stageView` + touche V, point de vue préservé ; StageMap SVG rendue interactive
  (`onCountryClick`, `eventGeo`) **uniquement en repli sans WebGL**.
  *(fait 2026-07-22, `3fd6077` — vérifié live)*
- [x] **S4** — Layout immersif (spec §4) dans `app/games/[id]/page.tsx` : globe plein théâtre,
  transcript overlay droite **à onglets** (Dialogues · Paris · Renseignement), bandeau
  événement, contrôles bas-gauche, fiche gauche. *(fait 2026-07-22 — `GlobeTheatre`
  (composition : la page garde la donnée, le composant le plateau) + `CountryFiche` ;
  réglage `stageView` persisté (Réglages, clé wosi.stage) ; repli SVG si WebGL absent ou
  palier léger ; colonne empilée sous la scène en mobile (même DOM, le transcript garde
  sa ref) ; vérifié live sur une vraie partie)*
- [ ] **S5** — Branchements réels : bulle de pensée sur `turn.reasoning`/digest selon
  `expose_thinking` ; fiche sur les données Informations + état de partie ; géoloc via
  `geo_lon`/`geo_lat` (C1) avec repli barycentre côté front en attendant.
- [ ] **S6** — Perf + accessibilité : mesure tokens/s ON/OFF (protocole §5), réglages,
  `prefers-reduced-motion`, i18n fr/en, annonces sr-only conservées.
- [ ] **S7** — Campagne : vérifier que le chapitre hérite du théâtre sans code spécifique.
- [ ] **S8** — v1.5 « le jeu sur la carte » : piles de billets ← vraies cagnottes
  (`market_api`) ; satellite ← bureau de renseignement (coût compute, rapports réels).
- [ ] **S9** — v1.5 renforts gameplay (spec §4 bis) : UI du **carnet de suspicion** (épingles
  sur les robots ; socle C3), **cicatrices du monde** (couche texture ← `RoundSummary`),
  **motion de censure** en séquence de vote illuminée (trames SSE existantes).
- [x] **S10** — **Kit futuriste sur toutes les surfaces** (spec §9) : adopter
  `web/src/styles/theatre-kit.css` (tokens en `@theme` Tailwind et/ou classes telles
  quelles) sur `/`, `/accueil`, `/lobby`, `/campagne`, `/laboratoire`, `/defi`,
  `/reglages`, `/profil`, `/leaderboard`, header, `auth-gate` — texte net, chanfreins,
  néon discret, a11y intacte. *(fait 2026-07-22, `d9f2deb` — par le système : tokens
  rebasés + ui.tsx chanfreiné ; nota : le CSS du kit, non-layered, prime sur les
  utilitaires Tailwind → états sélectionnés en style inline ; vérifié live)*
- [ ] **S11** — **Le hall** (spec §9, prototype comme référence : états
  `auth → menu → config → game`) : GlobeStage monté au **layout** (scène persistante entre
  routes), connexion/lobby/config convertis en **overlays** ; choix du pays incarné **au
  clic sur le globe** (halo cyan + badge VOUS) ; lancement = plongée caméra vers le round 1 ;
  repli sans WebGL : mêmes pages sur fond `--thk-bg`.
  **Checklist anti-régression (spec §9 « rien ne se perd ») : chaque option du lobby
  actuel — 4 rôles, sélection 7/33 sur le globe (+ tailles 5-12), forge complète, casting
  multi-modèles avec répartition/assignations, scénarios, brouillard/escalade/pensée,
  difficulté, rounds 3-20, délai du tour 30-300 s, table G17, langue, admin — DOIT exister
  dans le hall avant de supprimer l'ancien lobby.**
- [ ] **S12** — **Laury en 3D + tutoriel immersif** (spec §10, prototype comme référence) :
  `mascot.ts` (chibi fidèle au SVG maître, contour-coques, petit monde = texture du théâtre),
  compagnon caméra + présentation des cibles ; la visite guidée à portes rebranchée sur les
  jalons de `tutorial-events.ts` ; entrée « Première fois ? » au hall.
- [ ] **S13** — **Cérémonie de fin + entrées du hall** (spec §11) : fin de partie sur le
  globe (accusé isolé, chute du masque, onde du Juge, score mixte + XP en carte kit) ;
  cartes hall : Défi du jour, Forger un pays (v1.5), casting des modèles (v1.5).

## Ordre & dépendances

- **S0-S2 démarrent tout de suite** (aucune dépendance).
- S3 consomme `globe-view.ts` (C2) — si C2 n'est pas livré, coder contre l'interface
  documentée ci-dessus et brancher ensuite.
- S5 dépend de C1 (repli barycentre front en attendant). S9-score dépend de C3 (l'UI des
  épingles peut venir avant).
- S10 (kit, surfaces existantes) peut démarrer dès maintenant — indépendant du globe.
  S11 (hall) vient après S1-S3 (il réutilise la scène et le morph).
- S12 (mascotte/tutoriel) vient après S2 ; S13 (cérémonie, hall enrichi) après S11.

## Definition of done (v1)

Une partie **Classique se joue entièrement sur le globe** (et en 2D via V) : fiche au clic,
bulle de pensée si `expose_thinking`, événement géolocalisé qui pulse au bon endroit, StageMap
en repli automatique sans WebGL, Campagne héritée. Suite pytest (~1310) + vitest verts, `ruff`
propre, perte tokens/s ≤ ~8 %.
