# Planète réaliste — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rendre le globe photo-réaliste (jour/nuit/spéculaire/nuages/atmosphère + lune + étoiles, textures NASA) sans rien perdre du gameplay, derrière un palier qualité.

**Architecture:** Un nouveau matériau Terre (ShaderMaterial jour/nuit/spéculaire) qui **préserve verbatim le morph vertex actuel** (sphère⇄plan par `uFlat`) et ne change QUE le fragment. Le peintre de texture actuel devient un peintre de **surcouche transparente** (bordures/liseré/cicatrices, zéro remplissage) composée dans le fragment. Nuages/atmosphère/lune = sphères séparées ; étoiles = fond de scène. Un réglage `planetQuality` bascule réaliste ⇄ globe peint actuel (repli léger).

**Tech Stack:** three.js (WebGLRenderer, GLSL inline), Next.js 16, TypeScript, `sharp` (downsample), vitest.

## Global Constraints

- Cible matérielle : **RTX 2060 Super 8 Go, VRAM partagée avec Ollama** → textures **4K jour / 2K nuit,nuages,lune,étoiles**, palier qualité, mipmaps + anisotropy `min(4, maxAniso)`.
- **Garder tout** : délégués + mood/veil/lock/votes/suspicion, drone GM, Juge + onde, satellite, funds, arcs, fly-to, morph 2D⇄3D, Laury, ONU, arène Labo, HUD, SSE, StageMap SVG (repli WebGL absent).
- **Signal pays SANS remplissage** : liseré + halo dont la COULEUR encode l'indice U (échelle `uTint` existante rouge→vert). Jamais d'aplat de pays.
- **Morph vertex préservé au pixel** : la logique `mix(position, flatPos, uFlat)` avec `FLAT_W`/`FLAT_H` est reprise verbatim ; on ne touche qu'au fragment.
- Conventions repo : LF, commits conventionnels, trailer `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`. Front dans `web/` : `npx tsc --noEmit`, `npx eslint`, `npx vitest run`. `web/AGENTS.md` : lire les docs Next bundlées avant tout code Next.
- Source 8K dans `nasa_texture/` (racine) : `8k_earth_daymap.jpg`, `8k_earth_nightmap.jpg`, `8k_earth_clouds.jpg`, `8k_moon.jpg`, `8k_stars.jpg` — **hors build** (gitignore).

---

## File Structure

- **Create** `scripts/downsample-textures.mjs` — script Node one-off (sharp) : `nasa_texture/*` → `web/public/textures/*` en 4K/2K.
- **Create** `web/public/textures/{earth-day,earth-night,earth-clouds,moon,stars}.jpg` — artefacts générés, committés.
- **Modify** `web/src/lib/settings.ts` — type `PlanetQuality` + champ `planetQuality` (défaut `realistic`).
- **Modify** `web/src/components/settings-provider.tsx` — persistance + setter `setPlanetQuality`.
- **Modify** `web/src/components/globe/texture.ts` — nouveau `createOverlayPainter` (surcouche transparente, bordures-only).
- **Create** `web/src/components/globe/earth-material.ts` — `createEarthMaterial({day,night,overlay,flatW,flatH})` → `{ material, setSun, setFlat }`.
- **Create** `web/src/components/globe/sky.ts` — `makeClouds(tex)`, `makeAtmosphere()`, `makeMoon(tex)`, `makeStarfield(tex)`.
- **Modify** `web/src/components/globe/globe-stage.tsx` — charge les textures, construit la base réaliste + ciel quand `quality==="realistic"`, sinon le globe peint actuel ; anime le soleil ; compose la surcouche ; repli si textures absentes.
- **Modify** `web/src/app/reglages/page.tsx` — sélecteur qualité planète.
- **Modify** `web/src/app/dev/globe/page.tsx` — toggle qualité.
- **Test** `web/src/components/globe/earth-material.test.ts`, `web/src/components/globe/texture.test.ts` (overlay), `web/src/lib/settings.test.ts` (ou existant).

---

## Task 1: Pipeline de textures (spec A1)

**Files:**
- Create: `scripts/downsample-textures.mjs`
- Create (generated): `web/public/textures/{earth-day,earth-night,earth-clouds,moon,stars}.jpg`
- Modify: `.gitignore`

**Interfaces:**
- Produces: 5 fichiers servis à `/textures/earth-day.jpg` etc. (day 4096×2048, autres 2048×1024).

- [ ] **Step 1: Écrire le script sharp**

```js
// scripts/downsample-textures.mjs
import sharp from "sharp";
import { mkdir } from "node:fs/promises";
import { resolve } from "node:path";

const SRC = resolve("nasa_texture");
const OUT = resolve("web/public/textures");
const JOBS = [
  ["8k_earth_daymap.jpg", "earth-day.jpg", 4096],
  ["8k_earth_nightmap.jpg", "earth-night.jpg", 2048],
  ["8k_earth_clouds.jpg", "earth-clouds.jpg", 2048],
  ["8k_moon.jpg", "moon.jpg", 2048],
  ["8k_stars.jpg", "stars.jpg", 2048],
];
await mkdir(OUT, { recursive: true });
for (const [src, out, w] of JOBS) {
  await sharp(resolve(SRC, src))
    .resize({ width: w, height: w / 2, fit: "fill" })
    .jpeg({ quality: 86, mozjpeg: true })
    .toFile(resolve(OUT, out));
  console.log(`✓ ${out} (${w}×${w / 2})`);
}
```

- [ ] **Step 2: Vérifier que sharp est disponible**

Run: `cd web && node -e "require('sharp');console.log('sharp ok')"`
Expected: `sharp ok`. Si absent : `npm --prefix web i -D sharp` (sharp est déjà tiré par Next en général).

- [ ] **Step 3: Lancer le script**

Run (depuis la racine repo) : `node scripts/downsample-textures.mjs`
Expected : 5 lignes `✓ …`. 

- [ ] **Step 4: Vérifier les fichiers + dimensions**

Run: `file web/public/textures/*.jpg`
Expected : `earth-day.jpg … 4096x2048`, les 4 autres `2048x1024`. Poids total ~5–8 Mo.

- [ ] **Step 5: Ignorer la source 8K**

Ajouter à `.gitignore` (racine) :
```
/nasa_texture/
```

- [ ] **Step 6: Commit**

```bash
git add scripts/downsample-textures.mjs web/public/textures/*.jpg .gitignore
git commit -m "feat(web): pipeline + textures NASA sous-echantillonnees (4K/2K)"
```

---

## Task 2: Réglage `planetQuality` (spec A7)

**Files:**
- Modify: `web/src/lib/settings.ts`
- Modify: `web/src/components/settings-provider.tsx`
- Test: `web/src/lib/settings.test.ts` (créer si absent)

**Interfaces:**
- Produces: `type PlanetQuality = "realistic" | "light"` ; `settings.planetQuality` ; `setPlanetQuality(q)`. Défaut `"realistic"`.

- [ ] **Step 1: Test — défaut réaliste + parse**

D'abord lire `web/src/lib/settings.ts` pour le patron exact (type `Settings`, defaults, parse/persist). Puis test :
```ts
// settings.test.ts (adapter au patron existant : DEFAULT_SETTINGS / parseSettings)
import { DEFAULT_SETTINGS } from "./settings";
it("planetQuality par défaut = realistic", () => {
  expect(DEFAULT_SETTINGS.planetQuality).toBe("realistic");
});
```

- [ ] **Step 2: Run — échoue**

Run: `cd web && npx vitest run settings`
Expected: FAIL (`planetQuality` undefined).

- [ ] **Step 3: Implémenter**

Dans `settings.ts` : ajouter `export type PlanetQuality = "realistic" | "light";`, le champ `planetQuality: PlanetQuality` au type `Settings` et à `DEFAULT_SETTINGS` (= `"realistic"`), et le parser/persister dans la (dé)sérialisation existante (suivre le patron de `stageView`). Dans `settings-provider.tsx` : exposer `setPlanetQuality` (miroir de `setStageView`).

- [ ] **Step 4: Run — passe**

Run: `cd web && npx vitest run settings`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/src/lib/settings.ts web/src/components/settings-provider.tsx web/src/lib/settings.test.ts
git commit -m "feat(web): reglage planetQuality (realistic|light, defaut realistic)"
```

---

## Task 3: Peintre de surcouche transparente (spec A5)

**Files:**
- Modify: `web/src/components/globe/texture.ts`
- Test: `web/src/components/globe/texture.test.ts`

**Interfaces:**
- Consumes: la géométrie pays + `uTint` (échelle U) déjà dans `texture.ts`/`stage.ts`.
- Produces: `createOverlayPainter(ctx, features)` → `{ paint(countries, speaking, scars, lisere) }` qui peint sur un canvas **transparent** : bordures teintées U + liseré + cicatrices + voile brouillard, **aucun remplissage**. Même signature `paint(...)` que `createGlobePainter` pour un swap direct.

- [ ] **Step 1: Lire l'existant**

Lire `web/src/components/globe/texture.ts` (`createGlobePainter`, comment il remplit + trace bordures/liseré/cicatrices) et `stage.ts` `uTint`. Identifier la passe « remplissage » (à retirer) vs « bordure/liseré/cicatrices » (à garder).

- [ ] **Step 2: Test — surcouche transparente + bordure teintée**

```ts
// texture.test.ts (jsdom + canvas ; suivre le patron des tests globe existants)
import { createOverlayPainter } from "./texture";
it("surcouche : intérieur transparent, bordure teintée", () => {
  const cvs = document.createElement("canvas"); cvs.width = 64; cvs.height = 32;
  const ctx = cvs.getContext("2d")!;
  const painter = createOverlayPainter(ctx, /* features de test minimal */ MOCK_FEATURES);
  painter.paint([{ slug: "usa", u: 0.2 }], null, [], undefined);
  const img = ctx.getImageData(0, 0, 64, 32).data;
  // au moins un pixel totalement transparent (intérieur non rempli)
  let hasTransparent = false;
  for (let i = 3; i < img.length; i += 4) if (img[i] === 0) hasTransparent = true;
  expect(hasTransparent).toBe(true);
});
```
(Si `jsdom` canvas 2D est trop limité pour `getImageData`, tester à la place que `createOverlayPainter` n'appelle jamais `ctx.fill()` de remplissage pays — via un `ctx` espionné (vi.fn) — et appelle bien `ctx.stroke()` pour les bordures. Choisir la variante qui tourne dans l'env vitest du repo.)

- [ ] **Step 3: Run — échoue**

Run: `cd web && npx vitest run texture`
Expected: FAIL (`createOverlayPainter` non défini).

- [ ] **Step 4: Implémenter**

Ajouter `createOverlayPainter` à `texture.ts` : cloner `createGlobePainter` mais (a) démarrer par `ctx.clearRect` (canvas transparent), (b) **supprimer la passe de remplissage pays**, (c) garder/renforcer la passe bordure : `strokeStyle = uTint(u)`, `lineWidth` doux + `shadowBlur` léger pour le glow, double trait (halo sombre dessous + trait teinté dessus) pour la lisibilité sur terre claire ET océan sombre, (d) garder cicatrices (alpha) + voile brouillard.

- [ ] **Step 5: Run — passe**

Run: `cd web && npx vitest run texture`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add web/src/components/globe/texture.ts web/src/components/globe/texture.test.ts
git commit -m "feat(web): createOverlayPainter (surcouche transparente, bordures teintees U, zero remplissage)"
```

---

## Task 4: Matériau Terre réaliste (spec A2)

**Files:**
- Create: `web/src/components/globe/earth-material.ts`
- Test: `web/src/components/globe/earth-material.test.ts`

**Interfaces:**
- Consumes: `THREE.Texture` day/night/overlay ; `flatW`, `flatH` (constantes de `globe-stage`).
- Produces:
  `createEarthMaterial(opts: { day: THREE.Texture; night: THREE.Texture; overlay: THREE.Texture; flatW: number; flatH: number }) → { material: THREE.ShaderMaterial; setSun(dir: THREE.Vector3): void; setFlat(k: number): void }`.
  Le `material` échantillonne day/night (mélange par soleil), spéculaire océan, compose `overlay` par-dessus, et **préserve le morph** `mix(position, flatPos, uFlat)`.

- [ ] **Step 1: Test — uniforms + poignées**

```ts
import * as THREE from "three";
import { createEarthMaterial } from "./earth-material";
it("expose les uniforms attendus et les setters", () => {
  const t = () => new THREE.Texture();
  const m = createEarthMaterial({ day: t(), night: t(), overlay: t(), flatW: 6, flatH: 3 });
  expect(m.material.uniforms.uDay).toBeDefined();
  expect(m.material.uniforms.uNight).toBeDefined();
  expect(m.material.uniforms.uOverlay).toBeDefined();
  expect(m.material.uniforms.uSun).toBeDefined();
  expect(m.material.uniforms.uFlat).toBeDefined();
  m.setFlat(1); expect(m.material.uniforms.uFlat.value).toBe(1);
  m.setSun(new THREE.Vector3(1, 0, 0));
  expect(m.material.uniforms.uSun.value.x).toBe(1);
});
```

- [ ] **Step 2: Run — échoue**

Run: `cd web && npx vitest run earth-material`
Expected: FAIL.

- [ ] **Step 3: Implémenter le matériau (GLSL réel, morph verbatim)**

```ts
// earth-material.ts
import * as THREE from "three";

export type EarthMaterial = {
  material: THREE.ShaderMaterial;
  setSun: (dir: THREE.Vector3) => void;
  setFlat: (k: number) => void;
};

export function createEarthMaterial(opts: {
  day: THREE.Texture; night: THREE.Texture; overlay: THREE.Texture;
  flatW: number; flatH: number;
}): EarthMaterial {
  const { day, night, overlay, flatW, flatH } = opts;
  day.colorSpace = THREE.SRGBColorSpace;
  night.colorSpace = THREE.SRGBColorSpace;
  const material = new THREE.ShaderMaterial({
    uniforms: {
      uDay: { value: day }, uNight: { value: night }, uOverlay: { value: overlay },
      uSun: { value: new THREE.Vector3(1, 0.15, 0.4).normalize() },
      uFlat: { value: 0 },
    },
    vertexShader: `
      uniform float uFlat;
      varying vec2 vUv; varying vec3 vNormalW;
      void main(){
        vUv = uv;
        vNormalW = normalize(mat3(modelMatrix) * normalize(position)); // normale sphere stable
        vec3 flatPos = vec3((uv.x-0.5)*${flatW.toFixed(6)}, (uv.y-0.5)*${flatH.toFixed(6)}, 0.0);
        vec3 p = mix(position, flatPos, uFlat);           // MORPH VERBATIM
        gl_Position = projectionMatrix * modelViewMatrix * vec4(p, 1.0);
      }`,
    fragmentShader: `
      uniform sampler2D uDay; uniform sampler2D uNight; uniform sampler2D uOverlay;
      uniform vec3 uSun; uniform float uFlat;
      varying vec2 vUv; varying vec3 vNormalW;
      void main(){
        vec3 day = texture2D(uDay, vUv).rgb;
        vec3 night = texture2D(uNight, vUv).rgb;
        float sd = dot(normalize(vNormalW), normalize(uSun));
        float dayMix = smoothstep(-0.15, 0.25, sd);
        dayMix = mix(dayMix, 1.0, uFlat);                 // carte = plein jour
        vec3 col = mix(night * 0.9, day, dayMix);
        float lum = dot(day, vec3(0.299,0.587,0.114));
        float ocean = smoothstep(0.28, 0.12, lum) * step(day.r, day.b);
        vec3 h = normalize(uSun + vec3(0.0,0.0,1.0));
        float spec = pow(max(dot(normalize(vNormalW), h), 0.0), 60.0) * ocean * dayMix * (1.0 - uFlat);
        col += vec3(0.7,0.8,1.0) * spec * 0.6;
        vec4 ov = texture2D(uOverlay, vUv);
        col = mix(col, ov.rgb, ov.a);                     // surcouche gameplay
        gl_FragColor = vec4(col, 1.0);
      }`,
  });
  return {
    material,
    setSun: (dir) => (material.uniforms.uSun.value as THREE.Vector3).copy(dir).normalize(),
    setFlat: (k) => (material.uniforms.uFlat.value = k),
  };
}
```

- [ ] **Step 4: Run — passe**

Run: `cd web && npx vitest run earth-material`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/src/components/globe/earth-material.ts web/src/components/globe/earth-material.test.ts
git commit -m "feat(web): earth-material (jour/nuit/speculaire, morph preserve)"
```

---

## Task 5: Ciel — nuages, atmosphère, lune, étoiles (spec A3/A4/A6)

**Files:**
- Create: `web/src/components/globe/sky.ts`

**Interfaces:**
- Produces:
  - `makeClouds(tex: THREE.Texture): THREE.Mesh` — sphère r=1.003, alpha=luminance, transparent, depthWrite=false.
  - `makeAtmosphere(): { mesh: THREE.Mesh; setSun(dir): void; setFlat(k): void }` — fresnel BackSide, couleur jour-bleu→crépuscule-ambre selon soleil, fondu par uFlat.
  - `makeMoon(tex: THREE.Texture): THREE.Mesh` — sphère texturée éclairée.
  - `makeStarfield(tex: THREE.Texture): THREE.Mesh` — grande sphère BackSide r≈50 (ou usage `scene.background`).

- [ ] **Step 1: Implémenter `sky.ts`**

```ts
import * as THREE from "three";

export function makeClouds(tex: THREE.Texture): THREE.Mesh {
  tex.colorSpace = THREE.SRGBColorSpace;
  const m = new THREE.ShaderMaterial({
    transparent: true, depthWrite: false,
    uniforms: { uMap: { value: tex }, uFlat: { value: 0 } },
    vertexShader: `varying vec2 vUv; void main(){ vUv=uv;
      gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}`,
    fragmentShader: `uniform sampler2D uMap; uniform float uFlat; varying vec2 vUv;
      void main(){ vec3 c=texture2D(uMap,vUv).rgb; float a=dot(c,vec3(0.333));
        gl_FragColor=vec4(vec3(1.0), a*0.9*(1.0-uFlat)); }`,
  });
  return new THREE.Mesh(new THREE.SphereGeometry(1.003, 96, 64), m);
}

export function makeAtmosphere(): { mesh: THREE.Mesh; setSun: (d: THREE.Vector3) => void; setFlat: (k: number) => void } {
  const mat = new THREE.ShaderMaterial({
    side: THREE.BackSide, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false,
    uniforms: { uSun: { value: new THREE.Vector3(1, 0.15, 0.4).normalize() }, uFlat: { value: 0 } },
    vertexShader: `varying vec3 vN; varying vec3 vW; void main(){
      vN=normalize(mat3(modelMatrix)*normal); vW=normalize(mat3(modelMatrix)*position);
      gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}`,
    fragmentShader: `varying vec3 vN; varying vec3 vW; uniform vec3 uSun; uniform float uFlat;
      void main(){
        float rim=pow(0.72-dot(vN,vec3(0.,0.,1.)),3.2);
        float sd=clamp(dot(normalize(vW),normalize(uSun))*0.5+0.5,0.0,1.0);
        vec3 col=mix(vec3(0.05,0.12,0.28), mix(vec3(0.9,0.5,0.2), vec3(0.36,0.65,1.0), sd), sd);
        gl_FragColor=vec4(col*rim*1.3*(1.0-uFlat),1.0);
      }`,
  });
  const mesh = new THREE.Mesh(new THREE.SphereGeometry(1.055, 72, 48), mat);
  return {
    mesh,
    setSun: (d) => (mat.uniforms.uSun.value as THREE.Vector3).copy(d).normalize(),
    setFlat: (k) => (mat.uniforms.uFlat.value = k),
  };
}

export function makeMoon(tex: THREE.Texture): THREE.Mesh {
  tex.colorSpace = THREE.SRGBColorSpace;
  const mesh = new THREE.Mesh(
    new THREE.SphereGeometry(0.34, 48, 32),
    new THREE.MeshStandardMaterial({ map: tex, roughness: 1, metalness: 0 }),
  );
  mesh.position.set(-4.6, 2.4, -6.5);
  return mesh;
}

export function makeStarfield(tex: THREE.Texture): THREE.Mesh {
  tex.colorSpace = THREE.SRGBColorSpace;
  return new THREE.Mesh(
    new THREE.SphereGeometry(50, 48, 32),
    new THREE.MeshBasicMaterial({ map: tex, side: THREE.BackSide, depthWrite: false }),
  );
}
```

- [ ] **Step 2: Vérifier compilation**

Run: `cd web && npx tsc --noEmit`
Expected: pas d'erreur sur `sky.ts`.

- [ ] **Step 3: Commit**

```bash
git add web/src/components/globe/sky.ts
git commit -m "feat(web): sky.ts (nuages, atmosphere soleil, lune, starfield)"
```

---

## Task 6: Câbler le palier réaliste dans `globe-stage.tsx` (spec A2/A3/A4/A6/A7)

**Files:**
- Modify: `web/src/components/globe/globe-stage.tsx`

**Interfaces:**
- Consumes: `createEarthMaterial`, `makeClouds/Atmosphere/Moon/Starfield`, `createOverlayPainter`, `settings.planetQuality` (via une prop `quality` passée par l'hôte, comme `view`).

- [ ] **Step 1: Ajouter la prop qualité**

Dans `GlobeStageProps` : `quality?: "realistic" | "light";` (défaut `"light"` pour zéro changement tant que non câblé). L'hôte (GlobeTheatre/StageShell/dev) la dérive de `settings.planetQuality`.

- [ ] **Step 2: Charger les textures (paresseux, repli)**

Au montage, si `propsRef.current.quality === "realistic"`, charger via `THREE.TextureLoader` `/textures/earth-day.jpg`, `earth-night.jpg`, `earth-clouds.jpg`, `moon.jpg`, `stars.jpg` (anisotropy `min(4, renderer.capabilities.getMaxAnisotropy())`). En cas d'échec d'une texture (`onError`) → basculer `realistic=false` (repli peint).

- [ ] **Step 3: Brancher la base selon la qualité**

Remplacer la construction actuelle de `globeMat`/`atmoMat`/étoiles par un aiguillage :
- `light` : code ACTUEL inchangé (globeMat peint + atmoMat + Points étoiles).
- `realistic` : `texture` (canvas) = surcouche via `createOverlayPainter` (au lieu de `createGlobePainter`) ; `globe.material` = `createEarthMaterial({day,night,overlay:texture,flatW:FLAT_W,flatH:FLAT_H}).material` ; ajouter `makeClouds`, `makeAtmosphere`, `makeMoon`, `makeStarfield` ; retirer les 1300 Points ; retirer l'HemisphereLight (garder une directionnelle « soleil » + ambient faible). Conserver `painter` = overlay (les `refresh()`/`paint` repeignent la surcouche).

- [ ] **Step 4: Animer le soleil + morph dans la boucle**

Dans `frame` : direction soleil lente (day-cycle), `earth.setSun(dir)` + `atmo.setSun(dir)` (figée si `reduced`) ; `earth.setFlat(morphK)`, `atmo.setFlat(morphK)`, clouds `uFlat=morphK` ; rotation lente des nuages (`clouds.rotation.y += dt*0.006`, coupée si `reduced`) ; anchors nuages/atmo/lune non requis (sphères centrées) ; starfield fixe.

- [ ] **Step 5: Vérifier live (les deux paliers)**

`preview_start {url}` → `/dev/globe` (Task 7 ajoute le toggle) ; sinon forcer `quality="realistic"` temporairement. Vérifier : Terre jour/nuit + spéculaire océan + nuages + atmosphère + lune + étoiles ; **morph V (2D⇄3D)** OK ; bordures pays teintées lisibles ; délégués/Laury/ONU/arène toujours là. `read_console_messages`/`preview_logs` sans erreur GL. Capturer une image (redimensionner la fenêtre si le screenshot timeout — cf. gotcha session).

- [ ] **Step 6: Commit**

```bash
git add web/src/components/globe/globe-stage.tsx
git commit -m "feat(web): palier realiste cable dans globe-stage (terre+ciel+overlay, morph preserve)"
```

---

## Task 7: Sélecteurs de qualité + repli (spec A7)

**Files:**
- Modify: `web/src/app/reglages/page.tsx`
- Modify: `web/src/app/dev/globe/page.tsx`
- Modify: hôtes qui montent `GlobeStage` (`stage-shell.tsx`, `theatre/globe-theatre.tsx`) pour passer `quality={settings.planetQuality}`.

- [ ] **Step 1: Passer la qualité depuis les hôtes**

`stage-shell.tsx` et `globe-theatre.tsx` : `quality={settings.planetQuality}` (lu via `useSettings`). Dev : état local.

- [ ] **Step 2: Réglage dans `/reglages`**

Ajouter un sélecteur « Qualité de la planète : Réaliste / Légère » (patron des réglages existants, `setPlanetQuality`).

- [ ] **Step 3: Toggle dev `/dev/globe`**

Bouton « 🌍 réaliste » qui bascule `quality`.

- [ ] **Step 4: Vérifier live les deux paliers + le repli**

Basculer Réaliste⇄Légère : le globe change sans casser le gameplay. Simuler une texture absente (renommer temporairement) → repli léger silencieux.

- [ ] **Step 5: Gate + commit**

Run: `cd web && npx tsc --noEmit && npx eslint src && npx vitest run`
Expected: vert.
```bash
git add web/src/app/reglages/page.tsx web/src/app/dev/globe/page.tsx web/src/components/shell/stage-shell.tsx web/src/components/theatre/globe-theatre.tsx
git commit -m "feat(web): selecteurs qualite planete (reglages + dev) + repli textures"
```

---

## Task 8: Polissage + perf (spec increment 7)

**Files:**
- Modify: `web/src/components/globe/globe-stage.tsx`

- [ ] **Step 1: Tonemapping + exposition**

`renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure ≈ 1.05;` (uniquement palier réaliste). Vérifier que la surcouche/HUD restent lisibles.

- [ ] **Step 2: Mesurer la perf sur la 2060S**

`nvidia-smi` VRAM avant/après passage réaliste ; FPS approx ; tokens/s Ollama pendant un round réaliste. Noter dans le commit si marge faible → recommander « légère » par défaut sur machines faibles.

- [ ] **Step 3: Gate complet**

Run: `cd web && npx tsc --noEmit && npx eslint src && npx vitest run` ; backend inchangé (pas de pytest requis).
Expected: vert.

- [ ] **Step 4: Commit**

```bash
git add web/src/components/globe/globe-stage.tsx
git commit -m "feat(web): polish rendu realiste (ACES tonemapping) + mesure perf 2060S"
```

---

## Self-Review (couverture spec)

- A1 textures → Task 1 ✓ · A2 matériau → Task 4 + Task 6 ✓ · A3 nuages → Task 5 + Task 6 ✓ · A4 atmosphère → Task 5 + Task 6 ✓ · A5 surcouche halo-only → Task 3 + Task 6 ✓ · A6 lune/étoiles → Task 5 + Task 6 ✓ · A7 palier → Task 2 + Task 6 + Task 7 ✓ · A8 invariants → vérifs live Task 6/7 ✓ · increment 7 polish → Task 8 ✓.
- Types cohérents : `PlanetQuality` (T2) = prop `quality` (T6/T7) ; `createOverlayPainter` (T3) consommé en T6 ; `createEarthMaterial`/`sky` (T4/T5) consommés en T6.
- Pas de placeholder : GLSL et TS réels fournis ; les points « lire l'existant » (T2 settings, T3 painter) sont des repérages de patron, pas des trous — le code à écrire est spécifié.

## Non-buts

Robots skinnés glTF (sous-projet B, spec séparé, bloqué asset) ; relief/bump ; migration WebGPU/TSL.
