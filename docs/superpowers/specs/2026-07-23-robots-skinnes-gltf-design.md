# Robots skinnés glTF (sous-projet B) — Design

**Statut** : validé (retour user 2026-07-23) — périmètre réduit v1 + expressions faciales subtiles.

## But

Remplacer les **délégués des pays du sommet** (aujourd'hui un humanoïde low-poly construit à la
main dans `makeRobot`) par un **robot skinné animé** (glTF `RobotExpressive`, CC0), piloté par
l'humeur, **sans rien perdre** du gameplay (ancrage capitale, face-caméra, morph 2D⇄3D, voile de
brouillard, cadenas de suspension, teinte de vote, étiquettes projetées, épingles de suspicion).

## Périmètre (v1 — réduit)

- **DANS** : les délégués des pays du sommet (la `Map robots` de `globe-stage.tsx`, construite
  depuis `p.countries` à capitale connue).
- **HORS v1** (restent low-poly `makeRobot`, inchangés) : l'**ONU** (`onu`), les candidats du
  **Laboratoire** (`labA`/`labB`). Non-humanoïdes inchangés : **drone GM**, **orbe Juge**,
  satellite, cagnottes.
- **Expressions faciales** : oui, subtiles (morph targets `Angry`/`Sad`/`Surprised` du modèle).

## Asset

`web/public/models/RobotExpressive.glb` — CC0 (Tomás Laulhé / Don McCurdy), 453 Ko, déjà téléchargé
depuis le dépôt three.js. Clips nommés : `Idle, Walking, Running, Dance, Death, Sitting, Standing,
Jump, Yes, No, Wave, Punch, ThumbsUp`. Morph targets visage (mesh tête) : `Angry, Surprised, Sad`.

## Architecture

### Contrat unifié `DelegateHandle`
Une interface que **les deux** fabriques produisent, pour que `globe-stage` pilote les délégués
polymorphiquement :
```ts
type DelegateHandle = {
  slug: string;
  group: THREE.Group;      // ancré à la capitale (inchangé)
  spinner: THREE.Group;    // pivot face-caméra (rotation.y) — inchangé
  base: { material: THREE.MeshBasicMaterial }; // socle teinté (vote/hue) — inchangé
  veil: THREE.Object3D;    // voile fog (visible on/off) — inchangé
  mood: RobotMood;
  setMood(mood: RobotMood): void;             // remplace setRobotMood (discret)
  update(t: number, dt: number, reduced: boolean): void; // remplace animateRobot (continu)
};
```
- `makeRobot` (low-poly) est **adapté** pour renvoyer un `DelegateHandle` : `setMood`/`update`
  enveloppent la logique existante (`setRobotMood`/`animateRobot`), **rendu identique**. ONU/Labo
  passent par cette même interface (toujours low-poly, apparence inchangée).
- `makeSkinnedRobot` (nouveau, `skinned-robot.ts`) renvoie un `DelegateHandle` dont `update` fait
  avancer un `AnimationMixer` et `setMood` déclenche le crossfade de clip + l'expression faciale.

### `skinned-robot.ts`
- **Chargement paresseux, une fois** : `loadRobotGltf()` = promesse cachée (`GLTFLoader` sur
  `/models/RobotExpressive.glb`). Réutilisée par tous les délégués.
- **Clone par délégué** : `SkeletonUtils.clone(gltf.scene)` (squelette + morphs propres), un
  `AnimationMixer` par clone, actions préparées depuis `gltf.animations`.
- **Échelle & orientation** : le modèle est mis à l'échelle pour coller à la stature actuelle
  (référence `ROBOT_H`/proportions du low-poly) ; posé debout dans `spinner`, +Y = normale au sol
  via le `group` (réutilise l'ancrage `AnchorRegistry` existant — aucun changement d'ancrage).
- **Socle lumineux + drapeau** : on **conserve** un socle (`base`, teinte hue/vote) et le **voile**
  (`veil`) comme dans low-poly, plus un **badge drapeau** en billboard près du délégué ; une couleur
  d'accent du robot est **teintée par la hue** du pays (identité pays).

### Humeur → clip + visage
| mood | clip corps | visage (morph subtil) |
|------|-----------|------------------------|
| idle | `Idle` (boucle) | neutre |
| thinking | `Idle` (boucle) + légère inclinaison tête | neutre/concentré |
| speaking | boucle gestuelle (`Wave` ou `Yes`) | `Surprised` léger, animé |
| suspended | `Sitting` (maintenu) | `Sad` |
- Votes (transitoires, one-shot) : **pour → `ThumbsUp`**, **contre → `No`** (rejoués au changement
  de bulletin), puis retour au clip d'humeur.
- Trahison révélée (au reveal, si exposé par l'hôte plus tard) : `Angry` — hors v1, prévu.
- Crossfade `mixer` (0,25 s) entre clips ; `reduced-motion` → mixer en pause sur une pose Idle.

### Intégration `globe-stage.tsx`
- La boucle des délégués pays (≈ l.1062) appelle désormais `r.setMood(mood)` / `r.update(t, dt,
  reduced)` et lit `r.group`/`r.spinner`/`r.veil`/`r.base` (interface). ONU/Labo idem via l'interface.
- **Chargement asynchrone + repli (décidé)** : le glTF est chargé **en amont** (en parallèle des
  côtes/textures, promesse cachée). Un délégué pays n'est créé **qu'une fois le glTF prêt** → skinné,
  **sans « pop »** low-poly→skinné. Si le chargement **échoue** (ou WebGL/asset absent), bascule d'un
  drapeau `skinnedReady=false` et les délégués pays sont créés en **`makeRobot` low-poly** (repli
  silencieux). Le chargement est rapide (453 Ko, caché) : l'attente est imperceptible.
- Étiquettes, épingles de suspicion, glow orateur, morph : **inchangés** (ancrés sur `CAPITALS` +
  `ROBOT_H`, pas sur les internes du robot).

### Perf (RTX 2060S, VRAM partagée Ollama)
- Géométrie **partagée** entre clones (`SkeletonUtils.clone` ne duplique pas les buffers d'attributs)
  → un seul upload VRAM. ~5–12 mixers = coût CPU négligeable. `dt` déjà plafonné (0,05).
- Mesure `nvidia-smi` avant/après ; si marge faible, doc « garder ONU/Labo low-poly » (déjà le cas).

## Tests
- **vitest (pur, node)** : `mood→clip` (table de mapping), contrat `DelegateHandle` de `makeRobot`
  adapté (mêmes champs), `makeSkinnedRobot` expose `setMood`/`update`/`group`/`spinner`/`base`/`veil`
  (three tourne en node sans WebGL ; le `GLTFLoader` est mocké/évité — on teste la logique de mapping
  et l'adaptation d'interface, pas le décodage binaire).
- **Live** (`/dev/globe`) : délégués skinnés animés par humeur (pense/parle/suspendu/vote), visage
  subtil, face-caméra, morph 2D⇄3D, voile fog, teinte de vote, repli si glTF absent (renommer).
  `nvidia-smi` + `read_console_messages` sans erreur GL.

## Non-buts (v1)
ONU/Labo skinnés (itération suivante), nouveau rig, robot pour drone GM/Juge, LOD, expression
`Angry` au reveal (prévu, non câblé), animations de déplacement (marche entre capitales).

## Fichiers
- **Create** `web/src/components/globe/skinned-robot.ts` — loader caché + `makeSkinnedRobot`.
- **Create** `web/src/components/globe/skinned-robot.test.ts` — mapping + contrat.
- **Modify** `web/src/components/globe/robots.ts` — `DelegateHandle` + `makeRobot` adapté
  (`setMood`/`update` enveloppent la logique existante ; rendu identique).
- **Modify** `web/src/components/globe/globe-stage.tsx` — délégués pays via l'interface + skinné +
  repli ; câblage async du glTF.
- **Asset** `web/public/models/RobotExpressive.glb` (déjà présent).
