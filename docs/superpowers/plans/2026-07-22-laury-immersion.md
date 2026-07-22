# Full immersion à l'identique de proto_9 — Laury 3D + chorégraphie caméra

> Cible user : tout l'univers = UNE scène 3D continue (connexion → tutoriel Laury → hall →
> config → théâtre), planète aussi détaillée que possible, pas de page/scroll. La mécanique
> RÉELLE (auth, création, SSE) s'adapte à cette coquille immersive.

## Constat clé (cartographie du JS de proto_9, l.427-1927)

**Ma scène `web/src/components/globe/globe-stage.tsx` + sous-modules (texture/robots/camera/
morph/picking) est DÉJÀ un portage fidèle du proto — souvent au-dessus** : côtes **50m** (proto
110m) + cicatrices (proto n'a pas), même shader morph, atmosphère fresnel, 2 anneaux, 1300
étoiles, délégués humanoïdes (+ voile brouillard/cadenas suspension que le proto n'a pas), drone
GM, Juge + onde de verdict, satellite, billets, arcs, fly-to orateur/événement/verdict, bulle de
pensée, dépliage 2D⇄3D. **⇒ NE PAS réécrire la scène. NE RIEN copier du proto sur la planète.**

## Le vrai delta (priorisé)

### 1. Laury 3D + tutoriel (NEUF — priorité) → nouveau `web/src/components/globe/mascot.ts`
Chibi assemblé en primitives three (PAS de sprite/modèle), **contour « sticker » par coques
inversées** (`MeshBasicMaterial{color:#fff, side:BackSide}`, clone géométrie × scale 1.07-1.08).
Racine Group `scale 0.68`, `visible=false`. Matériaux : skin `#a7693d`, black `#131317`, hair
`#1c0f08`, tee `#f4f2ea`, gum `#d9d6cb`, eye Basic `#3a2313`. (proto l.1651-1714)
- Tête `Sphere(.021,22,18)` scale(1,.95,.96) @ (0,.052,0) ; 2 yeux (globe `.0052` + reflet `.0016`) ;
  8 boucles cheveux `Sphere(.0045)` en arc ; calotte `Sphere(.0215,20,14,0,2π,0,π*.52)` ; visière
  `Cylinder(.019,.019,.0028,18,1,false,-.62,1.24)` scale(1,.55,1.35).
- Torse `Cylinder(.0125,.0155,.024,14)` tee ; bandoulière + sacoche black ; bras G + main.
- **Bras D levé (LE geste)** : Group `armR` @ (.013,.033,.002) ; dans armR : le **petit monde**
  `Sphere(.0085,18,14)` `MeshBasicMaterial{map: LA TEXTURE DU GLOBE}` @ (.011,.0255,.008) + halo
  `Torus(.0122,.0006,8,36)` cyan + étincelle `Octahedron(.0016)` ambre.
- Jambes+sneakers (s=±1). Contours : hull(head,1.07), hull(cap,1.07), hull(torso,1.08).
- Retourne `{g, rig, head, armR, mini, halo, spark}`.

**Animation compagnon-caméra** (dans la boucle `frame`, proto l.1609-1624) : ancre devant la
caméra (`camDir*.28 + camRight*(-.125) + camUp*(-.052)`) ; si `tutoTarget`, lerp .38 vers le
point du globe présenté ; suivi lissé position `1-exp(-6dt)` + quaternion slerp `1-exp(-8dt)` ;
idle : bob y `sin(t*2.1)*.0016`, roll z `sin(t*1.3)*.04`, `mini.rotation.y += dt*.7`, halo
opacity `.6+sin(t*3)*.2`, spark orbite. Gelé si reduced-motion.

**Visite 8 étapes** (`TUTO`, proto l.1717-1764) + carte DOM `#tuto-card` (nom « ● LAURY —
gardien du petit monde », texte machine-à-écrire 52 cps, step k/8, passer/suivant) :
1 accueil · 2 « la planète EST le plateau » go:event · 3 « délégués = IA à pensée native »
go:speaker · 4 « le liseré = trajectoire U » go:wide · 5 « ta colonne » hl:transcript ·
6 « clique un délégué » **gate:fiche** (branché sur `onCountryClick`) · 7 « appuie V, le monde se
déplie » **gate:flat** (branché sur `onViewToggle`) · 8 « démasque le traître sans faire tomber le
monde » end. Verrous : `tutoGateHit(kind)` débloque « SUIVANT » ; `startTuto/stepTuto/endTuto`.
Entrée : pastille hall « Première fois ? Visite guidée — avec Laury » → lance une partie tutoriel
puis `startTuto()`.
**React** : `mascot.ts` (pur, réutilise `createGlobePainter`/la texture pour le `mini`) ; poignée
`startTuto/stepTuto/endTuto` sur `GlobeStage` pilotée par une prop `tutorial` (step + gates) ;
carte `#tuto-card` en overlay HUD.

### 2. Hall en immersion caméra continue (petit, fort impact)
Manque dans `globe-stage.tsx` : **`autoRotate`** (rotation lente d'attente `cam.lon += 1.1*dt`
quand pas de drag/suivi — derrière connexion & hall). + fly-to de transition : menu→config
`flyTo(38,24,3.1,1.2)`, **plongée au lancement** `cam.dist=max(dist,4.1)`. À câbler via une prop
d'intention caméra dérivée de `phase` (StageShell/StageDirector) → `GlobeStage`.

### 3. Théâtre plein-cadre → voir `2026-07-22-theatre-plein-cadre.md` (SP-1→SP-6).

### 4. (Optionnel) Mode Laboratoire (absent de `robots.ts`) : arène `Ring` concentriques + 2
candidats labA/labB + `enterLab/exitLab/nextLab` + caméra bercée autour de Genève (proto l.1048-1107).

### 5. (Optionnel, au-delà des DEUX protos) planète « encore plus détaillée » : fond `countries-10m`,
couche **nuages** (2ᵉ sphère alpha, rotation lente), **night-lights** + spéculaire océan
(échantillonnage additionnel dans le fragment shader), relief/bump (⇒ globe en matériau éclairé).
À peser vs budget `low-power` (2060S partagée avec Ollama).

## Mock du proto à remplacer par le vrai backend (déjà en place côté app)
SUMMIT/CAPITALS/EVENTS/SCRIPT/MARKETS/FINDINGS/LAB en dur → roster réel + **flux SSE**
(`sse.ts`) + `createGame` (`api.ts`) + marché/renseignement réels. La coquille (`stage-shell`,
`stage-director`, `config-overlay`) fusionne déjà ce flux réel dans la scène.
