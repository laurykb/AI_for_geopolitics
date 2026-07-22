# Théâtre plein-cadre (alignement proto_9) — Plan d'exécution

> Cible user (2026-07-22) : le théâtre = **globe plein-cadre + HUD fixe** flottant dessus,
> à l'identique de `proto_9`, au lieu de la page qui scrolle (globe boîte 76vh + panneaux).
> **100 % JSX/CSS** : hooks SSE, effets, dérivations et interactions vitales NON modifiés.
> Classes CSS proto déjà dispo (`web/src/styles/hall.css` + `theatre-kit.css`).

## Décisions transverses (arbitrées par la cartographie)

1. **Globe** : garder le `GlobeStage` PROPRE de `GlobeTheatre`, le passer en `fixed inset-0`.
   **NE PAS** démasquer `StageShell` sur `/games/*` ni pousser `deriveGlobeView` dans le
   `StageDirector` (risque de fuite de clés `setStage` entre rounds + re-wiring handlers sur
   un jeu live). La migration « globe du layout partagé » = **Inc 4 ultérieur, découplé**.
2. **pointer-events** (pattern `ShellMain`-sur-`/`) : globe `fixed inset-0 z-0 pointer-events-auto` ;
   couche HUD `fixed inset-0 z-10 pointer-events-none`, chaque panneau enfant `pointer-events-auto`.
3. **Contrôles de round vitaux** (lancer round, `TurnComposer`, `MotionForm/VoteForm`, `SuspectBoard`)
   → restent dans le **slot `dock`** sous la colonne transcript (déjà câblé, aucun re-wiring).
4. **Gros panneau de commandes de round** (décret/brouillard/rejouer-crise) → **tiroir gauche
   « Mise en scène »**, fermé par défaut. Bouton primaire « lancer » reste dans le dock.

## Piège critique
`page.tsx:~1247` enveloppe `<GlobeTheatre>` dans `<div class="… -translate-x-1/2 …">` →
`transform` crée un bloc conteneur : tout `fixed` descendant se cale dessus, PAS sur le viewport.
**SP-1 doit sortir `GlobeTheatre` de ce wrapper AVANT tout passage en fixed.** (`main`/`ShellMain`/
`SiteHeader` sans transform — OK.)

## Sous-paliers (chacun vérifié live : DOM + un round SSE sans régression)

- **SP-0** — `globe-theatre.tsx` : `const FULL_FRAME = true;` gate tous les choix de className
  (rollback 1 caractère). `false` ⇒ rendu identique à aujourd'hui.
- **SP-1** — `page.tsx:~1247` : extraire `<GlobeTheatre>` du `<div -translate-x-1/2>`, enfant
  direct du root sans transform. Le reste (grid secondaire, StageBand) dans un wrapper distinct.
- **SP-2** — `globe-theatre.tsx` : boîte `h-[48vh]…md:h-[76vh]` (l.118) → plateau
  `fixed inset-0 z-0 pointer-events-auto` (GlobeStage `absolute inset-0`). La `<section>` devient
  la couche HUD `fixed inset-0 z-10 pointer-events-none`. Repli `StageMap` re-parenté.
- **SP-3** — `globe-theatre.tsx` : panneaux `absolute` → `fixed` + enfant `pointer-events-auto` :
  `#transcript` (top/right/bottom, w≈400px), controls+legend bas-gauche, `#fiche` tiroir gauche,
  `dock` sous la colonne. Garder les 3 volets MONTÉS (`hidden`) → ref/scroll transcript préservés.
- **SP-4** — `globe-theatre.tsx` : + `#brand` (haut-gauche), `#event-banner` (haut-centre pulsant,
  lit `view.eventTitle`/sévérité), `#hint` (bas-droite). Pur décor.
- **SP-5** — `page.tsx` : contenu du `<Panel>` commandes de round (~910-1244) → nœud `stageDrawer`
  (nouveau slot de `GlobeTheatre`, tiroir gauche fermé par défaut). États (`decree/fogId/…`)
  NON déplacés ; `play()` lit toujours les mêmes états.
- **SP-6** — `page.tsx` : grid secondaire (AlliancePills, DeadlineStrip, Relations, Forecast,
  ModelCast, OperationalPicture, ObservablesGrid, DirectiveComposer) → tiroir/onglet **Expert**
  (gaté `showEngine`). HUD principal ≤ 3 panneaux (Dialogues/Paris/Renseignement + fiche + legend).
  `StageBand` (scrubber+courbe U) → candidat band fixe bas-centre (garder `selected/setSelected`).
  `RoundConclusion` + `turnFailed` restent en overlays fixes (avis critiques).
- **SP-7** — cohabitation : masquer `SiteHeader` sur `/games/*` (chevauche `#brand`) ou z-index ;
  header interne page fusionné dans `#brand`/tiroir Expert ; audit pointer-events ; repli mobile
  (colonne empilée sous `md`, fixed plein-cadre en `md+`).

## Préservé intact (jamais réécrit — on ne déplace que des nœuds JSX)
`useRoundStream`, `submitTurn`/`speak`, `play`/`beginRound`/`startAccel`, `fileMotion`,
`submitMotionVote`, `deriveStageView`/`deriveGlobeView`/`stageInput`, tous les effets SSE,
le repli `StageMap`, `showEngine`, `selected/setSelected` (scrub).

## Risques
R1 transform-trap → SP-1 avant fixe. R2 SSE → plan JSX/CSS pur. R3 ref transcript → volets montés.
R4 double canvas → `StageShell` reste masqué sur `/games/*`. R5 `SiteHeader` vs `#brand` → SP-7.
