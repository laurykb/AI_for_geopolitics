# Coquille unique — Plan d'implémentation (sous-projet A)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development ou
> superpowers:executing-plans, tâche par tâche. Étapes en cases à cocher (`- [ ]`).
> Spec de référence : `docs/superpowers/specs/2026-07-22-coquille-unique-design.md`.

**Goal:** Faire du globe la scène persistante d'une coquille unique — connexion → hall → config
→ théâtre → fin comme états d'une seule scène montée au root layout, point d'entrée unique `/`.

**Architecture:** Un seul root layout (`app/layout.tsx`) monte `StageProvider` + `StageShell`
(îlot client) qui rend `GlobeStage` en fond `fixed inset-0` (dynamic, `ssr:false`) + un HUD mince.
Les pages deviennent des overlays qui poussent leur intention visuelle dans un `StageDirector`
(reducer pur). `StageShell` se masque sur `/r/*` (partage public) et, jusqu'à l'Inc 4, sur
`/games/*` (le théâtre garde son globe). `flow.ts` reste le modèle pur de composition.

**Tech Stack:** Next 16.2.10 (App Router), React 19.2, TypeScript, Tailwind v4, Three.js 0.185,
kit `theatre-kit.css`. Tests : vitest. Auth : `lib/auth.ts` (Supabase/Offline) inchangée.

## Global Constraints

- **`web/AGENTS.md`** : lire les docs Next **bundlées** (`node_modules/next/dist/docs/01-app/`)
  avant tout code Next. Faits établis (spec §2.4) : layouts persistent en navigation ; **zéro
  `template.tsx`** dans la chaîne du globe ; **un seul root layout** ; `ssr:false` = Client
  Component only ; redirections via `next.config async redirects()` (`permanent:true` = 308) ;
  `params`/`searchParams` = `Promise`.
- **Aucune animation par `setState`** : le globe s'anime dans sa boucle three ; on ne fait que
  lui passer des props (contrat `GlobeStageProps`).
- **Aucune dépendance nouvelle** (`three` déjà présent).
- **Aucun changement backend** (front-only + redirects).
- Commits atomiques conventionnels (`feat(web)/…`), **LF** (`.gitattributes`), `ruff`/tests verts
  à chaque palier. Vérif **live** (Browser pane) à chaque incrément.
- Parité S11 « rien ne se perd » (spec §5) avant toute suppression de route.

---

## Structure de fichiers

**Créer :**
- `web/src/lib/stage-director.ts` — reducer **pur** : `Phase`, `StageIntent`, `DirectorState`,
  `DirectorAction`, `directorReducer`, `INITIAL_DIRECTOR`, `phaseDefaults(phase)`.
- `web/src/lib/stage-director.test.ts` — tests du reducer.
- `web/src/components/shell/stage-provider.tsx` — contexte React (`useReducer` sur le reducer
  pur) + `useStageDirector()` + registre de handlers (`onCountryClick`, `onViewToggle`, `onUserDrag`).
- `web/src/components/shell/stage-shell.tsx` — îlot client : `GlobeStage` fond + HUD ; masquage
  `/r/*` + `/games/*` ; branche `view`/`onViewToggle` (settings) et le pick handler (director).
- `web/src/components/shell/hud.tsx` — HUD mince (fil d'Ariane de phase + pastille joueur/menu +
  langue + « retour au hall »).
- `web/src/components/shell/connexion-overlay.tsx` — Inc 2 (extrait de l'actuel `/`).
- `web/src/components/shell/hall-overlay.tsx` — Inc 3 (portes + reprendre + Défi + rang).
- `web/src/components/shell/config-overlay.tsx` — Inc 3 (porté de `/hall`, parité + alliances).
- `web/src/components/shell/config-overlay.parity.test.ts` — test doré `buildCreateBody`.

**Modifier :**
- `web/src/app/layout.tsx` — monter `StageProvider` + `StageShell` autour du chrome existant.
- `web/src/app/page.tsx` — devient la coquille (overlays connexion/hall/config) — Inc 2-3.
- `web/next.config.ts` — `async redirects()` (`/accueil`→`/`, `/lobby`→`/`) — Inc 3/5.
- `web/src/components/auth-gate.tsx` — la connexion n'est plus une page mais l'état de `/` — Inc 2.
- `web/src/components/theatre/globe-theatre.tsx` + `app/games/[id]/page.tsx` — Inc 4.
- `web/src/components/site-header.tsx` → fondu dans le HUD — Inc 5.

**Supprimer :** `app/hall/page.tsx` + `app/accueil/page.tsx` (Inc 3) ; `app/lobby/page.tsx` (Inc 5).

---

## Inc 1 — StageDirector (pur) + StageShell (globe au layout)

### Task 1.1 : le reducer pur `stage-director.ts`

**Files:** Create `web/src/lib/stage-director.ts`, Test `web/src/lib/stage-director.test.ts`

**Produces:**
```ts
export type Phase = "connexion" | "hall" | "config" | "theatre" | "fin";
// Intention visuelle = sous-ensemble des props GlobeStage (sans les callbacks).
export type StageIntent = Partial<Omit<GlobeStageProps,
  "onCountryClick" | "onViewToggle" | "onUserDrag" | "onUnsupported" | "view" | "className">>;
export type DirectorState = { phase: Phase; stage: StageIntent };
export type DirectorAction =
  | { type: "goPhase"; phase: Phase; stage?: StageIntent }
  | { type: "setStage"; stage: StageIntent };
export const INITIAL_DIRECTOR: DirectorState;
export function phaseDefaults(phase: Phase): StageIntent; // globe par défaut d'une phase
export function directorReducer(s: DirectorState, a: DirectorAction): DirectorState;
```
Règles : `goPhase` → `{ phase, stage: { ...phaseDefaults(phase), ...(action.stage ?? {}) } }`
(remise à plat aux défauts de la phase + override) ; `setStage` → `{ ...s, stage: { ...s.stage,
...action.stage } }` (merge sans perte). `INITIAL_DIRECTOR = { phase: "connexion", stage:
phaseDefaults("connexion") }`. `phaseDefaults` : connexion/hall = `{ countries: DEFAULT_COUNTRIES,
utopia: 0.5 }` sans `pickable` ; config = idem + `lisere: "#ffc14d"`. (import `DEFAULT_COUNTRIES`
de `@/lib/countries`.)

- [ ] **Step 1 — test qui échoue** :
```ts
import { describe, expect, it } from "vitest";
import { INITIAL_DIRECTOR, directorReducer, phaseDefaults } from "./stage-director";

describe("stage-director", () => {
  it("part en connexion avec le globe par défaut", () => {
    expect(INITIAL_DIRECTOR.phase).toBe("connexion");
    expect(INITIAL_DIRECTOR.stage.pickable).toBeUndefined();
  });
  it("goPhase config ouvre le picking doré", () => {
    const s = directorReducer(INITIAL_DIRECTOR, { type: "goPhase", phase: "config" });
    expect(s.phase).toBe("config");
    expect(s.stage.lisere).toBe("#ffc14d");
  });
  it("goPhase applique les défauts puis l'override", () => {
    const s = directorReducer(INITIAL_DIRECTOR, {
      type: "goPhase", phase: "config", stage: { countries: ["usa", "china"], chosen: "usa" },
    });
    expect(s.stage.countries).toEqual(["usa", "china"]);
    expect(s.stage.chosen).toBe("usa");
    expect(s.stage.lisere).toBe("#ffc14d"); // défaut de phase conservé
  });
  it("setStage fusionne sans perdre les autres clés", () => {
    const a = directorReducer(INITIAL_DIRECTOR, { type: "goPhase", phase: "config", stage: { countries: ["usa"] } });
    const b = directorReducer(a, { type: "setStage", stage: { chosen: "usa" } });
    expect(b.stage.countries).toEqual(["usa"]);
    expect(b.stage.chosen).toBe("usa");
  });
});
```
- [ ] **Step 2 — vérifier l'échec** : `cd web && npx vitest run src/lib/stage-director.test.ts` → FAIL (module absent).
- [ ] **Step 3 — implémenter** le module selon le contrat ci-dessus.
- [ ] **Step 4 — vérifier le succès** : même commande → PASS.
- [ ] **Step 5 — commit** : `feat(web): StageDirector — reducer pur des phases de la coquille`.

### Task 1.2 : `StageProvider` + `useStageDirector`

**Files:** Create `web/src/components/shell/stage-provider.tsx`
**Consumes:** Task 1.1. **Produces:** `<StageProvider>`, `useStageDirector()` →
`{ phase, stage, goPhase(phase, stage?), setStage(stage), handlers, setHandlers(h) }`.
`handlers` = `{ onCountryClick?, onViewToggle?, onUserDrag?, onUnsupported? }` stockés dans un ref
mutable (registration par l'overlay courant, pas dans l'état pur).
- [ ] **Step 1** : écrire le provider (`useReducer(directorReducer, INITIAL_DIRECTOR)` + ref
  handlers + hook). `"use client"`.
- [ ] **Step 2** : `npx tsc --noEmit` → clean.
- [ ] **Step 3 — commit** : `feat(web): StageProvider — contexte de la scène persistante`.

### Task 1.3 : `StageShell` (globe fond + masquage) + montage au layout

**Files:** Create `web/src/components/shell/stage-shell.tsx`, `web/src/components/shell/hud.tsx` ;
Modify `web/src/app/layout.tsx`.
**Consumes:** 1.2 + `GlobeStage` (dynamic, `ssr:false`) + `useSettings()` (view 3d/2d).
- [ ] **Step 1 — StageShell** : `"use client"`. `const hidden = pathname.startsWith("/r/") ||
  pathname.startsWith("/games/")`. Si `hidden` → `return null`. Sinon rend
  `<div className="fixed inset-0 -z-10"><GlobeStage {...stage} view={stageView}
  onViewToggle={toggleView} onCountryClick={handlers.onCountryClick} onUserDrag={...}
  onUnsupported={...} className="h-full w-full" /></div>` + `<Hud />`. (import `GlobeStage` via
  `dynamic(() => import("@/components/globe/globe-stage").then(m => m.GlobeStage), { ssr:false })`.)
- [ ] **Step 2 — Hud** : squelette mince (fil d'Ariane `phase` + placeholder pastille) stylé kit
  `thk-*`, `fixed top-0`. (Contenu complet en Inc 5 ; ici juste le socle + fil d'Ariane.)
- [ ] **Step 3 — layout** : envelopper le contenu dans `<StageProvider>` et insérer `<StageShell/>`
  juste après le `<body>` décor, AVANT le chrome ; garder `AuthProvider/SettingsProvider/TourProvider`.
  Le globe `-z-10` passe derrière `main`. **Ne pas** introduire de `template.tsx`.
- [ ] **Step 4 — build + tests** : `cd web && npm run build` (ou `npx tsc --noEmit`) + `npm test --
  --run` → verts.
- [ ] **Step 5 — vérif live** : `preview_start {name}` ; naviguer `/accueil` → `/campagne` →
  `/defi` : le globe reste **monté** (pas de flash de rechargement), masqué sur `/games/*` et `/r/*`.
- [ ] **Step 6 — commit** : `feat(web): StageShell — le globe monté au layout, persistant`.

---

## Inc 2 — Overlay connexion (l'espace connexion absorbé)

### Task 2.1 : `connexion-overlay.tsx` + `/` devient la coquille
**Files:** Create `web/src/components/shell/connexion-overlay.tsx` ; Modify `web/src/app/page.tsx`,
`web/src/components/auth-gate.tsx`.
**Consumes:** `getAuth()`, `useAuth()`, `useStageDirector()`.
- [ ] **Step 1** : extraire le formulaire pseudo/mdp/invité de l'actuel `app/page.tsx` en
  `ConnexionOverlay` (mêmes appels `signIn/signUp/continueAsGuest`), stylé kit, posé sur le globe
  (le globe vit dans StageShell — l'overlay ne monte plus de `<Globe>` 2D).
- [ ] **Step 2** : `app/page.tsx` : si `!player` → `goPhase("connexion")` + `<ConnexionOverlay/>` ;
  si `player` → `goPhase("hall")` (overlay hall arrive en Inc 3 ; ici, transitoire :
  `router.replace("/accueil")` tant que le hall overlay n'existe pas, PUIS bascule en Inc 3).
- [ ] **Step 3** : `auth-gate.tsx` : `isPublicRoute` inchangé (`/` + `/r/*`) ; la connexion vit
  sur `/`. « Jouer sans compte » → invité → phase hall (Inc 3) / `/accueil` transitoire.
- [ ] **Step 4 — vérif live** : `/` déconnecté montre l'overlay sur le globe ; login → accueil ;
  invité → accueil. Aucune régression auth.
- [ ] **Step 5 — commit** : `feat(web): l'espace connexion posé sur le globe persistant`.

---

## Inc 3 — Overlays hall + config (parité totale, /accueil + /hall absorbés)

### Task 3.1 : `hall-overlay.tsx` (portes + reprendre + Défi + rang)
Porte l'utile de `/accueil` (reprendre la dernière partie via `listGames`, Défi du jour via
`getDaily`/`startDaily`, rang via `getLeaguePlayer`+`rankForLevel`) + les 3 portes de mode
(Classique → phase config ; Campagne → `/campagne` ; Labo → `/laboratoire`) en overlay diégétique.
- [ ] Step 1 : composant `HallOverlay` (kit, portes + carte Défi + blason rang + reprendre).
- [ ] Step 2 : `goPhase("hall")` au montage ; portes = `goPhase("config")` ou `router.push`.
- [ ] Step 3 : vérif live (portes, Défi, reprendre, rang).
- [ ] Step 4 : commit `feat(web): le hall — portes, Défi du jour, reprise, rang`.

### Task 3.2 : `config-overlay.tsx` (parité S11 complète)
Porter le panneau de `/hall` (rôles + ONU, tailles 5/7/9/12, sélection au clic via
`goPhase("config", {pickable, ...})` + `setStage`, réglages, casting, lancement) ET combler les
écarts : **alliances de forge** (0-3, `registry`), **i18n `hall.*`**, **plongée caméra** au
lancement (voile + `usePlanetLaunch` puis `router.push`).
- [ ] Step 1 : composant `ConfigOverlay` réutilisant `flow.ts` (`buildCreateBody`, `canLaunch`,
  `toggleCountry`, `trimForRole`, `mapCapacity`, `SUMMIT_SIZES`) + `ModelCastSelector`.
- [ ] Step 2 : le clic globe : l'overlay enregistre `onCountryClick` via `setHandlers` et pousse
  `pickable`/`chosen`/`countries` via `setStage`.
- [ ] Step 3 : alliances de forge (repris de `/lobby`), i18n `hall.*` (ajouter clés fr/en).
- [ ] Step 4 : plongée caméra au lancement.

### Task 3.3 : test doré de parité
**Files:** Create `web/src/components/shell/config-overlay.parity.test.ts`
- [ ] Step 1 — test : pour un jeu d'entrées donné (rôle player, 7 pays, flag, réglages), l'appel
  `buildCreateBody(...)` de l'overlay config produit **exactement** le même `CreateGameBody` que
  celui de l'ancien lobby (mêmes args) — garantit « rien ne se perd ».
```ts
import { expect, it } from "vitest";
import { buildCreateBody, DEFAULT_SETTINGS } from "@/lib/flow";
it("config produit le meme body que le lobby", () => {
  const args = { scenario: "red_sea", baseMode: "classic" as const, settings: DEFAULT_SETTINGS,
    role: "player" as const, selected: ["usa","china","iran","france","egypt","saudi_arabia","uk"],
    flag: "france", language: "fr" as const };
  expect(buildCreateBody(args)).toMatchObject({ scenario: "red_sea", countries: args.selected,
    play_as: "france", horizon: 5, role: "player" });
});
```
- [ ] Step 2 : `npx vitest run` → PASS.

### Task 3.4 : suppression `/hall` + `/accueil` + redirects
- [ ] Step 1 : `app/page.tsx` : `player` → `<HallOverlay/>` / `<ConfigOverlay/>` selon phase (fin
  du transitoire Inc 2).
- [ ] Step 2 : supprimer `app/hall/page.tsx` + `app/accueil/page.tsx`.
- [ ] Step 3 : `next.config.ts` : `async redirects()` → `{source:"/accueil",destination:"/",permanent:true}`,
  `{source:"/hall",destination:"/",permanent:true}`. (`/lobby` en Inc 5.)
- [ ] Step 4 — vérif live : composer un sommet sur le globe + **lancer une vraie partie**
  end-to-end ; `/accueil` et `/hall` redirigent vers `/`.
- [ ] Step 5 — tests verts + commit `feat(web): le hall devient la porte unique — /accueil et /hall absorbés`.

---

## Inc 4 — Unification du théâtre (à bite-sizer sur place)

À détailler après lecture complète de `app/games/[id]/page.tsx` (~1650 l.) et `globe-theatre.tsx`.
Objectif : le globe du layout s'étend à `/games/*` ; `GlobeTheatre` consomme ce globe unique
(plus de `dynamic` propre) via `useStageDirector` (`goPhase("theatre")` + `setStage` à chaque tick
SSE) → **plongée caméra continue** hall→round 1. SSE/docks/onglets/repli SVG **inchangés**.
Sous-tâches prévues : (a) retirer le masquage `/games/*` de StageShell ; (b) `GlobeTheatre` pousse
`stage` au lieu de monter `GlobeStage` ; (c) fiche/colonne/dock restent en overlay ; (d) vérif d'un
round complet live ; (e) repli : voile de transition si remontage inévitable. Commit dédié.

## Inc 5 — Bascule finale
- [ ] `next.config.ts` : redirect `/lobby`→`/` (permanent) ; supprimer `app/lobby/page.tsx`.
- [ ] HUD final : `SiteHeader` fondu dans `hud.tsx` (pastille joueur → Réglages/Profil/
  Informations/Déconnexion, langue, « retour au hall ») ; `HeaderNav` migré ; en phase `theatre`
  HUD réduit.
- [ ] Vérif : aucune route morte ; tous les parcours passent par `/`. Commit.

## Inc 6 — Passe polish world-class / futuriste
- [ ] `frontend-design` sur overlays/HUD/portes/transitions (chanfreins kit, néon discret, plongée
  caméra, `thk-sweep`) ; `prefers-reduced-motion` respecté ; a11y (sr-only, focus, aria) ;
  responsive mobile ; captures live du voyage complet. Commit.

---

## Self-review (couverture spec → tâches)

- §2 architecture (globe au root layout, StageDirector) → Inc 1. ✅
- §2.4 faits Next → Global Constraints + Inc 1 (ssr:false, pas de template, un root layout). ✅
- §3 machine à états + HUD → Inc 1 (director + HUD socle), Inc 5 (HUD final). ✅
- §4 auth absorbée → Inc 2. ✅
- §5 parité S11 (rôles+ONU, tailles, forge+alliances, casting, réglages, i18n, caméra) → Inc 3 +
  test doré 3.3. ✅
- §6 migration 6 paliers → Inc 1-6. ✅
- §7 tests (reducer, parité, redirections, non-régression, live) → 1.1, 3.3, 3.4, chaque « vérif
  live ». ✅
- §8 non-goals (B-E) → hors plan (siège ONU en config = parité, pas la mécanique). ✅
