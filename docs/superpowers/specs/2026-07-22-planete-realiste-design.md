# Planète réaliste — refonte du rendu du globe (design)

> Cible user : « j'ai trouvé le design de la planète qu'il faut » (référence : Three.js
> Journey / `webgpu_tsl_earth`, textures NASA 8K fournies). **Garde tout** (toutes les
> mécaniques et features actuelles), **rends la planète photo‑réaliste et impressionnante.**

## Décomposition

Deux sous‑projets indépendants, chacun son cycle spec → plan → implémentation :

- **A — Réalisme de la planète** (CE spec). Textures en main → réalisable maintenant.
- **B — Robots skinnés glTF** (spec séparé, plus tard). **Bloqué sur un asset** : un modèle
  de robot riggé/animé glTF (l'exemple three.js `webgl_animation_skinning_additive_blending`
  utilise `Michelle.glb`, un humain). L'user fournira un robot glTF, ou on validera un modèle
  libre (Mixamo/Sketchfab) avant. Remplacer les délégués primitifs + Laury + ONU + candidats
  Labo par des modèles skinnés = gros rewire (morph, mood, veil, lock, votes, suspicion,
  anchoring) → hors de ce spec.

## Décisions (validées avec l'user)

1. **Résolution** : sous‑échantillonner le 8K → **4K jour**, **2K nuit/nuages/lune/étoiles**.
   Un palier **qualité** (réaliste par défaut ; globe peint actuel = repli « perf légère »).
2. **Signal pays « par halos »** : la planète reste photo‑réaliste **sans remplissage** ; les
   pays du sommet sont signalés par **liseré + halo dont la couleur encode l'indice U**
   (rouge→vert). Plus de fill couleur.
3. **Robots** = sous‑projet B (skinnés glTF), séparé.

## État actuel (ce qu'on garde et ce qu'on remplace)

- `web/src/components/globe/globe-stage.tsx` : monte la scène three. `globeMat` =
  `ShaderMaterial` qui échantillonne la **texture canvas peinte** (`createGlobePainter`), morphée
  sphère⇄plan par l'uniform `uFlat`. `atmoMat` = atmosphère fresnel simple. Anneaux, ~1300
  étoiles particules, HemisphereLight + 2 directionnelles, délégués (`makeRobot`), drone GM,
  Juge, satellite, arcs, fly‑to, Laury, ONU, arène Labo. **On garde tout ça** ; on remplace la
  **base** (matériau + texture) et le **décor** (étoiles/lune).
- `web/src/components/globe/texture.ts` : `createGlobePainter` peint les pays (**remplissage U**),
  cicatrices, liseré, brouillard sur un canvas `TEX_W×TEX_H`. → **reconverti** en peintre de
  **surcouche transparente** (bordures/liseré/cicatrices/voile seulement, **zéro remplissage**).
- `web/src/components/globe/morph.ts` : shader morph + `AnchorRegistry` + `mixTop`. **Inchangé**
  (le morph des acteurs). Le morph de la BASE (globe) est dans le shader `globeMat` → à préserver.
- `web/src/components/settings-provider.tsx` (+ `lib/settings.ts`) : réglages. → ajout
  `planetQuality: "realistic" | "light"` (défaut `realistic`), persistant.

## Architecture cible

### A1. Pipeline de textures
- Script one‑off Node (`sharp` — déjà dépendance Next ; repli ImageMagick) sous‑échantillonne
  `nasa_texture/*.jpg` → `web/public/textures/` :
  - `earth-day.jpg` 4096×2048 · `earth-night.jpg` 2048×1024 · `earth-clouds.jpg` 2048×1024 ·
    `moon.jpg` 2048×1024 · `stars.jpg` 2048×1024.
- `nasa_texture/` reste **hors build** (source ; ajouté à `.gitignore` si besoin). Les 5 JPEG 4K/2K
  (~5–8 Mo au total) sont committés sous `web/public/textures/`.
- Chargement via `THREE.TextureLoader` ; `colorSpace = SRGBColorSpace` pour day/night ; mipmaps +
  anisotropy (min(4, maxAniso)). Chargement paresseux + repli : si une texture échoue → palier
  « light ».

### A2. Matériau globe réaliste (`realistic`)
Nouveau `ShaderMaterial` (ou `MeshStandardMaterial` custom via `onBeforeCompile`) — **choix :
ShaderMaterial dédié**, pour garder le contrôle total du morph existant. Uniforms :
- `uDay`, `uNight`, `uOverlay` (surcouche transparente game), `uSun` (dir), `uFlat` (morph),
  `uTime`. (Les nuages ne sont PAS échantillonnés ici : sphère séparée, cf. A3.)
- Fragment :
  - `sunDot = dot(normalWorld, uSun)` → mélange **jour** (albédo) côté éclairé, **nuit** (city
    lights, additif) côté sombre, transition douce au terminateur.
  - **spéculaire océan** : masque océan dérivé du day (faible luminance + dominante bleue) →
    reflet spéculaire (Blinn‑Phong léger) uniquement sur l'eau.
  - **surcouche game** `uOverlay` : composée par‑dessus (bordures/liseré/cicatrices/voile), sans
    remplissage — c'est le seul canal « gameplay » sur la base.
  - **morph** `uFlat` : identique au globe actuel (les positions/uv morphées sphère⇄plan). La
    logique de morph des vertices est reprise **verbatim** du shader actuel.
- Éclairage : une **lumière directionnelle « soleil »** (dir = `uSun`) + un ambient faible. On
  peut retirer/atténuer l'HemisphereLight (elle lavait la nuit). Le night‑map fait la lumière
  côté sombre.

### A3. Couche nuages (sphère séparée)
- Sphère `radius = 1.003`, `MeshBasicMaterial`(map=clouds, alpha depuis luminance, transparent,
  depthWrite=false), rotation lente indépendante. Morphée avec le globe (masquée en mode plan
  `uFlat=1`, ou aplatie). Coupée en `prefers-reduced-motion` (statique) et en palier « light ».

### A4. Atmosphère fresnel (améliorée)
- Sphère `radius ≈ 1.015`, `BackSide`, fragment fresnel : couleur = mélange
  `atmosphereDay` (bleu) → `atmosphereTwilight` (ambre) selon `sunDot` au limbe, fondu vers le
  noir côté nuit. Additif, depthWrite=false. Remplace `atmoMat` actuel.

### A5. Signal pays (surcouche, halo‑only)
- `createGlobePainter` → **`createOverlayPainter`** : peint sur canvas **transparent** :
  - liseré/bordure de chaque pays du sommet, **couleur = teinte U** (échelle rouge→vert
    existante `uTint`) ; épaisseur douce + léger glow.
  - cicatrices (inchangé, alpha), voile brouillard (inchangé).
  - **aucun remplissage** de pays.
- Composé dans `globeMat` (`uOverlay`) par‑dessus la Terre. Les halos sprites orateur/incarné
  existants restent. Résultat : on lit « ce pays vire au rouge/vert » via son **contour** + halo,
  pas via un aplat.
- ⚠️ Contrainte : le contour doit rester lisible sur le blue‑marble (terre claire ET océan
  sombre) → glow + double trait (halo sombre + trait teinté) si nécessaire.

### A6. Lune & étoiles
- **Étoiles** : `scene.background` = texture `stars` équirect (ou grande sphère `BackSide`
  radius ~50). Retire les ~1300 particules actuelles (ou les garde en sus, discret). Le décor CSS
  `space-backdrop` (lune + shooting‑stars) est **masqué sur les pages‑globe** (déjà le cas via le
  layout ? sinon on le coupe quand le globe réaliste est monté).
- **Lune** : sphère texturée (`moon`), éclairée par le même soleil, placée loin (ex. derrière,
  échelle discrète). Optionnelle en palier « light » (coupée).

### A7. Palier qualité
- `settings.planetQuality` (`realistic` défaut · `light`). `GlobeStage` lit `lowPerf`‑like :
  - `realistic` : matériau A2 + nuages A3 + atmosphère A4 + lune/étoiles A6 + surcouche A5.
  - `light` : globe **peint actuel** (fills + liseré, pas de textures NASA) — code conservé tel
    quel, sélectionné par le réglage. Pas de nuages/lune/night‑map.
  - WebGL absent → StageMap SVG (inchangé).
- Réglage exposé dans `/reglages` (et un bouton dev `/dev/globe`). `prefers-reduced-motion` fige
  nuages/rotations mais garde le réalisme.

### A8. Ce qui est préservé (invariants)
Délégués + mood/veil/lock/votes/suspicion, drone GM, Juge + onde verdict, satellite + scan,
billets marché (funds), arcs, fly‑to, morph 2D⇄3D, Laury 3D, ONU Genève, arène Labo, HUD, SSE.
Tous sont des **acteurs/surcouches** au‑dessus de la base → indépendants du matériau. Test de
non‑régression : la scène complète rend en `realistic` ET `light`.

## Découpage d'implémentation (increments)

1. **Textures** : script de sous‑échantillonnage → `web/public/textures/` (+ `.gitignore`
   `nasa_texture/`). Vérifier les 5 fichiers servis.
2. **Réglage** : `planetQuality` dans settings + `/reglages` + `/dev/globe` (toggle). Défaut
   `realistic` ; par défaut la scène = globe peint (aucun changement visuel encore).
3. **Base réaliste A2** (sans nuages/atmo) : charger day/night, shader jour/nuit + spéculaire,
   morph préservé, derrière un flag `realistic`. Surcouche A5 (overlay painter) en parallèle.
4. **Atmosphère A4** + **nuages A3**.
5. **Lune & étoiles A6** + coupe du décor CSS sur pages‑globe.
6. **Palier A7** câblé bout‑en‑bout + repli textures manquantes → light.
7. Polissage (tonemapping `ACESFilmic`, exposition, anisotropy), mesure perf (tokens/s Ollama +
   FPS) sur la 2060S.

## Tests

- **Vitest (pur)** : sélection du matériau par `planetQuality` ; `createOverlayPainter` peint
  transparent (aucun pixel de remplissage opaque hors bordures) ; chemins de textures ; repli
  light si texture absente.
- **Trois `globe/*.ts` pur** restent verts (camera/morph/picking/robots/texture).
- **Visuel** : `/dev/globe` toggle réaliste/léger + événement/orateur → captures ; comparer au
  proto/à la référence Journey. Vérifier le morph 2D⇄3D en réaliste.
- **Non‑régression** : `npx tsc`, `eslint`, `vitest` complet ; scène rend dans les 2 paliers.

## Risques & garde‑fous

- **VRAM 2060S partagée avec Ollama** : 4K/2K + palier + mipmaps ; mesurer `nvidia-smi` avant/après.
  Repli light automatique si le contexte WebGL perd des ressources.
- **Réécriture shader morph** : le point le plus délicat ; reprendre la logique de morph des
  vertices **verbatim**, ne toucher qu'au fragment (couleur). Test visuel du morph obligatoire.
- **Lisibilité du signal pays** sans fill : valider le contraste du liseré teinté sur terre claire
  ET océan sombre (double trait/glow si besoin).
- **Poids git** : downsample avant commit ; source 8K hors build.

## Non‑buts (ce spec)

- Robots skinnés glTF (sous‑projet B).
- Relief/bump/normal‑map, terrain 3D (non fourni ; éventuel plus tard).
- Passage WebGPU/TSL (la référence est WebGPU ; on reste sur notre WebGLRenderer actuel — même
  rendu obtenable en GLSL, pas de migration de moteur).
