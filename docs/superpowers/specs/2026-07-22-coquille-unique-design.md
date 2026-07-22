# Refonte — La coquille unique (sous-projet A)

> **Statut** : design validé (brainstorming 2026-07-22). Terrain : `web/` (Next 16.2.10,
> React 19, App Router, TS, Tailwind v4). Sous-projet **A** d'une décomposition en 5.
> Contrat amont : `docs/RUNBOOK_THEATRE_GLOBE.md` (S11-S15), `docs/spec_theatre_globe.md`.

## 1. Intention

« Le hall doit devenir tout le jeu, un unique point d'entrée, un théâtre de jeu, l'espace
connexion, tout totalement refonte. » (directive user, 2026-07-22)

Aujourd'hui le jeu a une dizaine de surfaces d'entrée en parallèle (`/` connexion,
`/accueil` hub, `/lobby` création, `/hall` embryon S11, `/campagne`, `/laboratoire`,
`/defi`, header, …). On les collapse en **une seule coquille** : le `GlobeStage` (Three.js)
devient une **scène persistante montée au layout**, et connexion → hall → config → théâtre →
fin deviennent des **états** de cette scène. Point d'entrée unique : `/`, qui *est* le jeu.

**Décision de radicalité** (validée) : *Coquille unique totale* — `/accueil` et `/lobby`
supprimés (redirigés) ; Campagne/Labo/Défi deviennent des overlays du hall. Carve-outs
conservés en vraies routes hors coquille : `/r/[id]` (partage public SSR), replay, admin.

**Décision de navigation** (validée) : *Globe + HUD utilitaire mince* — navigation de jeu
diégétique (portes/cartes sur le globe) ; un HUD fin persistant porte l'utilitaire
(pseudo→réglages, langue, déconnexion, retour au hall).

## 2. Architecture

**Approche retenue** (① sur 3) : *globe au layout + couches d'overlay*. Un composant monté
dans un `layout.tsx` **persiste** (montage + état) quand on navigue entre routes enfant qui
partagent ce layout — comportement natif de l'App Router. On l'exploite : `GlobeStage` est
monté **une fois**, il ne se démonte plus, il est piloté par un store partagé.
(Alternatives écartées : ② machine mono-route → perd les URLs du jeu live + réécriture
massive du théâtre ; ③ globe singleton en portail → plomberie custom anti-framework.)

### 2.1 Nouveaux éléments

- **`StageShell`** (client) — monté dans le layout du groupe `(shell)`. Rend `GlobeStage`
  dans un `<div class="fixed inset-0">` de fond + le **HUD utilitaire mince**. Ne se démonte
  jamais. Rend `{children}` (les overlays) par-dessus.
- **`StageDirector`** — contexte React + reducer **pur** (aucune dépendance nouvelle). Porte
  `{ phase, stageProps }` où `phase ∈ connexion | hall | config | theatre | fin`.
  `stageProps` = superset des props `GlobeStage`. Actions : `authenticated`, `enterHall`,
  `chooseMode(mode)`, `configurePatch(patch)`, `launch(gameId)`, `enterTheatre`,
  `setStageProps(props)`, `finish(reveal)`, `returnToHall`. Hook `useStageDirector()`.
- **Les pages deviennent des couches d'overlay** : elles ne montent plus de globe ; elles
  poussent leur intention via `useStageDirector()` et rendent leur DOM (formulaires,
  panneaux kit `thk-*`) au-dessus du globe du layout.

### 2.2 Route map (point d'entrée unique)

| URL | Rôle | Coquille ? |
|---|---|---|
| `/` | Coquille : machine à états `connexion → hall → config` (états, deep-link `?vue=`) | oui |
| `/games/[id]` | État `theatre` : page live **allégée** (lit le globe du layout ; SSE/docks/onglets inchangés) | oui |
| `/games/[id]/fin` | État `fin` : cérémonie (contenu bilan réutilisé en overlay) | oui |
| `/campagne`, `/laboratoire`, `/defi` | **Routes sous la coquille** (globe persistant derrière = effet overlay, panneau kit) ; ouvertes depuis les portes du hall | oui |
| `/profil`, `/reglages`, `/informations`, `/admin`, `/dev/globe` | Routes utilitaires sous la coquille | oui |
| `/r/[id]` (+ opengraph) | **Carve-out** : partage public SSR anonyme — globe/HUD/auth masqués | non |
| `/accueil`, `/lobby` | **Supprimées** → redirigent vers `/` (`next.config`) | — |

**Un seul root layout** (confirmé docs Next 16, §2.4) : `app/layout.tsx` garde `<html><body>` +
providers et monte `StageShell` (îlot client) qui rend le globe + HUD. `StageShell` **masque**
globe/HUD quand `pathname` commence par `/r/` (même patron que `SiteHeader`/`AuthGate`
aujourd'hui) → le partage public SSR reste nu, anonyme, sans globe. Pas de route group ni de
multi-root-layout (ceux-ci forceraient un *full reload* = remontage du globe WebGL).
`{children}` (dont `/r/[id]`, Server Component) est passé À TRAVERS `StageShell` client → reste
rendu côté serveur. **Campagne/Labo/Défi ne sont pas repliés dans `/`** : ils restent des routes
sous ce même layout, donc le globe persiste derrière eux et la navigation depuis le hall se vit
comme un changement d'overlay, pas de page.

### 2.3 Le voyage

```
/  →  [connexion]  (pseudo/mdp/invité, globe en rotation lente)
   →  auth ok  →  [hall]  (portes Classique/Campagne/Labo/Défi + pastille joueur)
   →  Classique  →  [config]  (composer le sommet SUR le globe : rôles dont ONU,
                                pays au clic, casting, réglages — parité S11 totale)
   →  Lancer  →  plongée caméra  →  /games/[id] [theatre]  (même globe, continu)
   →  partie finie  →  [fin]  (cérémonie sur le globe)  →  retour [hall]
```

### 2.4 Faits Next 16.2.10 (docs bundlées, cités — `web/AGENTS.md`)

- **Persistance layout** (`01-getting-started/03-layouts-and-pages.md`) : « On navigation,
  layouts preserve state, remain interactive, and do not rerender. » → globe monté au root
  layout = jamais démonté entre routes enfant partagées.
- **`template.tsx` REMONTE** (`file-conventions/template.md`) : « templates … children Client
  Components reset their state … DOM elements … fully recreated. » → **zéro `template.tsx`**
  dans la chaîne du globe.
- **Multi-root-layout = full reload** (`file-conventions/route-groups.md`, `layout.md`) → **un
  seul** root layout au-dessus des routes qui gardent le globe.
- **`ssr:false` = Client Component only** (`guides/lazy-loading.md`) → `StageShell`/`GlobeStage`
  portent `'use client'` (déjà le cas).
- **Redirections** : `async redirects()` dans `next.config` (statique, `permanent:true` = 308) ;
  `redirect()` (throw, hors `try`) en Server Component ; `useRouter().replace()` en event
  handler client (jamais `redirect()` dans un handler). Ex-`middleware` → `proxy` (v16, non utilisé ici).
- **`params`/`searchParams` = `Promise`** (async) : ne pas régresser les pages qui les lisent
  (`/games/[id]`). Query sans remonter le globe : `useSearchParams` (sous `<Suspense>`) +
  `window.history.pushState/replaceState` (intégrés au router).

## 3. La machine à états & le HUD

| Phase | Overlay DOM | État du globe |
|---|---|---|
| `connexion` | pseudo/mdp/invité (kit verre) | planète, rotation lente, pas de délégués |
| `hall` | portes diégétiques (Classique · Campagne · Labo · Défi ; Forge/Casting = cartes v1.5→E) | planète, orbite douce |
| `config` | panneau de compo à droite | **pickable** : rôles (ONU siège Genève, forgé siège océanique), délégués posés/retirés au clic, incarnation = halo cyan + badge VOUS |
| `theatre` | colonne transcript à onglets + docks (existant) | délégués parlent/pensent, arcs, événement géoloc, billets, satellite, épingles, cicatrices, motion |
| `fin` | carte score mixte + XP | cérémonie (accusé isolé, chute du masque, onde du Juge) — minimal en A, chorégraphie → E |

**Transitions** (reducer pur, testable) : `connexion→hall` (auth) · `hall→config` (Classique) ·
`config→theatre` (Lancer, plongée caméra) · `theatre→fin` (done) · `fin→hall` (retour) ·
`hall→{campagne|labo|defi}` (overlays). Deep-link : `?vue=hall|config` sur `/` ; `/games/[id]`
reste une vraie route pour `theatre`/`fin` (back-button/partage OK).

**HUD utilitaire mince** (dans `StageShell`, persistant, kit `thk-*`) : gauche = marque + fil
d'Ariane de la phase (« Hall » / « Composer le sommet » / « Round 3 ») ; droite = pastille
pseudo → menu (Réglages · Profil · Informations · Déconnexion), langue, « Retour au hall ».
En phase `theatre`, le HUD se **réduit** à un coin discret. a11y + annonces sr-only conservées.

## 4. L'auth absorbée

Backend d'auth **inchangé** (`auth-provider.tsx`, `lib/auth.ts` Supabase **ou** Offline,
sessions, `is_admin`, invité). Seule la vue change :
- `/` non authentifié → overlay `connexion` ; authentifié → overlay `hall`.
- `AuthGate` : les routes protégées sans session redirigent vers `/` (qui montre l'overlay
  connexion). Plus de page login distincte.
- « Jouer maintenant sans compte » (CTA proéminent) → auth invité → **hall** (au lieu de
  plonger direct dans un chapitre). Friction quasi nulle, mais on atterrit dans le hall pour
  que le joueur voie le jeu.

## 5. Parité S11 (« rien ne se perd »)

`flow.ts` reste le **modèle pur** (rôles, `toggleCountry`, `canLaunch`, `buildCreateBody`,
`SUMMIT_SIZES`, casting) ; les overlays n'en sont que la vue. La checklist runbook S11 doit
être **complète dans l'overlay `config` avant** suppression du lobby :

☐ 4 rôles **+ ONU** (siège Genève) · pays forgé (siège océanique) · sélection 7/33 sur le
globe + tailles 5/7/9/12 · **forge complète** (nom + concept + **alliances réelles 0-3**) ·
casting multi-modèles + assignations par pays · scénarios · brouillard/escalade/pensée à
découvert · difficulté · rounds 3-20 · délai du tour 30-300 s · table G17 · langue · admin ·
**i18n `hall.*`** · **plongée caméra** de lancement.

Écarts à combler vs `/hall` actuel : alliances de forge, i18n `hall.*`, plongée caméra.

## 6. Migration incrémentale (6 paliers, commit atomique + vérif live à chacun)

**Inc 1 — StageShell + StageDirector (globe au root layout).** `app/layout.tsx` monte
`StageShell` (îlot client) : globe `fixed inset-0` en fond + squelette HUD. Masqué sur `/r/*`
ET `/games/*` (le théâtre garde son globe jusqu'à l'Inc 4). Reducer `StageDirector` pur + tests.
Le globe persiste sous `/`, `/campagne`, `/laboratoire`, `/defi`, `/profil`… Vérif live :
navigation sans remontage. Build + vitest verts.

**Inc 2 — Overlay `connexion`.** `/` devient la coquille : globe derrière + overlay connexion
si non-auth ; hall si auth. Auth réutilisée telle quelle. « Jouer sans compte » → hall. Vérif
login/invité live.

**Inc 3 — Overlays `hall` + `config` (parité totale, `/accueil` absorbé).** Porter le hall
depuis `/hall` en overlays de `/` lisant le globe du layout. Combler les écarts (alliances
forge, i18n `hall.*`, plongée caméra) ET absorber l'utile de `/accueil` (reprendre la dernière
partie, Défi du jour, rang de carrière). **Test doré de parité** (même `CreateGameBody` que
l'ancien lobby). Supprimer `/hall` + `/accueil` (redirect `/accueil`→`/`). Portes du hall →
`/campagne` `/laboratoire` `/defi` (globe persiste derrière). Vérif compose+lancement live.

**Inc 4 — Unification du théâtre (le morceau risqué, isolé).** Le globe du layout s'étend à
`/games/*` ; `GlobeTheatre` consomme ce globe unique (plus de montage propre) → **plongée
caméra continue** du hall au round 1. SSE/docks/onglets **inchangés**. Repli SVG conservé.
Vérif d'un round complet live. (Repli acceptable : voile de transition masquant un remontage,
l'unification pleine livrée en sous-palier — mais viser le continu.)

**Inc 5 — Bascule finale.** Rediriger `/lobby`→`/` (`next.config`), **supprimer** `/lobby`.
HUD final (`SiteHeader` devient le HUD mince ; nav → pastille joueur + retour hall). Vérif :
plus aucune route morte, tous les parcours passent par la coquille.

**Inc 6 — Passe polish world-class / futuriste.** `frontend-design` sur overlays/HUD/portes/
transitions (chanfreins kit, néon discret, plongée caméra) ; `prefers-reduced-motion` ; a11y ;
captures live du voyage complet.

## 7. Tests & vérification

- **Reducer `StageDirector`** : tests unitaires purs (transitions, gardes).
- **`flow.ts`** : suite existante + **test doré de parité** overlay config ↔ ancien lobby.
- **Pont de props** : le théâtre pousse bien `stageProps` dans le `StageDirector` (handle mocké).
- **Parcours** : vitest montant `/`, enchaînant connexion→hall→config (auth mockée), gardes `canLaunch`.
- **Redirections** : `/accueil`, `/lobby`, `/campagne`, `/laboratoire`, `/defi` redirigent.
- **Non-régression** : 418 vitest + ~1310 pytest **verts** (refonte front-only) ; `ruff` propre.
- **Vérif live** (protocole preview) : parcours complet dans le navigateur + captures.
- **Perf** : un seul globe (plus de remount) = budget respecté ou meilleur ; `pixelRatio ≤ 1.5`,
  `low-power`, pause si `document.hidden` conservés.

## 8. Non-goals (partent vers B-E, chacun son cycle spec→plan→impl)

- **B = S14** ONU jouable (hook avis avant verdict, SSE `org`, pupitre). A n'ajoute que le
  **siège** ONU en config (parité), pas la mécanique en round.
- **C = S15** Pouls du monde + worldmonitor v2 (dépêches SSE, halo d'instabilité). Socle C6 prêt.
- **D = S12** Laury 3D + tutoriel immersif (`mascot.ts`, compagnon caméra). A garde le hook
  tutoriel existant fonctionnel, sans mascotte 3D.
- **E = S13** cérémonie de fin chorégraphiée + cartes hall enrichies (Forge/Casting/Défi).

**Non-goals A** : aucune mécanique moteur nouvelle ; **aucun changement backend** (front-only
+ redirections) ; **aucune dépendance nouvelle** (`three` déjà présent) ; budget perf respecté.

## 9. Contraintes projet (rappel)

- `web/AGENTS.md` : lire les docs Next **bundlées** (`node_modules/next/dist/docs/`) avant tout
  code Next — breaking changes vs connaissances d'entraînement.
- Aucune animation pilotée par `setState` React : tout vit dans la boucle three (pilotage
  impératif via `GlobeHandle`).
- Commits atomiques conventionnels (`feat(web)/…`), LF (`.gitattributes`), `ruff`/tests verts
  à chaque palier.
- Jouable 12-65 ans : sophistication dans le moteur, surface simple ; repérage garanti (d'où
  le HUD mince).
