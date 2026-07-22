# Robots skinnés glTF (sous-projet B) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remplacer les délégués des pays du sommet par un robot skinné animé (RobotExpressive glTF), piloté par l'humeur, sans rien perdre du gameplay ; ONU/Labo restent low-poly.

**Architecture:** Un contrat `DelegateHandle` unifié (`setMood`/`update` + `group`/`spinner`/`base`/`veil`) que `makeRobot` (adapté, rendu identique) ET `makeSkinnedRobot` (nouveau) implémentent. `globe-stage` pilote les délégués pays via ce contrat, charge le glTF en amont (promesse cachée, `SkeletonUtils.clone` + `AnimationMixer` par délégué), et retombe sur `makeRobot` si le glTF échoue.

**Tech Stack:** three.js r185 (`three/addons` GLTFLoader + SkeletonUtils), Next.js 16, TypeScript, vitest.

## Global Constraints

- Cible RTX 2060S 8 Go, VRAM partagée Ollama → géométrie partagée entre clones (un upload), mixer en pause si `reduced-motion`.
- **Garder tout** : ancrage capitale, face-caméra (`spinner.rotation.y`), morph 2D⇄3D (anchors), voile fog (`veil`), cadenas suspension, teinte de vote (`base.material.color`), étiquettes, épingles de suspicion, glow orateur.
- Périmètre v1 : **pays du sommet uniquement**. ONU (`onu`) / Labo (`labA`/`labB`) restent `makeRobot`. Drone GM / orbe Juge inchangés.
- Conventions repo : LF, commits conventionnels, trailer `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`. Front dans `web/` : `npx tsc --noEmit`, `npx eslint src`, `npx vitest run`.
- Asset : `web/public/models/RobotExpressive.glb` (CC0, déjà committé). Clips : `Idle, Walking, Dance, Death, Sitting, Jump, Yes, No, Wave, Punch, ThumbsUp`. Morphs visage : `Angry, Surprised, Sad`.

---

## File Structure

- **Modify** `web/src/components/globe/robots.ts` — ajouter `DelegateHandle`, `MOOD_CLIP`/`moodToClip`, et un adaptateur `toDelegateHandle(robot)` OU faire renvoyer `makeRobot` un `DelegateHandle` (setMood/update enveloppant `setRobotMood`/`animateRobot`, rendu identique).
- **Create** `web/src/components/globe/skinned-robot.ts` — `loadRobotGltf()` (promesse cachée), `makeSkinnedRobot(opts): DelegateHandle`, mapping humeur→clip + expression.
- **Create** `web/src/components/globe/skinned-robot.test.ts` — mapping + contrat.
- **Modify** `web/src/components/globe/robots.test.ts` (ou existant) — contrat `DelegateHandle` de `makeRobot`.
- **Modify** `web/src/components/globe/globe-stage.tsx` — délégués pays via le contrat, skinné + repli, câblage async.

---

## Task 1: Contrat `DelegateHandle` + `makeRobot` adapté

**Files:**
- Modify: `web/src/components/globe/robots.ts`
- Test: `web/src/components/globe/robots.test.ts` (créer si absent)

**Interfaces:**
- Produces: `type DelegateHandle = { slug: string; group: THREE.Group; spinner: THREE.Group; base: { material: THREE.MeshBasicMaterial }; veil: THREE.Object3D; mood: RobotMood; setMood(mood: RobotMood): void; update(t: number, dt: number, reduced: boolean): void }`. `makeRobot(opts)` renvoie désormais un `DelegateHandle` (superset de l'ancien `RobotHandle`, champs internes conservés).

- [ ] **Step 1: Test — makeRobot expose le contrat DelegateHandle**

```ts
// robots.test.ts
import * as THREE from "three";
import { makeRobot } from "./robots";
it("makeRobot expose le contrat DelegateHandle", () => {
  const r = makeRobot({ slug: "usa", hue: "#4ea8ff", lonlat: [-77, 38], flagMap: null });
  expect(r.slug).toBe("usa");
  expect(r.group).toBeInstanceOf(THREE.Group);
  expect(r.spinner).toBeInstanceOf(THREE.Group);
  expect(r.base.material).toBeInstanceOf(THREE.MeshBasicMaterial);
  expect(typeof r.setMood).toBe("function");
  expect(typeof r.update).toBe("function");
  r.setMood("speaking");
  expect(r.mood).toBe("speaking");
  r.update(0, 0.016, false); // ne jette pas
});
```

- [ ] **Step 2: Run — échoue** — `cd web && npx vitest run robots` → FAIL (`setMood`/`update` absents).

- [ ] **Step 3: Implémenter** — dans `robots.ts` : exporter `type DelegateHandle` ; faire renvoyer `makeRobot` un objet qui étend l'actuel avec `setMood: (m) => setRobotMood(handle, m)` et `update: (t,_dt,reduced) => animateRobot(handle, t, reduced)` (garder `setRobotMood`/`animateRobot` internes ; rendu identique). `veil` typé `THREE.Object3D`, `base` conserve `material`.

- [ ] **Step 4: Run — passe** — `cd web && npx vitest run robots` → PASS.

- [ ] **Step 5: Commit** — `git commit -m "refactor(web): DelegateHandle unifie + makeRobot adapte (rendu identique)"`.

---

## Task 2: Mapping humeur→clip/visage + `skinned-robot.ts`

**Files:**
- Create: `web/src/components/globe/skinned-robot.ts`
- Test: `web/src/components/globe/skinned-robot.test.ts`

**Interfaces:**
- Consumes: `DelegateHandle`, `RobotMood` (Task 1).
- Produces: `moodToClip(mood): { clip: string; face: "" | "Angry" | "Sad" | "Surprised" }` (pur) ; `loadRobotGltf(): Promise<GLTF>` (caché) ; `makeSkinnedRobot(opts: { slug; hue; lonlat; flagMap; gltf: GLTF }): DelegateHandle`.

- [ ] **Step 1: Test — mapping humeur→clip/visage (pur)**

```ts
// skinned-robot.test.ts
import { moodToClip } from "./skinned-robot";
it("mappe chaque humeur vers un clip et une expression", () => {
  expect(moodToClip("idle")).toEqual({ clip: "Idle", face: "" });
  expect(moodToClip("thinking")).toEqual({ clip: "Idle", face: "" });
  expect(moodToClip("speaking").clip).toBe("Wave");
  expect(moodToClip("speaking").face).toBe("Surprised");
  expect(moodToClip("suspended")).toEqual({ clip: "Sitting", face: "Sad" });
});
```

- [ ] **Step 2: Run — échoue** — `cd web && npx vitest run skinned-robot` → FAIL (module absent).

- [ ] **Step 3: Implémenter le mapping + squelette du module**

```ts
// skinned-robot.ts
import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { clone as cloneSkeleton } from "three/addons/utils/SkeletonUtils.js";
import type { GLTF } from "three/addons/loaders/GLTFLoader.js";
import { toXYZ } from "./picking";
import { ROBOT_SCALE, type DelegateHandle, type RobotMood } from "./robots";

type Face = "" | "Angry" | "Sad" | "Surprised";
export function moodToClip(mood: RobotMood): { clip: string; face: Face } {
  switch (mood) {
    case "speaking": return { clip: "Wave", face: "Surprised" };
    case "suspended": return { clip: "Sitting", face: "Sad" };
    case "thinking": return { clip: "Idle", face: "" };
    default: return { clip: "Idle", face: "" };
  }
}

let gltfPromise: Promise<GLTF> | null = null;
export function loadRobotGltf(): Promise<GLTF> {
  gltfPromise ??= new Promise((res, rej) =>
    new GLTFLoader().load("/models/RobotExpressive.glb", res, undefined, rej),
  );
  return gltfPromise;
}
```
(La suite `makeSkinnedRobot` — clone, mixer, socle/veil, échelle, ancrage — est écrite ici mais son rendu se vérifie en Task 3/4. Squelette : cloner `gltf.scene`, `new THREE.AnimationMixer(clone)`, indexer les actions par `clip.name`, poser `clone` dans un `spinner`, `group` ancré via `toXYZ(lon,lat,1.001)` + quaternion normale — MÊME ancrage que `makeRobot` ; ajouter `base` (MeshBasicMaterial hue) + `veil` (CircleGeometry) réutilisés du patron low-poly ; échelle calée sur la stature low-poly.)
```

- [ ] **Step 4: Run — passe** — `cd web && npx vitest run skinned-robot` → PASS (mapping).

- [ ] **Step 5: `tsc` + commit** — `cd web && npx tsc --noEmit` propre sur `skinned-robot.ts` ; `git commit -m "feat(web): skinned-robot loader + mapping humeur/clip/visage + makeSkinnedRobot"`.

---

## Task 3: Câbler les délégués pays dans `globe-stage.tsx` (skinné + repli async)

**Files:**
- Modify: `web/src/components/globe/globe-stage.tsx`

**Interfaces:**
- Consumes: `makeSkinnedRobot`, `loadRobotGltf`, `DelegateHandle` (Task 1/2).

- [ ] **Step 1: Charger le glTF en amont** — au montage, `loadRobotGltf().then(g => { robotGltf = g; })` ; `robotGltf: GLTF | null`. En cas d'échec (`.catch`) → `robotGltf` reste null → repli.
- [ ] **Step 2: Fabrique de délégué pays** — dans `refresh`, remplacer `makeRobot({...})` (pour les pays du sommet **uniquement**) par : `robotGltf ? makeSkinnedRobot({..., gltf: robotGltf}) : makeRobot({...})`. La `Map robots` stocke des `DelegateHandle`. Si le glTF arrive après un premier `refresh` low-poly, un `refresh` ultérieur (changement d'état) recrée en skinné — acceptable ; sinon forcer un `refresh()` dans le `.then`.
- [ ] **Step 3: Boucle des délégués via le contrat** — remplacer `setRobotMood(r, mood)` → `r.setMood(mood)` et `animateRobot(r, t, reduced)` → `r.update(t, dt, reduced)` dans la boucle des délégués pays. `r.spinner.rotation.y`, `r.veil.visible`, `r.base.material.color` inchangés (contrat). ONU/Labo : garder `animateRobot(onu, …)` (toujours low-poly `makeRobot`), OU les passer aussi à `.update()` si `makeRobot` l'expose (rendu identique).
- [ ] **Step 4: Vérifier live (`/dev/globe`)** — délégués pays skinnés visibles, animés (Idle), face-caméra, morph V (2D⇄3D) OK, voile/vote/étiquettes OK ; `read_console_messages` sans erreur GL ; screenshot. Repli : renommer `RobotExpressive.glb` → délégués low-poly, pas de crash.
- [ ] **Step 5: Commit** — `git commit -m "feat(web): delegues pays skinnes cables dans globe-stage (+ repli low-poly)"`.

---

## Task 4: Humeurs animées + expressions faciales subtiles (live tuning)

**Files:**
- Modify: `web/src/components/globe/skinned-robot.ts`

- [ ] **Step 1: setMood → crossfade + visage** — `setMood` déclenche `mixer` crossfade (0,25 s) vers `actions[moodToClip(mood).clip]` et pose les `morphTargetInfluences` du visage (mesh tête) selon `face` (subtil : influence ≤ ~0,6). `update` fait `mixer.update(dt)` (skip si `reduced`, pose Idle statique).
- [ ] **Step 2: Votes one-shot** — exposer une hook (ex. `playEmote("ThumbsUp"|"No")`) appelée depuis globe-stage au changement de bulletin (pour→ThumbsUp, contre→No), retour au clip d'humeur après.
- [ ] **Step 3: Vérifier live** — pense/parle/suspendu/vote : clip + visage cohérents, subtils ; face-caméra ; pas de glissement au sol. Screenshot.
- [ ] **Step 4: Commit** — `git commit -m "feat(web): humeurs animees + expressions faciales subtiles (mixer + morphs)"`.

---

## Task 5: Perf + repli + porte finale

**Files:**
- Modify: `web/src/components/globe/globe-stage.tsx` (ajustements éventuels)

- [ ] **Step 1: Mesure perf** — `nvidia-smi` VRAM avant/après (sommet 7–12 pays skinnés), GPU %, FPS approx ; noter dans le commit. Si marge faible → doc « v1 sommet seulement » (déjà le cas).
- [ ] **Step 2: Repli vérifié** — glTF absent → low-poly silencieux (déjà en Task 3) ; `reduced-motion` → mixer en pause (pose Idle).
- [ ] **Step 3: Porte complète** — `cd web && npx tsc --noEmit && npx eslint src && npx vitest run` vert. Backend inchangé.
- [ ] **Step 4: Commit** — `git commit -m "feat(web): perf + repli robots skinnes (v1 sommet) + porte verte"`.

---

## Self-Review (couverture spec)

- Contrat `DelegateHandle` → Task 1 ✓ · `skinned-robot`/loader/mapping → Task 2 ✓ · câblage globe-stage + repli → Task 3 ✓ · humeurs/visage/votes → Task 4 ✓ · perf/repli/porte → Task 5 ✓.
- Types cohérents : `DelegateHandle` (T1) consommé par `makeSkinnedRobot` (T2) et globe-stage (T3) ; `moodToClip` (T2) utilisé en T4.
- Non-buts respectés : ONU/Labo/GM/Juge inchangés ; pas de LOD ; `Angry` au reveal prévu non câblé.

## Non-buts

ONU/Labo skinnés (itération suivante) ; nouveau rig ; robot pour drone/Juge ; LOD ; marche entre capitales.
