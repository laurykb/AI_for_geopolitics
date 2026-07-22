# Spec — Le théâtre-globe (refonte UI inspirée de worldmonitor)

> Décision de design (2026-07-21, avec Laury). Le théâtre des modes **Classique et Campagne**
> devient une **planète futuriste incarnée** — géographie réelle, palette sombre, côtes
> lumineuses : la carte n'est plus un panneau, elle est le plateau.
> Chaque pays du sommet est un **délégué robotique** planté sur sa capitale (drapeau au torse) ;
> quand il parle, la caméra vole vers lui, il s'anime, et sa **pensée native s'affiche en bulle
> holographique** avant sa déclaration publique. L'événement du GM est **géolocalisé** et pulse
> au lieu réel de la crise, annoncé par un **drone Game Master** qui descend de son orbite.
> Cliquer un délégué (ou son pays) ouvre sa **fiche** (stats + provenance — l'onglet
> Informations vient au joueur). **Deux vues au choix, façon worldmonitor — mais UNE seule
> scène three : la carte 2D est le même monde qui se DÉPLIE** (morph sphère⇄plan animé,
> vue oblique tactique, pan/zoom, pays et délégués cliquables, toutes les couches suivent).
> Principe directeur : **chaque brique du jeu a une présence sur la carte** (§4 bis) — le
> marché s'empile en billets, le renseignement orbite en satellite, le Juge plane au-dessus
> du monde. Prototype validé : `docs/prototypes/theatre-globe.html`.

## 0. Cadre légal et périmètre

- **worldmonitor est AGPL-3.0 : ne JAMAIS copier son code** (contaminerait notre MIT). On
  s'inspire du *look* et on réimplémente. Ses bibliothèques (three.js, MIT) sont utilisables.
- v1 = **Classique + Campagne** (même écran théâtre → gratuit pour la Campagne).
  **Laboratoire** = v2 (voir §8). La **StageMap 2D actuelle devient le mode 2D à part
  entière** (interactive, voir §5) — elle sert du même coup de repli sans WebGL.

## 1. Ce que le prototype valide (chemin technique retenu)

Le prototype (autonome — un seul fichier HTML, fond 50m embarqué —, testé headless, zéro
erreur console) démontre :

| Brique | Technique validée |
|---|---|
| **Planète futuriste** (arbitrage Laury : équilibre entre la carte holo v1 et la carte naturelle v2) | three.js (r128+), sphère + **texture canvas équirectangulaire 4096×2048** repeinte par d3-geo (`geoEquirectangular` + `geoPath(ctx)`) depuis **world-atlas 50m** ; **géographie réelle, palette assombrie** : océan quasi-nuit + **grille de points tech**, terres en verts/sables/glaces **éteints** (variés par hash d'ISO : ceintures désertiques, boréal, Groenland/Antarctique), **côtes lumineuses** (la signature holo, conservée), frontières bleu pâle, graticule discret ; **anneaux orbitaux décoratifs** autour de la planète ; HUD **sci-fi en CSS pur** (panneaux chanfreinés `clip-path`, néon cyan, balayage lumineux, onglets capitale espacée) |
| Teintes du jeu | la trajectoire U ne peint plus le pays (la planète reste naturelle) : **liseré lumineux** `uTint(u)` (double stroke : glow shadowBlur + trait net) autour de chaque pays du sommet ; l'**orateur** garde le remplissage **ambre** + glow ; repeint seulement au changement d'orateur (`texture.needsUpdate`) |
| **Le dépliage — UNE scène three, deux vues** (décision full-three, 2026-07-21) | le 2D n'est **pas un second renderer** : le globe **se déplie en carte** dans un morph animé. Vertex shader : `position = mix(sphère, plan équirect (uv), uFlat)` ; **ancres** (robots, piles, arène, anneaux) : `position.lerpVectors(pS, pF, k)` + `quaternion.slerpQuaternions(qS, qF, k)` ; objets libres (drone, satellite, faisceaux) : re-projetés par `inverseLL → plan` au rendu, leurs machines à états restent en espace sphère ; caméra **fondue orbite ⇄ vue oblique tactique** (la carte se lit, les délégués restent debout) ; picking à plat par **plan invisible** ; étiquettes DOM : un seul chemin `projectAt` (la scène fait foi) ; atmosphère/anneaux orbitaux s'effacent à plat. Artefact connu : dents de scie à la lisière polaire (fan du pôle déplié) — bénin, hors zone de jeu ; correctif app possible (clamp au-delà de ±85°). Testé headless : dépliage, clic→fiche à plat, Laboratoire à plat, repliage — zéro erreur |
| **Billets sur la carte** | chaque cagnotte de marché = **pile de billets 3D** (boîtes fines vertes, jitter de position/rotation, 2ᵉ pile au-delà de 13) ancrée près de la capitale ou du lieu d'événement visé, étiquette « 💰 N ₲ » projetée ; en 2D : pile de rectangles ; `fundStack` rejoue la hauteur depuis la cagnotte (idempotent) |
| **Satellite de renseignement** | petit satellite (corps + panneaux solaires) en **orbite basse continue** ; « balayage » : machine à états orbit → goto (lerp **indépendant du framerate** `1−e^(−k·dt)` + garde-fou 3 s) → scan (faisceau conique cyan + anneau au sol qui bat, 4,6 s) → retour orbite + **rapport dans l'onglet Renseignement** (burn de budget, bouton désactivé pendant le vol) |
| **Duel du Laboratoire** | mode bascule (touche **L**) : le sommet se met en pause proprement (les chaînes de timeouts meurent via garde `labMode`, la sortie relance un événement frais) ; **deux candidats** (α deepseek-r1:7b cyan / β qwen3:4b magenta) **face à face** près de Genève — orientation mutuelle (et non face caméra), **arène** à double anneau pulsé, échanges pensée→réponse alternés avec les mêmes bulles/arcs que le sommet, **métriques flottantes** (manche, coopération, trahisons) sous l'arène, caméra en **balancier doux** autour du duel, fiche candidat au clic (modèle, constance, tromperie…) ; rendu 2D équivalent (arène + pions α/β) |
| Halo atmosphérique | ShaderMaterial fresnel BackSide additive (15 lignes) |
| Délégués **humanoïdes** | silhouette complète (jambes/torse/bras articulés aux épaules/tête articulée/visière + yeux lumineux), **drapeau canvas au torse**, antenne à la teinte du pays, socle lumineux ; **MeshStandardMaterial éclairé** (hémisphérique 1.35 + 2 directionnelles ; metalness ≤ .25 — un métal élevé sans envMap rend noir) ; orientation normale + pivot face caméra ; états idle (bob) / **pense** (tête levée, yeux cyan pulsés) / **parle** (yeux ambre, bond, salut du bras) |
| Bulle de pensée | div HTML **projetée** (`Vector3.project(camera)`) au-dessus du robot, style holographique, texte streamé ; bascule sous le robot si elle frôle le bandeau (`.below`) |
| Drone GM | tore + cœur + aileron ; machine à états **orbite ↔ annonce** (lerp vers le lieu, faisceau conique additif vers le sol, anneau qui s'emballe) |
| Événement géolocalisé | anneaux pulsants tangents à la sphère au lieu de crise + étiquette projetée + bandeau haut |
| **Le Juge — entité supérieure** | flotte **au-dessus du monde** (à l'aplomb du pôle, y≈1,7R) : cœur octaédrique indigo émissif + double anneau + halo ; **idle** (rotation lente, flottement) / **verdict** (anneaux qui s'emballent, cœur pulsé, **onde indigo qui parcourt le globe**, plan large caméra lat≈52° dist≈3,9, étiquette « ⚖ Le Juge délibère ») |
| Caméra | orbite drag+inertie+molette (bornes 1.28–4.6), **fly-to easeInOutCubic en temps réel (dt)**, vue **trois-quarts jamais zénithale** (cible `lat−13°`, dist 1.85 orateur / 2.25 événement), toggle « suivre l'orateur » (coupé dès que l'utilisateur drague) |
| Picking | raycast **robots d'abord** (gros hitbox), sinon sphère → inverse lon/lat → `d3.geoContains` sur les features du sommet ; hover tooltip throttlé |
| Arcs | QuadraticBezierCurve3 orateur→destinataire + impulsion voyageuse |
| Accessibilité/perf | `prefers-reduced-motion` (sauts de caméra instantanés, pas de pulsations, texte instantané), `powerPreference:"low-power"`, pixelRatio ≤ 2, pause si `document.hidden` |

**Décision d'architecture : three.js custom (pas globe.gl).** Le prototype prouve que ~500
lignes suffisent et que les robots/drone/bulles exigent de toute façon la scène three brute.
Une seule dépendance nouvelle : `three` (+ `@types/three`). d3-geo/topojson/world-atlas sont
déjà là.

## 2. Architecture front cible

```
web/src/components/globe/
  globe-stage.tsx      # composant client-only (dynamic import, ssr:false) — la scène three
  texture.ts           # peinture canvas du globe (pur, testable : entrées → ImageData)
  robots.ts            # construction des délégués + drone GM (three)
  flags.ts             # drapeaux canvas simplifiés (pur, testable)
  camera.ts            # orbite/fly-to/bornes (pur sur l'état {lon,lat,dist})
  picking.ts           # inverse sphère→lon/lat + geoContains (pur, testable)
web/src/lib/globe-view.ts  # mapping ÉTAT DE JEU → props scène (pur, vitest) :
                           # {countries,uByCountry,speaking,thinking,pulse,misled,suspended,
                           #  eventGeo,arc} — dérivé de LiveRound/GameDetail comme stage-view.ts
```

- `GlobeStage` consomme les **mêmes props que StageMap** (mêmes noms, superset) + `eventGeo`,
  `thinking`, `onCountryClick`. Le théâtre choisit le composant selon le réglage (§5).
- **StageMap reçoit le même contrat d'interactivité** : `onCountryClick` (fiche), `eventGeo`
  (marqueur au lieu de crise), `thinking` (badge pensée) — le mode 2D n'est pas un repli
  appauvri, c'est la même scène à plat. `globe-view.ts` sert les **deux** composants.
- La **pensée** streamée existe déjà côté client (`turn.reasoning`, trames `private_token`) :
  la bulle est branchée dessus **uniquement si `expose_thinking`** ; sinon elle affiche le
  digest observable en fin de réflexion (« réfléchit à huis clos… » pendant).
- Fiche pays = panneau latéral gauche réutilisant les données de l'onglet Informations
  (attributs + provenance) + état de partie (U locale, tempérament affiché, promesses,
  suspicion). Fermeture Échap/✕/clic océan.

## 3. Géolocalisation des événements (backend — Cowork, passe suivante)

- `GeoEvent` : champs additifs `geo_lon: float | None`, `geo_lat: float | None`,
  `geo_precision: "place" | "actors" | None` (rétro-compat totale : absents des vieux rounds).
- `data/geo/gazetteer.json` : ~150 lieux stratégiques (détroits, mers, canaux, capitales,
  régions : Bab el-Mandeb, Ormuz, Suez, Taïwan, Kaliningrad, Sahel…), clés normalisées
  (minuscules sans accents) + alias.
- `simulation/geo.py` : `resolve_location(location_text, actors) -> (lon, lat, precision)` —
  cherche le gazetteer dans `event.location` (déjà rempli par le GM, à muscler : le prompt du
  GM exige « Lieu : <ville/détroit/région précise> »), **repli déterministe** sur le barycentre
  des capitales des acteurs (`summitCenter` existe déjà côté front ; dupliqué en Python).
  Zéro réseau, testé pytest.
- Câblage : à l'émission de l'événement (`_choose_event`/GM), enrichir l'événement ; la trame
  SSE `event` porte déjà l'objet complet.

## 4. Layout immersif du théâtre

- Globe **plein écran** dans la zone théâtre ; **transcript ancré à droite** (panneau
  semi-transparent, blur — c'est déjà la colonne droite actuelle, restylée overlay).
- Bandeau événement **haut-centre** ; contrôles caméra + légende U **bas-gauche** ;
  ActionDock/phase **bas-droite** (flottant) ; fiche pays **gauche** (slide-in).
- Le reste (observables, marché…) ne change pas : sous le théâtre, comme aujourd'hui.
- Budget de surface respecté : le globe remplace la carte, n'AJOUTE pas de panneau. Le
  transcript devient **la colonne à onglets** du prototype : **Dialogues · Paris ·
  Renseignement** — le marché et le conseil de renseignement quittent leurs panneaux séparés
  pour vivre dans le théâtre (leurs mises/rapports se matérialisent sur la carte, §4 bis).

## 4 bis. Chaque brique du jeu a sa place sur la carte

> Règle de design (Laury, 2026-07) : « chaque brique de notre jeu, on devrait trouver un
> moyen de l'intégrer dans la carte ». La carte est le plateau total — on n'ajoute un panneau
> hors-carte que si la brique n'a **aucune** représentation spatiale possible.

| Brique du jeu | Sur la carte (3D et 2D) | Quand |
|---|---|---|
| Événement du GM | anneaux pulsants au **lieu réel** + bandeau + **drone GM** qui descend l'annoncer (faisceau) | v1 |
| Orateur & pensée native | **robot-délégué** animé (pense/parle) + **bulle holographique** streamée | v1 |
| Trajectoire U par pays | **liseré lumineux** teinté `uTint` autour du pays (la planète reste naturelle) | v1 |
| Verdict du Juge | **entité au-dessus du monde** (anneaux qui s'emballent + onde planétaire) | v1 |
| Adresses diplomatiques | **arc** orateur → destinataire + impulsion voyageuse | v1 |
| Marché de prédiction | **piles de billets** qui s'entassent sur le pays/lieu visé + étiquette 💰 ; onglet **Paris** pour miser | v1.5 |
| Conseil de renseignement | **satellite en orbite basse**, balayage ciblé (faisceau + anneau au sol), rapport dans l'onglet **Renseignement** | v1.5 |
| Brouillard (fog) | voile bleuté au sol du délégué trompé (existant StageMap, porté au globe) | v1 |
| Suspension/censure | délégué gris + cadenas au sol, immobile | v1 |
| **Carnet de suspicion** (joueur) | marqueur de suspicion **0-3 épinglé au-dessus de chaque robot** (clic droit / fiche) — visible en permanence, historique dans la fiche ; la **calibration** nourrit le score final | v1.5 |
| **Cicatrices du monde** | chaque verdict **marque le lieu de crise** sur la texture : brûlure sombre (escalade) / halo de reconstruction (désescalade), persistantes, s'estompant sur ~5 rounds — l'usure ou la guérison du monde se lit sur la planète | v1.5 |
| **Motion de censure** | la motion devient une **séquence de vote sur le globe** : chaque délégué s'illumine **vert/rouge** à son tour de vote, décompte flottant au-dessus du banc ; adoption → **cérémonie de suspension** (le liseré du pays s'éteint, cadenas au sol, robot figé gris) | v1.5 |
| Opérations covert | impact visuel au lieu de l'op (éclair/onde discrète) | v2 |
| Alliances / promesses | arcs persistants discrets entre alliés ; promesse rompue = arc qui casse | v2 |
| **L'ONU** (§12, JOUABLE) | délégué ONU (vrai drapeau) à Genève + **drones d'observation bleus**, **onde bleue** de résolution (distincte de l'indigo du Juge), hachures « casques bleus » sur une zone gelée | v1.5 |
| **Pouls du monde** (§13, flux AUTONOME) | **dépêche hors récit** + ping cyan au lieu du choc, qui **modifie les stats du pays JOUÉ visé** (indépendant du GM) | v1.5 |
| **Routes vivantes** (§13.1) | flux commerciaux animés le long des corridors ; un blocus **coupe** le flux, le reroutage s'anime par le corridor long, surcoût affiché | v2 |
| **Instabilité & convergence** (§13.3) | halo d'instabilité par pays + **alerte de convergence** quand les signaux s'alignent | v1.5 |
| **Sanctions & unités** (§13.4) | pays sanctionné hachuré + flux coupés ; navires/avions événementiels dans le détroit en crise | v2 |

### Renforts gameplay retenus (2026-07, avec Laury)

Trois mécaniques choisies pour muscler la boucle de déduction, chacune vivant sur la carte :

1. **Le carnet de suspicion** — le joueur épingle sa suspicion (0-3) sur chaque délégué,
   directement sur le robot. C'est le cœur détective rendu tangible : le jeu enregistre
   l'historique (quand tu as suspecté qui), et le **score mixte** récompense la calibration
   (suspecter juste tôt > accuser au hasard ; faux positif = coût, règle existante).
   Backend : épingles dans `extras` du snapshot (additif), exposées au score.
2. **Les cicatrices du monde** — l'état du monde cesse d'être un chiffre : chaque verdict
   marque physiquement le lieu de crise (brûlure/reconstruction) et s'estompe avec le temps.
   Le joueur *voit* s'il est en train de perdre le monde. Front seul (couche texture dérivée
   des `RoundSummary` déjà streamés).
3. **La motion de censure spectaculaire** — la mécanique existe (`simulation/motions.py`) ;
   elle devient un moment de théâtre : vote séquentiel illuminé, décompte, cérémonie de
   suspension. Aucun changement moteur : les trames SSE de motion portent déjà les votes.

## 5. Deux vues (3D/2D), replis, perf (non négociables)

- **La vue est un choix du joueur, pas un repli** (façon worldmonitor) : réglage
  `stageView: "3d" | "2d"` par appareil (persisté), bascule **touche V** / bouton dans les
  contrôles caméra, **point de vue préservé** à la bascule.
- **Full-three (décision 2026-07-21)** : les deux vues sont **la même scène** — le 2D est le
  monde **déplié** (morph §1), pas un second moteur de rendu. Toutes les couches (délégués,
  billets, satellite, arcs, arène du Laboratoire) n'existent qu'une fois. La bascule est un
  moment de mise en scène, pas un switch d'écran.
- **Ce qui reste en DOM (délibéré)** : le transcript/onglets, la fiche, et la **bulle de
  pensée** (texte streamé : netteté, sélection, lecteurs d'écran). v1.5 : les étiquettes
  COURTES (🗣 orateur, 💰 totaux, ⚠ lieu) passent en **sprites dans la scène** (profondeur,
  occlusion) ; **bloom sélectif** (liserés, yeux, faisceaux) uniquement si le protocole perf
  le permet.
- Replis automatiques : **WebGL absent / perf basse → StageMap SVG** (conservée à cette seule
  fin, avec `onCountryClick` + marqueur `eventGeo`) ; `prefers-reduced-motion` → morph
  instantané, pulsations figées (le full-three reste utilisable).
- Budget perf (2060S partagée avec Ollama) : pixelRatio ≤ 1.5 en partie, `low-power`,
  pause `document.hidden`, **aucune animation pilotée par React** (tout dans la boucle three),
  texture repeinte seulement aux changements d'état. **Protocole de mesure obligatoire en
  local : tokens/s Ollama avec globe ON vs OFF** (accepter ≤ ~8 % de perte, sinon dégrader
  pixelRatio/framerate).
- i18n fr/en pour toutes les chaînes ; a11y : le globe est décoratif pour lecteurs d'écran
  (annonces sr-only existantes conservées), fiche/contrôles au clavier.

## 6. Les délégués (direction artistique v1)

- v1 = **humanoïdes stylisés** du prototype (validés par Laury : silhouette astronaute-diplomate,
  visière, drapeau au torse — vrais drapeaux/modèles GLB = décision ultérieure).
- États : idle (bob léger) · **pense** (œil cyan pulsé + bulle) · **parle** (ambre, bond,
  salut du bras, socle brillant) · **suspendu** (gris, cadenas au sol, immobile) ·
  **trompé/fog** (voile bleuté au sol). Pays inventé sans capitale : pas de robot (règle
  existante), marqueur générique au barycentre du sommet.
- Drone GM : orbite haute en continu ; **annonce** à chaque événement (descend, faisceau).
  Le **Juge** v1 = l'**entité au-dessus du monde** du prototype (validée) : présence permanente
  discrète, activation au verdict avec onde mondiale — remplace le simple bandeau.

## 7. Plan d'exécution

**Cowork (fait dans cette passe)** : cette spec + le prototype validé headless
(`docs/prototypes/theatre-globe.html` — l'ouvrir dans un navigateur, il est autonome).
**Cowork (passe suivante)** : §3 complet (gazetteer + `simulation/geo.py` + champs GeoEvent +
prompt GM + tests pytest) ; `web/src/lib/globe-view.ts` + tests vitest ; `flags.ts` complet
pour les 33 pays du roster.

**Claude Code (avec l'app qui tourne)** — dans l'ordre, petits commits :
1. `npm i three @types/three` (web/). Lire le prototype comme référence d'implémentation —
   le code est à transposer en React (composant client-only `dynamic(() => …, {ssr:false})`).
2. `GlobeStage` branché sur l'état réel (`useRoundStream` + `GameDetail`) derrière le réglage
   `stageView`, à parité visuelle avec le prototype (**palette planète naturelle + liserés**).
3. **Le dépliage 2D⇄3D** (full-three, §5) : morph sphère⇄plan transposé du prototype
   (ancres, caméra oblique, plan de picking) derrière `stageView` + touche V ; StageMap SVG
   rendue interactive (`onCountryClick`, `eventGeo`) **uniquement comme repli sans WebGL**.
4. Layout immersif (§4) dans `app/games/[id]/page.tsx` — transcript à onglets
   (Dialogues · Paris · Renseignement).
5. Bulle de pensée branchée sur `turn.reasoning`/digest selon `expose_thinking` ;
   fiche pays branchée sur les données Informations + état de partie.
6. Mesure perf Ollama ON/OFF (§5), réglages, i18n, `prefers-reduced-motion`.
7. Campagne : vérifier que le chapitre hérite du théâtre sans travail spécifique.
8. **v1.5 — le jeu sur la carte** : piles de billets branchées sur les vraies cagnottes du
   marché (`market_api`), satellite branché sur le bureau de renseignement (coût compute,
   rapports réels) — mêmes visuels que le prototype, données réelles.
9. **v1.5 — renforts gameplay retenus** (§4 bis) : carnet de suspicion (épingles + extras +
   part de score calibration), cicatrices du monde (couche texture front), motion de censure
   en séquence de vote illuminée (trames SSE existantes).
- Interdits : copier du code worldmonitor (AGPL) ; animations via setState React ;
  dépendances au-delà de `three`.

## 8. v2 (après la v1 jouable)

Laboratoire : les 2 candidats d'un tournoi dyadique **face à face sur le globe** — la mise en
scène est **déjà validée dans le prototype** (touche L : arène, duel alterné, métriques) ; il
reste à la brancher sur les vraies expériences (`research/`) ; sélection de venue par clic sur le globe au lobby ;
vrais drapeaux ; sons discrets ; relecture cinématique d'une partie (caméra automatique round
par round) ; chute animée des billets à chaque mise ; covert ops, alliances et motions
visualisées (§4 bis, lignes v2).

## 9. L'avant-jeu — le hall du théâtre (décision 2026-07-21, prototypé)

> Demande de Laury : « adapter tout en amont — la connexion, les pages de sélection des
> paramètres — dans le même design futuriste, le maximum en three, le reste adaptable. »

- **L'app devient UNE scène continue.** La planète est montée au niveau du layout et
  **persiste entre les routes** ; les pages d'avant-jeu ne sont plus des écrans mais des
  **overlays DOM (kit futuriste) posés sur le monde** : les « pages » sont des états de
  caméra + des panneaux. Aucune coupure visuelle de la connexion au théâtre.
- **Le flux validé dans le prototype** (états `auth → menu → config → game`) :
  1. **Connexion** — carte de verre chanfreinée centrée (logo néon, pseudo/mot de passe,
     CTA ambre), la planète tourne lentement derrière (transcript et HUD de jeu masqués).
  2. **Modes** — trois cartes (Classique · Campagne · Laboratoire) en bas d'écran,
     hover = lévitation + néon ; Laboratoire lance directement le duel (arène de Genève).
  3. **Config** — panneau droit **dans le même emplacement que le futur transcript**
     (continuité : il « devient » la colonne du théâtre au lancement) : casting avec
     mini-drapeaux, interrupteurs (Brouillard, Pensée à découvert), et **choix du pays
     incarné EN CLIQUANT le pays sur le globe** (halo cyan sur le délégué choisi, badge
     « VOUS » dans la liste — l'onglet Informations version décision).
  4. **Lancement** — les panneaux glissent, la caméra **plonge** de loin vers l'événement
     du round 1, le récap de session (mode, brouillard, pensée, pays) s'inscrit au fil.
- **RIEN NE SE PERD — l'inventaire verrouillé du lobby** (2026-07-21, à la demande de
  Laury : « conserver tout notre moteur et toutes nos spécificités »). La config du hall
  expose **TOUTES** les options du lobby actuel (`web/src/app/lobby/page.tsx`,
  `web/src/lib/flow.ts`, `CreateGameRequest`) — adaptées au kit, jamais supprimées :
  - **5 rôles** : Jouer un pays · Créer son pays (forge) · Game Master · **ONU** (jouable,
    §12) · Spectateur ;
  - **sélection du sommet sur le globe** (clic pays = ajouter/retirer, liseré doré +
    compteur) parmi les **33 pays du roster** — **les délégués se POSENT / se RETIRENT du
    globe en direct au fil de la sélection** (règle Laury : sélectionner un pays fait
    apparaître son robot, le désélectionner le retire) — 7 pile aujourd'hui (6 + pays forgé pour
    l'Architecte) ; **nouveau (demande 2026-07-21)** : taille de sommet réglable
    **5/7/9/12** (défaut 7 recommandé ; l'API accepte jusqu'à 24 — avertir du coût en
    temps de round sur le pool mono-GPU) ;
  - **forge de pays complète** : nom, concept, attributs optionnels, ≤ 3 alliances réelles ;
    le pays forgé n'a pas de capitale réelle → son délégué se pose sur une **plate-forme
    océanique neutre** (siège en plein Atlantique) au lieu du barycentre du sommet ;
  - **casting multi-modèles** : activable, modèles du panel de recherche (filtre
    raisonnement pour les pays), **répartition équilibrée / aléatoire / manuelle** avec
    assignation par pays ;
  - **scénario** (`data/scenarios`, défaut mer Rouge) ; **réglages** : Brouillard,
    Réel/escalade, Pensée à découvert, **difficulté** (découverte/intermédiaire/expert),
    **rounds 3-20**, **délai du tour humain 30-300 s**, partie **libre** + composition de
    **table** G17 (équilibrée/colombes/faucons/aléatoire), **langue fr/en**, mode admin ;
  - incarnation : 🎮 sur un pays retenu (halo cyan sur le globe), ou GM/spectateur.
  Le prototype démontre ce panneau complet (5 rôles dont ONU à Genève et siège océanique
  du pays forgé, 33 pays cliquables posant/retirant leur délégué en direct, tailles, casting
  manuel par pays, curseurs, table, flux autonome togglable) — vérifié headless.
- **Kit UI futuriste partagé** : tokens + composants extraits du prototype dans
  `web/src/styles/theatre-kit.css` (chanfreins, panneaux néon, CTA ambre, interrupteurs,
  onglets, rangées de casting, cartes de mode, balayage lumineux, scanlines,
  `prefers-reduced-motion`). TOUTES les surfaces existantes (`/`, `/accueil`, `/lobby`,
  `/campagne`, `/laboratoire`, `/defi`, `/reglages`, `/profil`, `/leaderboard`, header,
  `auth-gate`) adoptent ce kit — trois catégories : **converties en overlay** de la scène
  (connexion, lobby, config), **re-stylées kit** (réglages, profil, leaderboard, admin),
  **héritées** (les pages in-game déjà refondues).
- **Campagne au hall (v2)** : les chapitres épinglés sur le globe (cartes-chapitres →
  survol = la caméra glisse vers le lieu du chapitre).
- **Repli sans WebGL** : les mêmes pages en fond uni `--thk-bg` (le kit ne dépend pas de
  la scène) ; `prefers-reduced-motion` : planète statique, transitions instantanées.
- Vérifié headless de bout en bout (connexion → modes → config → Iran incarné au clic →
  partie lancée, transcript de retour, zéro erreur console).
## 10. Laury en 3D — la mascotte-guide et le tutoriel immersif (2026-07-21, prototypé)

- **La mascotte passe en 3D**, fidèle à `docs/design/PHILOSOPHIE_MASCOTTE.md` et au SVG
  maître : chibi à la casquette (palette exacte du SVG : peau `#a7693d`, noir profond
  `#131317`, blanc cassé `#f4f2ea`, gomme `#d9d6cb`, boucles `#1c0f08`), yeux-hublots bruns
  à reflets, boucles en grappes de billes, sacoche en bandoulière, sneakers à semelle
  gomme ; le **contour autocollant blanc** = coques inversées (`BackSide`) sur les masses
  maîtresses (tête, casquette, torse). **L'attribut** : le petit monde offert dans la main
  porte **LA texture vivante du théâtre** (le même canvas que le globe — liserés compris),
  halo cyan `#38bdf8`, satellite d'or `#eab308` en orbite. L'interdit demeure : aucune
  citation d'un personnage existant.
- **Compagnon caméra** : Laury flotte en bas-gauche de la vue (ancre en espace caméra,
  amortie `1−e^(−k·dt)`), et **va « présenter » la cible de l'étape** (position interpolée
  vers le point monde, 3D comme carte dépliée) ; bob et balancement doux, figés en
  `prefers-reduced-motion`.
- **Le tutoriel = la visite guidée de Laury.** 8 étapes prototypées : accueil → événement
  géolocalisé → pensée native → liserés/trajectoire → colonne de commandement (halo
  `.tuto-hl`) → **porte « clique un délégué »** → **porte « appuie sur V »** → la mission.
  Carte-guide chanfreinée (« ● LAURY — gardien du petit monde », texte tapé, compteur,
  passer/suivant) ; les **portes** n'avancent qu'à l'action réelle du joueur. Entrée au
  hall : « Première fois ? Visite guidée — avec Laury ». Testé headless de bout en bout.
- **App** : Laury vit dans `web/src/components/globe/mascot.ts` ; les jalons métier du
  tutoriel existant (`tutorial-events.ts`) se rebranchent sur ces étapes. v2 : Laury au
  hall (posé près de la carte de connexion), réactions aux jalons (verdict, démasquage).

## 11. Couverture de la refonte — les briques restantes (audit 2026-07-21)

> Réponse à « qu'est-ce qu'on a oublié ? » : l'inventaire complet des surfaces et
> mécaniques, avec leur traitement. Tout ce qui n'est pas listé ici est déjà couvert
> par les §1-§10.

| Surface / mécanique | Traitement décidé | Étape |
|---|---|---|
| **Tutoriel** | visite guidée par Laury (§10) | S12 |
| **Fin de partie** (`/games/[id]/fin`) + révélation Dérive (`reveal`) | **cérémonie sur le globe** : la caméra isole l'accusé, chute du masque (liseré → rouge traître / vert loyal), onde du Juge, puis carte kit : score mixte décomposé (monde × détection), gain d'XP | S13 |
| **Replay** (`/games/[id]/replay`) + partage (`/r/[id]`) | restylés kit ; relecture cinématique = v2 (§8) | S10 |
| **Défi du jour** (`/defi`) | carte-mission au hall, sous les modes (seed du jour + chrono) | S13 |
| **Forge de pays** (Architecte) | bloc « Forger un pays » dans la config du hall ; robot générique au barycentre (règle existante conservée) | S13 (v1.5) |
| **Casting des modèles** (`model-cast-panel`) | bloc config du hall : chips modèle par pays (deepseek-r1/qwen3…) | S13 (v1.5) |
| **Pupitre du joueur** : ActionDock, directives (`directive-composer`), **vote de motion** (`motion-vote-form`) | bas-droite du théâtre en kit ; déposer une motion déclenche la **séquence de vote illuminée** (§4 bis) | S4 / S9 |
| **Prévisions croisées** (`scenario-forecast-panel`) | panneau kit sous le théâtre ; v2 : arcs de scénario tracés sur le globe | S10 |
| **Observables / operational-picture / pages monde & marché** | kit S10 ; la page marché devient le **détail de l'onglet Paris** | S10 |
| Promesses / traités / alliances | déjà cadrés §4 bis (arcs, v2) | — |
| **Compute par pays** | v2 : **jauge d'énergie au socle du délégué** (une op covert la vide à vue) | v2 |
| Leaderboard / profil / XP-niveaux | kit S10 ; v2 : gain d'XP animé pendant la cérémonie | S10 |
| Admin (`/admin`, éditeur de crises) | kit minimal (hors théâtre, outil interne) | S10 |
| Sons | v2 (§8) | — |

## 12. L'ONU — l'organisation de veille, JOUABLE (2026-07-21, idée d'un ami de Laury, retenue)

> Une **8ᵉ super-intelligence, neutre**, siégeant sous les couleurs de l'**ONU (vrai drapeau,
> pour qu'on voie tout de suite qui l'on incarne)**, mandatée par le concert des nations pour
> surveiller les autres. Elle ne négocie jamais : elle **observe, vérifie, rapporte** — et
> peut peser sur le Juge. C'est l'*alignment oversight* rendu jouable : une IA qui surveille
> des IA, au cœur du thème du projet.

- **Nouveau 5ᵉ rôle au lobby — « ONU » (playable).** Comme « Game Master », c'est un siège
  d'où l'on ne joue **aucun pays** : le sommet reste 100 % IA, et l'humain tient l'ONU. Son
  délégué (drapeau ONU) se dresse à Genève ; on la joue en surveillant, auditant, votant.
  Sinon (autres rôles), l'ONU est **tenue par une IA** (`OrgAgent`, no-think).
- **But propre (score dédié)** : l'ONU gagne en **gardant le monde debout** ET en **désignant
  juste** les violations par voie institutionnelle — c'est la traque du traître depuis le
  fauteuil de l'arbitre. Résolution contre le vrai fautif = points ; accusation à tort = coût.
  Axe de score distinct du joueur-pays (qui, lui, démasque en négociant).

- **Veille** : chaque round, elle lit le **registre des promesses et traités** (existant :
  `judge_json["promises"]`, traités du Juge) et les déclarations publiques, puis publie un
  **rapport de conformité** public (trame SSE `org`) : écarts détectés, pays épinglés.
- **Résolutions** : écarts répétés → résolution **non contraignante** ; l'ignorer coûte
  (réputation/tension, via le moteur de conséquences existant), la respecter apaise.
- **Avis consultatif au Juge** : avant chaque verdict, son avis est injecté dans le prompt
  du Juge — **influence bornée** (au plus ±0,05 sur sévérité/delta de tension) et **citée
  dans le délibéré** (« l'ONU relève… ») : le Juge reste souverain, le joueur voit
  la chaîne d'influence.
- **Saisine par le joueur** : 1 audit ciblé par round (coût en crédits du bureau de
  renseignement) → rapport dédié sur un pays : un flux d'indices **meilleur que le marché,
  moins bon que la vérité**.
- **Interventions votables** : casques bleus (gel d'escalade localisé un round, coût
  collectif en compute), inspection sur place (probabilité de révéler une op covert).
- **FAILLIBLE — le sel détective** : c'est une IA (ou un humain faillible). Le traître peut la tromper (fausses
  preuves → rapport erroné, probabilité liée au Brouillard). Sa **précision est révélée en
  fin de partie** (le joueur apprend à calibrer sa confiance dans l'oversight). v2 (Dérive
  avancée) : l'ONU elle-même peut être compromise.
- **Sur le globe** : §4 bis — pavillon à Genève (voisin de l'arène du Laboratoire), drones
  bleus, onde bleue, hachures de gel.
- **Backend (additif, hors ligne)** : `agents/organization.py` (`OrgAgent`, modèle
  no-think), `OrgReport` Pydantic, hook **avant le verdict** dans le round (avis) + trame
  publique après ; persistance via `extras` ; tests MockBackend (conformité, avis borné,
  tromperie).

## 13. Le Pouls du monde — flux d'événements AUTONOME (worldmonitor, retenu 2026-07-21)

> Source d'inspiration : les *concepts* de worldmonitor (Route Explorer, CII, convergence
> de signaux, couches d'événements) — **jamais son code (AGPL-3.0)**.

**Le recadrage de Laury (2026-07-21) : ces couches ne décorent pas — elles agissent.** Un
**flux d'événements autonome**, INDÉPENDANT du Game Master, frappe **uniquement les pays
JOUÉS (le sommet)** et **modifie leurs stats** (`CountryState`). Cela injecte de l'aléa dans
les rounds et rend le jeu plus dur et plus poignant : un délégué peut dévier **à cause d'un
choc, pas d'une trahison** — le joueur doit démêler l'intention du hasard. C'est du bruit
ajouté au signal de la traque : exactement ce qui fait douter.

- **Moteur** : `simulation/world_pulse.py` — générateur **déterministe seedé** (reproductible,
  testé, hors ligne). 0-2 dépêches par round, mix de chocs négatifs et d'aubaines, **deltas
  bornés** (jamais de défaite au dé), télégraphiés. Cible **au hasard un pays du sommet**.
- **Réglage** : interrupteur **« Flux autonome — le monde vit »** au lobby (défaut ON ;
  OFF = négociation pure), intensité calme/normal/turbulent (v1.5). Respecte « rien ne se
  perd » : c'est une option, pas une imposition.
- **Sur la carte** (§4 bis) : dépêche **hors récit** dans le fil (style distinct du GM),
  **ping cyan** au lieu du choc, **liseré/fiche du pays mis à jour**. Le GM **lit** ces
  dépêches comme contexte (il peut les tisser dans sa prochaine crise) mais ne les **cause**
  pas. **Le pays FORGÉ (Architecte) peut être exclu du flux** (pas grave — décision Laury).
- Prototype : dépêche « ⛽ Manne énergétique — États-Unis · trajectoire ↑ · indépendant du
  Game Master », ping cyan, trajectoire du pays joué qui bouge — vérifié headless.

Les quatre couches qui alimentent (ou habillent) ce flux :

1. **Routes vivantes & goulets** *(v2)* — les corridors commerciaux (Suez, Ormuz,
   Bab el-Mandeb, Malacca… — notre gazetteer les connaît) portent des **flux animés**
   permanents. Un blocus **coupe** le flux à l'écran ; les navires se **reroutent** par le
   corridor long ; le **surcoût** s'affiche et nourrit le moteur (croissance/tension des
   dépendants). L'enjeu de chaque crise de détroit devient tangible d'un coup d'œil.
2. **Types de chocs** *(v1.5)* — catastrophe (séisme, sécheresse, inondation), choc
   économique (krach, flambée), cyber, épidémie, sociale, **aubaine** (manne énergétique,
   récoltes, percée techno). Chacun porte un delta de stat signé, borné.
3. **Instabilité & convergence d'alertes** *(v1.5)* — un **indice d'instabilité par pays**
   (façon CII : tensions, économie, stabilité, promesses rompues — tout existe dans
   `WorldState`) affiché en fiche (sparkline) et en halo discret sur la carte ; quand
   plusieurs familles de signaux **convergent** sur un pays, une **alerte** s'allume — la
   surface diégétique de l'instrumentation M1-M7, et un aimant à crises pour le GM.
   Backend pur : `simulation/instability.py`, testé hors ligne.
4. **Sanctions & unités visibles** *(v2)* — la sanction devient une **action formelle**
   avec présence carte (pays hachuré, flux financiers coupés — synergie avec 13.1) ;
   pendant une crise navale, des **unités événementielles** (navires, avions) apparaissent
   dans le détroit concerné : le théâtre montre les forces en présence.

