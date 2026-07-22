"use client";

/** GlobeStage (spec théâtre-globe §1-§2, §5) — la planète futuriste du théâtre.
 *
 * S1 : globe à texture canvas (palette naturelle assombrie, côtes lumineuses,
 * liserés U), halo atmosphérique, anneaux orbitaux, étoiles, caméra orbitale
 * (drag + inertie + molette + fly-to) et picking pays (clic → fiche).
 * S2 : délégués humanoïdes, drone GM, entité Juge, arcs, anneau d'événement.
 * S3 : LE DÉPLIAGE — une seule scène pour les deux vues (décision full-three) :
 * le vertex shader du globe interpole sphère→plan (`uFlat`), les ancres
 * suivent (position + orientation), le drone garde son orbite en espace
 * sphère et se re-projette au rendu, la caméra fond vers une vue oblique
 * « table tactique », le picking à plat passe par un plan invisible.
 * Bascule par la prop `view` (l'hôte possède le réglage) et touche V
 * (`onViewToggle`) ; le point de vue est préservé dans les deux sens.
 *
 * Règles non négociables (runbook) : composant client only (l'hôte l'importe
 * via `dynamic(…, { ssr: false })`), AUCUNE animation pilotée par setState —
 * tout vit dans la boucle three ; pixelRatio ≤ 1.5 ; `low-power` ; pause si
 * `document.hidden` ; texture repeinte seulement aux changements d'état. */

import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import { feature } from "topojson-client";
import type { GeometryCollection, Topology } from "topojson-specification";

import { useT } from "@/components/settings-provider";
import { speakerMeta } from "@/lib/countries";
import type { EventGeo } from "@/lib/globe-view";
import { CAPITALS, prefersReducedMotion, summitCenter } from "@/lib/stage";

import {
  CAM_HOME,
  EVENT_VIEW,
  JUDGE_VIEW,
  SPEAKER_VIEW,
  camPosition,
  clampDist,
  clampLat,
  flyTowards,
  stepFly,
  zoomBy,
  type CameraFly,
  type CamState,
} from "./camera";
import { paintFlag } from "./flags";
import {
  AnchorRegistry,
  FLAT_EVENT_DIST,
  FLAT_H,
  FLAT_JUDGE_VIEW,
  FLAT_SPEAKER_DIST,
  FLAT_W,
  Q_ID,
  arcCurveAt,
  clampFlat,
  enterFlatView,
  exitFlatView,
  flatCameraPose,
  flatFlyTowards,
  flatWorldPerPixel,
  mixPoint,
  mixTop,
  planeXYZ,
  stepFlatFly,
  stepMorph,
  type FlatCamState,
  type FlatFly,
} from "./morph";
import { countryAt, inverseLL, summitFeatures, toXYZ, type GlobeFeature } from "./picking";
import {
  ROBOT_H,
  aimBeam,
  animateRobot,
  buildArc,
  fillFundStack,
  makeEventGroup,
  makeFundStack,
  makeGMDrone,
  makeJudge,
  makeRobot,
  makeSatellite,
  makeVerdictWave,
  setRobotMood,
  stepDrone,
  stepEventRings,
  stepSatellite,
  stepVerdictWaves,
  type ArcHandle,
  type DroneState,
  type FundStack,
  type RobotHandle,
  type RobotMood,
  type SatelliteState,
} from "./robots";
import { TEX_H, TEX_W, createGlobePainter, type Scar } from "./texture";

/** Superset des props StageMap (spec §2) : le théâtre passe la même vue aux
 * deux modes. Les champs encore muets ici (pense, événement, brouillard…)
 * prennent vie en S2-S3 sans changer le contrat. */
export type GlobeStageProps = {
  countries: string[];
  uByCountry: Record<string, number>;
  utopia: number;
  speaking?: string | null;
  /** Délégué en pleine pensée native (bulle holographique — S2). */
  thinking?: string | null;
  /** Contenu de la bulle (S5) : pensée streamée si `expose_thinking`, sinon le
   * digest « réfléchit à huis clos… ». L'hôte tranche — la scène affiche. */
  thinkingText?: string;
  misled?: Record<string, string>;
  suspended?: string[];
  eventTitle?: string;
  /** Lieu de crise géolocalisé (anneaux pulsants — S2). */
  eventGeo?: EventGeo | null;
  /** L'anneau d'événement pulse (round en cours). */
  pulse?: boolean;
  /** Temps suspendu (verdict) : le Juge s'anime, onde planétaire. */
  frozen?: boolean;
  /** Arc diplomatique orateur → destinataire. */
  arc?: { from: string; to: string } | null;
  /** Cagnottes du marché posées sur la carte (S8) : piles de billets + 💰. */
  funds?: { key: string; lon: number; lat: number; total: number }[];
  /** Balayage satellite (S8) : un `key` nouveau déclenche le vol + scan. */
  scan?: { lon: number; lat: number; key: string | number } | null;
  /** Cicatrices du monde (S9) : les verdicts marquent la texture, ~5 rounds. */
  scars?: Scar[];
  /** Carnet de suspicion (S9) : niveau 0-2 épinglé au-dessus de chaque robot. */
  suspicion?: Record<string, number>;
  /** Motion de censure (S9) : votes en séquence illuminée + décompte. */
  motionVotes?: { country: string; vote: string }[];
  motionTarget?: string | null;
  /** HALL (S11) — pays cliquables au-delà du sommet (sélection sur le globe). */
  pickable?: string[];
  /** HALL (S11) — liseré uniforme (doré) : la partie n'a pas commencé. */
  lisere?: string;
  /** HALL (S11) — le pays incarné : halo cyan + badge « VOUS » sur son délégué. */
  chosen?: string | null;
  /** La vue du joueur (spec §5) : globe, ou LE MÊME monde déplié en carte. */
  view?: "3d" | "2d";
  /** Touche V pressée : l'hôte (qui possède le réglage `stageView`) bascule. */
  onViewToggle?: () => void;
  /** Clic sur un pays du sommet (ou son délégué) → fiche. */
  onCountryClick?: (slug: string) => void;
  /** La caméra suit l'orateur. Le réglage appartient à l'hôte : `onUserDrag`
   * lui signale un drag pour qu'il coupe le suivi (sémantique prototype). */
  followSpeaker?: boolean;
  onUserDrag?: () => void;
  /** Rotation lente d'attente (avant-jeu) : le monde tourne seul derrière la connexion
   * et le hall (full immersion, proto §3) — coupée dès qu'on drague ou qu'un vol se joue. */
  autoRotate?: boolean;
  /** Intention de vol caméra déclarative (full immersion, chorégraphie hall→config) :
   * un nouveau `key` déclenche un fly-to vers (lon,lat,dist) sur `dur` s. L'hôte
   * (StageDirector) la pousse par phase ; la scène joue le vol dans sa boucle. */
  flyTo?: { lon: number; lat: number; dist: number; dur?: number; key: string | number };
  /** WebGL indisponible : l'hôte peut retomber sur la StageMap 2D (S3). */
  onUnsupported?: () => void;
  className?: string;
};

// --- fond 50m (côtes fines), chargé une fois par session --------------------

let featuresPromise: Promise<GlobeFeature[]> | null = null;

function loadFeatures50m(): Promise<GlobeFeature[]> {
  featuresPromise ??= import("world-atlas/countries-50m.json").then((mod) => {
    const topo = mod.default as unknown as Topology<{ countries: GeometryCollection }>;
    return feature(topo, topo.objects.countries).features as unknown as GlobeFeature[];
  });
  return featuresPromise;
}

// --- scène ------------------------------------------------------------------

/** Poignée impérative posée par l'effet de montage — les effets de props ne
 * touchent la scène qu'à travers elle (jamais de setState). */
type GlobeHandle = {
  refresh: () => void;
  flyToCountry: (slug: string) => void;
  flyTo: (lon: number, lat: number, dist: number, dur?: number) => void;
  setEvent: () => void;
  setArc: () => void;
  verdict: () => void;
  setView: (flat: boolean) => void;
  syncFunds: () => void;
  setScan: () => void;
};

function glowTexture(color: string): THREE.CanvasTexture {
  const c = document.createElement("canvas");
  c.width = c.height = 128;
  const x = c.getContext("2d")!;
  const g = x.createRadialGradient(64, 64, 0, 64, 64, 64);
  g.addColorStop(0, color);
  g.addColorStop(0.35, color.replace(")", ",.55)").replace("rgb", "rgba"));
  g.addColorStop(1, "rgba(0,0,0,0)");
  x.fillStyle = g;
  x.fillRect(0, 0, 128, 128);
  return new THREE.CanvasTexture(c);
}

export function GlobeStage(props: GlobeStageProps) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const propsRef = useRef(props);
  const handleRef = useRef<GlobeHandle | null>(null);
  // i18n (S6) : la scène construit ses libellés hors rendu (verdict, tooltip) —
  // la traduction passe par une ref, comme les props.
  const t = useT();
  const tRef = useRef(t);

  // La boucle three et les handlers lisent toujours les DERNIÈRES props via la
  // ref, synchronisée hors rendu (règle react-hooks/refs). Déclaré en premier :
  // les effets suivants la trouvent à jour.
  useEffect(() => {
    propsRef.current = props;
    tRef.current = t;
  });

  // Signatures stables : ne toucher la scène QUE quand l'état change vraiment.
  const {
    speaking = null,
    thinking = null,
    followSpeaker = true,
    utopia,
    eventTitle,
    pulse = false,
    frozen = false,
    view = "3d",
  } = props;
  const tintKey = useMemo(
    () =>
      props.countries
        .map((c) => `${c}:${(props.uByCountry[c] ?? utopia).toFixed(3)}`)
        .join("|"),
    [props.countries, props.uByCountry, utopia],
  );
  const eventKey = props.eventGeo ? `${props.eventGeo.lon},${props.eventGeo.lat}` : "";
  const arcKey = props.arc ? `${props.arc.from}>${props.arc.to}` : "";

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    let dead = false;

    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: "low-power" });
    } catch {
      propsRef.current.onUnsupported?.();
      return;
    }
    const reduced = prefersReducedMotion();
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
    renderer.domElement.style.display = "block";
    host.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    scene.background = new THREE.Color("#04060c");
    const camera = new THREE.PerspectiveCamera(42, 1, 0.01, 100);
    scene.add(new THREE.HemisphereLight(0xd8e6ff, 0x2a3550, 1.35));
    const sun = new THREE.DirectionalLight(0xffffff, 0.85);
    sun.position.set(3, 4, 2);
    scene.add(sun);
    const sun2 = new THREE.DirectionalLight(0x9db8e8, 0.35);
    sun2.position.set(-3, -1, -2);
    scene.add(sun2);

    // Anneaux orbitaux décoratifs — s'effacent quand le monde se déplie.
    const orbitals: [THREE.Mesh<THREE.TorusGeometry, THREE.MeshBasicMaterial>, number][] = [];
    const ring1 = new THREE.Mesh(
      new THREE.TorusGeometry(1.38, 0.0016, 8, 128),
      new THREE.MeshBasicMaterial({ color: 0x4ea8ff, transparent: true, opacity: 0.14 }),
    );
    ring1.rotation.x = Math.PI / 2.25;
    scene.add(ring1);
    orbitals.push([ring1, 0.14]);
    const ring2 = new THREE.Mesh(
      new THREE.TorusGeometry(1.55, 0.0012, 8, 128),
      new THREE.MeshBasicMaterial({ color: 0x59e0c8, transparent: true, opacity: 0.09 }),
    );
    ring2.rotation.x = Math.PI / 1.8;
    ring2.rotation.y = 0.5;
    scene.add(ring2);
    orbitals.push([ring2, 0.09]);

    // Étoiles.
    {
      const n = 1300;
      const pos = new Float32Array(n * 3);
      for (let i = 0; i < n; i++) {
        const u = Math.random() * 2 - 1;
        const th = Math.random() * Math.PI * 2;
        const s = Math.sqrt(1 - u * u);
        const d = 38 + Math.random() * 14;
        pos.set([s * Math.cos(th) * d, u * d, s * Math.sin(th) * d], i * 3);
      }
      const geo = new THREE.BufferGeometry();
      geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
      scene.add(
        new THREE.Points(
          geo,
          new THREE.PointsMaterial({
            color: 0x9db4d8,
            size: 0.055,
            sizeAttenuation: true,
            transparent: true,
            opacity: 0.75,
          }),
        ),
      );
    }

    // Halo atmosphérique (fresnel BackSide additif) — s'efface à plat.
    const atmoMat = new THREE.ShaderMaterial({
      side: THREE.BackSide,
      transparent: true,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
      uniforms: { uFlat: { value: 0 } },
      vertexShader: `varying vec3 vN; void main(){ vN=normalize(normalMatrix*normal);
        gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}`,
      fragmentShader: `varying vec3 vN; uniform float uFlat; void main(){
        float i=pow(0.72-dot(vN,vec3(0.,0.,1.)),3.2);
        gl_FragColor=vec4(0.36,0.65,1.0,1.0)*i*1.2*(1.0-uFlat);}`,
    });
    const atmo = new THREE.Mesh(new THREE.SphereGeometry(1.055, 72, 48), atmoMat);
    scene.add(atmo);

    // Texture du globe — peinte au chargement du fond 50m, puis aux
    // changements d'état seulement (`refresh`). Pas d'étiquette de colorspace :
    // le shader écrit le texel tel quel, comme le prototype.
    const tcan = document.createElement("canvas");
    tcan.width = TEX_W;
    tcan.height = TEX_H;
    const tctx = tcan.getContext("2d")!;
    const texture = new THREE.CanvasTexture(tcan);
    texture.anisotropy = 4;
    // LE globe morphable : chaque sommet bascule sphère→plan dans le vertex
    // shader (uv = position dépliée, par construction de l'équirectangulaire).
    const globeMat = new THREE.ShaderMaterial({
      uniforms: { map: { value: texture }, uFlat: { value: 0 } },
      vertexShader: `
        uniform float uFlat; varying vec2 vUv;
        void main(){
          vUv=uv;
          vec3 flatPos=vec3((uv.x-.5)*${FLAT_W.toFixed(6)},(uv.y-.5)*${FLAT_H.toFixed(6)},0.0);
          vec3 p=mix(position,flatPos,uFlat);
          gl_Position=projectionMatrix*modelViewMatrix*vec4(p,1.0);
        }`,
      fragmentShader: `
        uniform sampler2D map; varying vec2 vUv;
        void main(){ gl_FragColor=texture2D(map,vUv); }`,
    });
    const globe = new THREE.Mesh(new THREE.SphereGeometry(1, 96, 64), globeMat);
    scene.add(globe);
    // Plan invisible : le picking du monde déplié.
    const pickPlane = new THREE.Mesh(
      new THREE.PlaneGeometry(FLAT_W, FLAT_H),
      new THREE.MeshBasicMaterial({ transparent: true, opacity: 0, depthWrite: false }),
    );
    scene.add(pickPlane);

    // Glow de l'orateur (le pays s'allume, le halo respire dans la boucle).
    const speakerGlow = new THREE.Sprite(
      new THREE.SpriteMaterial({
        map: glowTexture("rgb(255,193,77)"),
        transparent: true,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
        opacity: 0,
      }),
    );
    speakerGlow.scale.setScalar(0.3);
    scene.add(speakerGlow);
    // Halo cyan du pays INCARNÉ (hall, spec §9) — badge VOUS projeté avec.
    const chosenGlow = new THREE.Sprite(
      new THREE.SpriteMaterial({
        map: glowTexture("rgb(89,215,255)"),
        transparent: true,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
        opacity: 0,
      }),
    );
    chosenGlow.scale.setScalar(0.22);
    scene.add(chosenGlow);

    // Les habitants du globe (S2) : délégués, drone GM, Juge, événement, arc.
    const anchors = new AnchorRegistry();
    const robots = new Map<string, RobotHandle>();
    const flagTextures = new Map<string, THREE.Texture>();
    const flagTextureOf = (slug: string): THREE.Texture => {
      let tex = flagTextures.get(slug);
      if (!tex) {
        const c = document.createElement("canvas");
        c.width = 48;
        c.height = 32;
        const g = c.getContext("2d")!;
        paintFlag(g, slug, 48, 32, speakerMeta(slug).hue);
        g.strokeStyle = "rgba(0,0,0,.35)";
        g.strokeRect(0, 0, 48, 32);
        tex = new THREE.CanvasTexture(c);
        tex.anisotropy = 2;
        tex.colorSpace = THREE.SRGBColorSpace;
        flagTextures.set(slug, tex);
      }
      return tex;
    };
    const { drone: gmDrone, ring: gmRing, beam: gmBeam } = makeGMDrone();
    scene.add(gmDrone);
    scene.add(gmBeam);
    // La machine à états du drone vit en ESPACE SPHÈRE ; le rendu mixe.
    const gmPos = new THREE.Vector3(1.6, 0, 0);
    let droneState: DroneState = { mode: "orbit", a: 0, t: 0, target: null };
    const judge = makeJudge(glowTexture("rgb(129,140,248)"));
    scene.add(judge.group);
    let judgeMode: { mode: "idle" | "verdict"; t: number } = { mode: "idle", t: 0 };
    let waves: ReturnType<typeof makeVerdictWave>[] = [];
    const eventGroup = makeEventGroup();
    scene.add(eventGroup.group);
    let arcHandle: ArcHandle | null = null;
    let arcLL: [[number, number], [number, number]] | null = null;
    let arcKCache = -1;
    // Satellite de renseignement (S8) : orbite basse permanente, scan à la demande.
    const { sat, beam: scanBeam, ring: scanRing } = makeSatellite();
    scene.add(sat);
    scene.add(scanBeam);
    scene.add(scanRing);
    const satPos = new THREE.Vector3(1.34, 0, 0);
    let satState: SatelliteState = { mode: "orbit", a: 2.1, t: 0, target: null };
    // Piles de billets (S8) : une par cagnotte, rejouées idempotentes.
    const fundStacks = new Map<string, { stack: FundStack; ll: [number, number]; el: HTMLElement }>();

    // DOM projeté (tooltip, bandeau d'événement, étiquette d'orateur) —
    // stylé inline, piloté par la boucle : jamais de setState.
    const makeTag = (extra: string): HTMLDivElement => {
      const el = document.createElement("div");
      el.style.cssText =
        "position:absolute;pointer-events:none;z-index:10;transform:translate(-50%,-140%);" +
        "padding:4px 8px;border-radius:6px;font-size:11px;white-space:nowrap;opacity:0;" +
        "background:rgba(8,12,24,.92);border:1px solid rgba(120,170,255,.35);color:#dbe6ff;" +
        "transition:opacity .12s;" +
        extra;
      host.appendChild(el);
      return el;
    };
    const tooltip = makeTag("");
    const eventTag = makeTag("border-color:rgba(255,193,77,.55);color:#ffe0a3;");
    const speakerTag = makeTag("border-color:rgba(255,193,77,.55);color:#ffe9c2;font-weight:600;");
    const judgeTag = makeTag("border-color:rgba(129,140,248,.55);color:#c7d2fe;");
    // La bulle de pensée holographique (S5) : plus large, multi-lignes, cyan.
    const bubbleTag = makeTag(
      "border-color:rgba(89,215,255,.5);color:#cfe8ff;max-width:260px;white-space:normal;" +
        "text-align:left;font-size:11px;line-height:1.35;box-shadow:inset 0 0 18px -8px rgba(89,215,255,.5);",
    );
    let bubbleBelow = false;
    let bubbleText = "";
    // Épingles de suspicion (S9) : une petite étiquette par robot suspecté.
    const pinTags = new Map<string, HTMLElement>();
    // Décompte de la motion (S9), projeté au barycentre du sommet.
    const tallyTag = makeTag("border-color:rgba(248,113,113,.55);color:#fecaca;font-weight:600;");
    let tallyText = "";
    // Badge du pays incarné (hall, S11).
    const chosenTag = makeTag(
      "border-color:rgba(89,215,255,.6);color:#bfefff;font-weight:700;letter-spacing:.1em;",
    );
    chosenTag.textContent = "🎮 VOUS";

    const PROJ = new THREE.Vector3();
    const CAMV = new THREE.Vector3();
    const LOC = new THREE.Vector3();
    const TMP = new THREE.Vector3();
    const TMP2 = new THREE.Vector3();
    const CAMP = new THREE.Vector3();
    const CAMT = new THREE.Vector3();
    const ORIGIN = new THREE.Vector3(0, 0, 0);

    // État interne de la scène (refs, pas de React).
    let cam: CamState = { ...CAM_HOME };
    let fly: CameraFly | null = null;
    let fcam: FlatCamState = { x: 0, y: 0, dist: 2.2 };
    let flyF: FlatFly | null = null;
    let morphK = 0;
    let morphTarget = 0;
    let vlon = 0;
    let vlat = 0;
    let dragging = false;
    let dragSignaled = false;
    let moved = 0;
    let px = 0;
    let py = 0;
    let hoverT = 0;
    let glowLL: [number, number] | null = null;
    let painter: ReturnType<typeof createGlobePainter> | null = null;
    let feats: ReturnType<typeof summitFeatures> = [];
    let raf = 0;

    const projectAt = (el: HTMLElement, pos: THREE.Vector3, visible: boolean, dy = 0): void => {
      if (!visible) {
        el.style.opacity = "0";
        return;
      }
      PROJ.copy(pos).project(camera);
      // Le test d'horizon n'a de sens que côté sphère : à plat, rien n'est
      // « derrière » le monde.
      const behind =
        PROJ.z > 1 ||
        (morphK < 0.5 &&
          pos.clone().normalize().dot(TMP.copy(camera.position).normalize()) < 0.12);
      const w = host.clientWidth;
      const h = host.clientHeight;
      el.style.left = `${((PROJ.x + 1) / 2) * w}px`;
      el.style.top = `${((-PROJ.y + 1) / 2) * h + dy}px`;
      el.style.opacity = behind ? "0" : "1";
    };

    const refresh = () => {
      if (!painter) return;
      const p = propsRef.current;
      // Picking : au hall, TOUT le roster est cliquable ; en partie, le sommet.
      feats = summitFeatures(p.pickable ?? p.countries, allFeatures);
      const paintFeats = p.pickable ? summitFeatures(p.countries, allFeatures) : feats;
      painter.paint(
        paintFeats.map((f) => ({ ...f, u: p.uByCountry[f.slug] ?? p.utopia })),
        p.speaking ?? null,
        p.scars ?? [],
        p.lisere,
      );
      texture.needsUpdate = true;
      // Délégués : un robot par pays du sommet à capitale connue (un pays
      // inventé n'en a pas — règle existante, conservée).
      const want = new Set(p.countries.filter((c) => CAPITALS[c]));
      for (const [slug, r] of robots) {
        if (want.has(slug)) continue;
        anchors.remove(r.group);
        scene.remove(r.group);
        robots.delete(slug);
      }
      for (const slug of want) {
        if (robots.has(slug)) continue;
        const meta = speakerMeta(slug);
        const cap = CAPITALS[slug];
        const r = makeRobot({ slug, hue: meta.hue, lonlat: cap, flagMap: flagTextureOf(slug) });
        anchors.anchor(r.group, cap[0], cap[1], { lift: 0.001 });
        scene.add(r.group);
        robots.set(slug, r);
      }
      const cap = p.speaking ? CAPITALS[p.speaking] : null;
      if (cap && p.speaking) {
        glowLL = cap;
        speakerGlow.material.opacity = 0.95;
        speakerTag.textContent = `🗣 ${speakerMeta(p.speaking).label}`;
      } else {
        glowLL = null;
        speakerGlow.material.opacity = 0;
      }
    };

    const flyToCountry = (slug: string) => {
      const cap = CAPITALS[slug];
      if (!cap || dragging) return;
      if (morphTarget === 1) {
        const target = { lon: cap[0], lat: cap[1], dist: FLAT_SPEAKER_DIST };
        if (reduced) {
          const [x, y] = planeXYZ(target.lon, target.lat);
          fcam = clampFlat({ x, y, dist: target.dist });
          return;
        }
        flyF = flatFlyTowards(fcam, target, 1.1);
        return;
      }
      const target = { lon: cap[0], lat: cap[1] + SPEAKER_VIEW.latOffset, dist: SPEAKER_VIEW.dist };
      if (reduced) {
        cam = { lon: target.lon, lat: clampLat(target.lat), dist: target.dist };
        return;
      }
      fly = flyTowards(cam, target, 1.15);
    };

    // Vol caméra déclaratif poussé par une intention de phase (hall→config…) : cadre
    // une région (lon,lat,dist) en douceur. Ignoré en mode carte (2D) ou pendant un drag.
    const flyTo = (lon: number, lat: number, dist: number, dur = 1.2) => {
      if (dragging || morphTarget === 1) return;
      if (reduced) {
        cam = { lon, lat: clampLat(lat), dist: clampDist(dist) };
        return;
      }
      fly = flyTowards(cam, { lon, lat, dist }, dur);
    };

    // L'événement du GM : anneaux au lieu de crise, drone qui descend
    // l'annoncer, caméra en plan large. Ré-annonce SEULEMENT si le lieu change
    // (le titre ou la pulsation peuvent bouger sans re-descendre le drone).
    let lastEventKey = "";
    const setEvent = () => {
      const p = propsRef.current;
      const key = p.eventGeo ? `${p.eventGeo.lon},${p.eventGeo.lat}` : "";
      const isNew = key !== lastEventKey && key !== "";
      lastEventKey = key;
      if (!p.eventGeo) {
        eventGroup.group.visible = false;
        anchors.remove(eventGroup.group);
        eventTag.style.opacity = "0";
        return;
      }
      anchors.anchor(eventGroup.group, p.eventGeo.lon, p.eventGeo.lat, {
        lift: 0.004,
        flatQ: Q_ID,
      });
      eventGroup.group.visible = true;
      eventTag.textContent = p.eventTitle ? `⚠ ${p.eventTitle}` : "⚠";
      if (!isNew) return;
      droneState = {
        mode: "announce",
        a: droneState.a,
        t: 0,
        target: new THREE.Vector3(...toXYZ(p.eventGeo.lon, p.eventGeo.lat, 1)),
      };
      if ((p.followSpeaker ?? true) && !dragging) {
        if (morphTarget === 1) {
          const target = { lon: p.eventGeo.lon, lat: p.eventGeo.lat, dist: FLAT_EVENT_DIST };
          if (reduced) {
            const [x, y] = planeXYZ(target.lon, target.lat);
            fcam = clampFlat({ x, y, dist: target.dist });
          } else {
            flyF = flatFlyTowards(fcam, target, 1.4);
          }
          return;
        }
        const target = {
          lon: p.eventGeo.lon,
          lat: p.eventGeo.lat + EVENT_VIEW.latOffset,
          dist: EVENT_VIEW.dist,
        };
        if (reduced) cam = { lon: target.lon, lat: clampLat(target.lat), dist: target.dist };
        else fly = flyTowards(cam, target, 1.5);
      }
    };

    const setArc = () => {
      if (arcHandle) {
        scene.remove(arcHandle.line);
        scene.remove(arcHandle.pulse);
        arcHandle.line.geometry.dispose();
        (arcHandle.line.material as THREE.Material).dispose();
        arcHandle = null;
        arcLL = null;
      }
      const a = propsRef.current.arc;
      if (!a || a.from === a.to) return;
      const from = CAPITALS[a.from];
      const to = CAPITALS[a.to];
      if (!from || !to) return;
      arcHandle = buildArc(from, to);
      arcLL = [from, to];
      arcKCache = -1; // reconstruit au prochain tour de boucle, quel que soit k
      scene.add(arcHandle.line);
      scene.add(arcHandle.pulse);
    };

    // Verdict : le Juge s'emballe, onde planétaire, plan large « au-dessus
    // de la mêlée ».
    const verdict = () => {
      judgeMode = { mode: "verdict", t: 0 };
      judgeTag.textContent = tRef.current("theatre.juge-delibere");
      if (!reduced) {
        const w = makeVerdictWave();
        scene.add(w);
        waves.push(w);
      }
      const p = propsRef.current;
      if ((p.followSpeaker ?? true) && !dragging) {
        if (morphTarget === 1) {
          if (reduced) {
            const [x, y] = planeXYZ(FLAT_JUDGE_VIEW.lon, FLAT_JUDGE_VIEW.lat);
            fcam = clampFlat({ x, y, dist: FLAT_JUDGE_VIEW.dist });
          } else {
            flyF = flatFlyTowards(fcam, FLAT_JUDGE_VIEW, 1.4);
          }
          return;
        }
        if (reduced) cam = { ...cam, lat: JUDGE_VIEW.lat, dist: JUDGE_VIEW.dist };
        else fly = flyTowards(cam, { lon: cam.lon, lat: JUDGE_VIEW.lat, dist: JUDGE_VIEW.dist }, 1.5);
      }
    };

    // Les cagnottes du marché (S8) : créer/remplir/retirer les piles + étiquettes.
    const syncFunds = () => {
      const wanted = new Map((propsRef.current.funds ?? []).map((f) => [f.key, f]));
      for (const [key, entry] of fundStacks) {
        if (wanted.has(key)) continue;
        anchors.remove(entry.stack.group);
        scene.remove(entry.stack.group);
        entry.el.remove();
        fundStacks.delete(key);
      }
      for (const [key, f] of wanted) {
        let entry = fundStacks.get(key);
        if (!entry) {
          const stack = makeFundStack();
          stack.group.scale.setScalar(1.7);
          anchors.anchor(stack.group, f.lon, f.lat, { lift: 0.001 });
          scene.add(stack.group);
          entry = { stack, ll: [f.lon, f.lat], el: makeTag("color:#9fe3b4;") };
          fundStacks.set(key, entry);
        } else if (entry.ll[0] !== f.lon || entry.ll[1] !== f.lat) {
          entry.ll = [f.lon, f.lat];
          anchors.anchor(entry.stack.group, f.lon, f.lat, { lift: 0.001 });
        }
        fillFundStack(entry.stack, f.total);
        entry.el.textContent = `💰 ${Math.round(f.total)} ₲`;
      }
    };

    // Le balayage satellite (S8) : un `key` nouveau = un vol + un scan.
    let lastScanKey: string | number | null = null;
    const setScan = () => {
      const s = propsRef.current.scan;
      if (!s || s.key === lastScanKey) return;
      lastScanKey = s.key;
      if (satState.mode !== "orbit") return; // un seul vol à la fois
      satState = {
        mode: "goto",
        a: satState.a,
        t: 0,
        target: new THREE.Vector3(...toXYZ(s.lon, s.lat, 1)),
      };
      anchors.anchor(scanRing, s.lon, s.lat, { lift: 0.004, flatQ: Q_ID });
    };

    // La bascule (spec §5) : le point de vue est préservé dans les deux sens ;
    // `prefers-reduced-motion` saute le dépliage (morph instantané).
    const setView = (flat: boolean) => {
      const target = flat ? 1 : 0;
      if (morphTarget === target) return;
      morphTarget = target;
      if (flat) {
        fcam = enterFlatView(cam);
        flyF = null;
      } else {
        cam = exitFlatView(fcam);
        fly = null;
      }
      if (reduced) morphK = target;
    };

    let allFeatures: GlobeFeature[] = [];
    loadFeatures50m().then((loaded) => {
      if (dead) return;
      allFeatures = loaded;
      painter = createGlobePainter({ ctx: tctx, features: allFeatures });
      refresh();
      setEvent();
      setArc();
      syncFunds();
      setScan();
      setView(propsRef.current.view === "2d");
      handleRef.current = {
        refresh,
        flyToCountry,
        flyTo,
        setEvent,
        setArc,
        verdict,
        setView,
        syncFunds,
        setScan,
      };
    });

    // --- interactions --------------------------------------------------------
    const ray = new THREE.Raycaster();
    const ndc = new THREE.Vector2();
    const setRay = (e: PointerEvent | MouseEvent): boolean => {
      const r = renderer.domElement.getBoundingClientRect();
      if (r.width === 0 || r.height === 0) return false;
      ndc.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
      ray.setFromCamera(ndc, camera);
      return true;
    };
    // Robots d'abord (gros hitbox), sinon le monde : sphère → geoContains, ou
    // plan déplié → lon/lat linéaire (le raycast CPU ignore le vertex shader,
    // d'où le plan de picking dédié).
    const slugAt = (e: PointerEvent | MouseEvent): string | null => {
      if (!setRay(e)) return null;
      const pool = [...robots.values()].map((r) => r.group);
      const robotHit = ray.intersectObjects(pool, true)[0];
      if (robotHit) {
        let o: THREE.Object3D | null = robotHit.object;
        while (o && !o.userData.slug) o = o.parent;
        if (o) return o.userData.slug as string;
      }
      if (morphK > 0.5) {
        const hit = ray.intersectObject(pickPlane)[0];
        if (!hit) return null;
        return countryAt(
          [(hit.point.x / (FLAT_W / 2)) * 180, (hit.point.y / (FLAT_H / 2)) * 90],
          feats,
        );
      }
      const hit = ray.intersectObject(globe)[0];
      return hit ? countryAt(inverseLL([hit.point.x, hit.point.y, hit.point.z]), feats) : null;
    };

    const onPointerDown = (e: PointerEvent) => {
      dragging = true;
      dragSignaled = false;
      moved = 0;
      px = e.clientX;
      py = e.clientY;
      fly = null;
      flyF = null;
    };
    const onPointerUp = () => {
      dragging = false;
    };
    const onWindowMove = (e: PointerEvent) => {
      if (!dragging) return;
      const dx = e.clientX - px;
      const dy = e.clientY - py;
      px = e.clientX;
      py = e.clientY;
      moved += Math.abs(dx) + Math.abs(dy);
      if (moved > 6 && !dragSignaled) {
        dragSignaled = true;
        propsRef.current.onUserDrag?.();
      }
      if (morphK > 0.5) {
        // À plat, le drag PANNE la carte : le monde suit le curseur.
        const wpp = flatWorldPerPixel(fcam.dist, host.clientHeight || 1);
        fcam = clampFlat({ x: fcam.x - dx * wpp, y: fcam.y + dy * wpp, dist: fcam.dist });
      } else {
        vlon = -dx * 0.22;
        vlat = dy * 0.22;
        cam = { ...cam, lon: cam.lon + vlon, lat: clampLat(cam.lat + vlat) };
      }
    };
    const onHover = (e: PointerEvent) => {
      if (dragging) return;
      const now = performance.now();
      if (now - hoverT < 70) return;
      hoverT = now;
      const slug = slugAt(e);
      renderer.domElement.style.cursor = slug ? "pointer" : "grab";
      if (slug) {
        const r = host.getBoundingClientRect();
        tooltip.textContent = `${speakerMeta(slug).label} — ${tRef.current("theatre.tooltip-fiche")}`;
        tooltip.style.left = `${e.clientX - r.left}px`;
        tooltip.style.top = `${e.clientY - r.top}px`;
        tooltip.style.opacity = "1";
      } else {
        tooltip.style.opacity = "0";
      }
    };
    const onClick = (e: MouseEvent) => {
      if (moved > 6) return;
      if (morphK > 0.02 && morphK < 0.98) return; // pas de picking en plein dépliage
      const slug = slugAt(e);
      if (slug) propsRef.current.onCountryClick?.(slug);
    };
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      if (morphK > 0.5) {
        fcam = clampFlat({ ...fcam, dist: fcam.dist * (1 + Math.sign(e.deltaY) * 0.1) });
      } else {
        cam = zoomBy(cam, Math.sign(e.deltaY));
      }
    };
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key !== "v" && e.key !== "V") return;
      const el = e.target as HTMLElement | null;
      if (el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.isContentEditable))
        return;
      propsRef.current.onViewToggle?.();
    };

    renderer.domElement.addEventListener("pointerdown", onPointerDown);
    renderer.domElement.addEventListener("pointermove", onHover);
    renderer.domElement.addEventListener("click", onClick);
    renderer.domElement.addEventListener("wheel", onWheel, { passive: false });
    window.addEventListener("pointerup", onPointerUp);
    window.addEventListener("pointermove", onWindowMove);
    window.addEventListener("keydown", onKeyDown);

    const resize = () => {
      const w = host.clientWidth;
      const h = host.clientHeight;
      if (w === 0 || h === 0) return;
      renderer.setSize(w, h);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
    };
    const ro = new ResizeObserver(resize);
    ro.observe(host);
    resize();

    // --- boucle ---------------------------------------------------------------
    const clock = new THREE.Clock();
    const frame = () => {
      raf = requestAnimationFrame(frame);
      if (document.hidden) return;
      const dt = Math.min(0.05, clock.getDelta());

      // Le morph avance vers sa cible ; tout le monde suit.
      morphK = stepMorph(morphK, morphTarget, dt);
      anchors.apply(morphK);
      globeMat.uniforms.uFlat.value = morphK;
      atmoMat.uniforms.uFlat.value = morphK;
      for (const [o, base] of orbitals) o.material.opacity = base * (1 - morphK);

      // Caméra : inertie orbitale (côté sphère), vols des deux mondes.
      if (!dragging && morphK < 0.5) {
        vlon *= Math.pow(0.05, dt);
        vlat *= Math.pow(0.05, dt);
        if (Math.abs(vlon) > 0.002 || Math.abs(vlat) > 0.002) {
          cam = { ...cam, lon: cam.lon + vlon, lat: clampLat(cam.lat + vlat) };
        }
      }
      // Rotation lente d'attente (avant-jeu, full immersion) : le monde vit seul derrière
      // la connexion et le hall — coupée par le drag, un vol de caméra, le mode carte ou
      // le réglage reduced-motion.
      if (propsRef.current.autoRotate && !dragging && !fly && morphK < 0.5 && !reduced) {
        cam = { ...cam, lon: cam.lon + 3.5 * dt };
      }
      if (fly) {
        const step = stepFly(cam, fly, dt);
        cam = step.cam;
        fly = step.fly;
      }
      if (flyF) {
        const step = stepFlatFly(fcam, flyF, dt);
        fcam = step.fcam;
        flyF = step.fly;
      }
      CAMP.set(...camPosition(cam));
      CAMT.copy(ORIGIN);
      if (morphK > 0) {
        const pose = flatCameraPose(fcam);
        CAMP.lerp(TMP.set(...pose.position), morphK);
        CAMT.lerp(TMP2.set(...pose.target), morphK);
      }
      camera.position.copy(CAMP);
      camera.lookAt(CAMT);

      const t = clock.elapsedTime;
      const p = propsRef.current;

      // Drone GM : machine à états en espace sphère, rendu morphé.
      droneState = stepDrone(gmPos, gmBeam, droneState, dt);
      mixPoint(gmPos, morphK, gmDrone.position);
      if (droneState.mode === "announce" && droneState.target) {
        aimBeam(gmBeam, gmDrone.position, mixPoint(droneState.target, morphK, TMP));
      }
      gmRing.rotation.z += dt * (droneState.mode === "announce" ? 4 : 1.2);
      gmDrone.lookAt(
        morphK > 0.5 ? TMP.set(gmDrone.position.x, gmDrone.position.y, -10) : ORIGIN,
      );

      // Satellite de renseignement (S8) : même principe que le drone.
      satState = stepSatellite(satPos, scanBeam, scanRing, satState, dt, t, reduced);
      mixPoint(satPos, morphK, sat.position);
      if (satState.mode === "scan" && satState.target) {
        aimBeam(scanBeam, sat.position, mixPoint(satState.target, morphK, TMP));
      }
      sat.lookAt(morphK > 0.5 ? TMP.set(sat.position.x, sat.position.y, -10) : ORIGIN);

      // Le Juge : au-dessus du monde… quel que soit l'état du monde.
      const verdictOn = judgeMode.mode === "verdict";
      judge.core.rotation.y += dt * (verdictOn ? 1.6 : 0.35);
      judge.ringA.rotation.z += dt * (verdictOn ? 1.8 : 0.3);
      judge.ringB.rotation.z -= dt * (verdictOn ? 1.4 : 0.22);
      TMP.set(0, 1.72 + (reduced ? 0 : Math.sin(t * 0.9) * 0.02), 0);
      TMP2.set(0, FLAT_H / 2 + 0.18, 0.85);
      judge.group.position.copy(TMP).lerp(TMP2, morphK);
      if (verdictOn) {
        judgeMode = { mode: "verdict", t: judgeMode.t + dt };
        judge.core.scale.setScalar(reduced ? 1 : 1 + Math.sin(t * 6) * 0.12);
        if (judge.halo) judge.halo.material.opacity = 0.5 + Math.sin(t * 5) * 0.25;
        if (judgeMode.t > 5) {
          judgeMode = { mode: "idle", t: 0 };
          judge.core.scale.setScalar(1);
          if (judge.halo) judge.halo.material.opacity = 0.5;
        }
      }
      const aliveWaves = stepVerdictWaves(waves, dt, morphK);
      for (const w of waves) {
        if (aliveWaves.includes(w)) continue;
        scene.remove(w);
        w.geometry.dispose();
        w.material.dispose();
      }
      waves = aliveWaves;

      // Délégués : humeur (suspendu > pense > parle > repos) + face caméra.
      const suspendedSet = new Set(p.suspended ?? []);
      const voteBySlug = new Map((p.motionVotes ?? []).map((v) => [v.country, v.vote]));
      for (const r of robots.values()) {
        const mood: RobotMood = suspendedSet.has(r.slug)
          ? "suspended"
          : p.thinking === r.slug
            ? "thinking"
            : p.speaking === r.slug
              ? "speaking"
              : "idle";
        if (mood !== r.mood) setRobotMood(r, mood);
        if (mood !== "suspended") {
          const local = r.group.worldToLocal(CAMV.copy(camera.position));
          r.spinner.rotation.y = Math.atan2(local.x, local.z);
        }
        animateRobot(r, t, reduced);
        r.veil.visible = !!p.misled?.[r.slug];
        // Motion illuminée (S9) : le socle du votant s'allume — pour (suspendre)
        // = rouge, contre (garder) = vert, abstention = gris ; la cible rougit.
        const vote = voteBySlug.get(r.slug);
        r.base.material.color.set(
          vote === "pour"
            ? "#f87171"
            : vote === "contre"
              ? "#34d399"
              : vote
                ? "#9ca3af"
                : p.motionTarget === r.slug
                  ? "#f87171"
                  : speakerMeta(r.slug).hue,
        );
      }

      // Anneau d'événement, arc (reconstruit selon le morph), glow d'orateur.
      if (eventGroup.group.visible) {
        stepEventRings(eventGroup.rings, t, !reduced && (p.pulse ?? false));
      }
      if (arcHandle && arcLL && morphK !== arcKCache) {
        arcKCache = morphK;
        arcHandle.curve = arcCurveAt(arcLL[0], arcLL[1], morphK);
        arcHandle.line.geometry.dispose();
        arcHandle.line.geometry = new THREE.BufferGeometry().setFromPoints(
          arcHandle.curve.getPoints(72),
        );
      }
      if (arcHandle) {
        const kk = reduced ? 0.5 : (t * 0.55) % 1;
        arcHandle.pulse.position.copy(arcHandle.curve.getPointAt(kk));
      }
      if (glowLL) speakerGlow.position.copy(mixTop(glowLL, 1.008, 0.008, morphK, TMP));
      if (p.speaking && !reduced) {
        speakerGlow.material.opacity = 0.7 + Math.sin(t * 3.2) * 0.2;
      }
      // Le pays incarné (hall) : halo cyan qui respire + badge VOUS.
      const chosenCap = p.chosen ? CAPITALS[p.chosen] : null;
      if (p.chosen && chosenCap) {
        chosenGlow.position.copy(mixTop(chosenCap, 1.01, 0.01, morphK, TMP));
        chosenGlow.material.opacity = reduced ? 0.7 : 0.6 + Math.sin(t * 2.6) * 0.2;
        mixTop(chosenCap, 1 + ROBOT_H * 1.3, ROBOT_H * 1.3, morphK, LOC);
        projectAt(chosenTag, LOC, true, -4);
      } else {
        chosenGlow.material.opacity = 0;
        chosenTag.style.opacity = "0";
      }

      // Étiquettes projetées : un seul chemin, la scène (morphée) fait foi.
      projectAt(eventTag, eventGroup.group.position, eventGroup.group.visible, -14);
      const spkSlug = p.speaking ?? null;
      const spkCap = spkSlug ? CAPITALS[spkSlug] : null;
      if (spkSlug && spkCap && robots.has(spkSlug)) {
        mixTop(spkCap, 1 + ROBOT_H * 1.12, ROBOT_H * 1.12, morphK, LOC);
        projectAt(speakerTag, LOC, true, 8);
      } else {
        speakerTag.style.opacity = "0";
      }
      // La bulle de pensée : au-dessus du penseur, bascule dessous si elle
      // frôle le bord haut (sémantique prototype `.below`).
      const thkSlug = p.thinking ?? null;
      const thkCap = thkSlug ? CAPITALS[thkSlug] : null;
      if (thkSlug && thkCap && robots.has(thkSlug)) {
        mixTop(thkCap, 1 + ROBOT_H * 1.12, ROBOT_H * 1.12, morphK, LOC);
        bubbleTag.style.transform = bubbleBelow ? "translate(-50%,10%)" : "translate(-50%,-108%)";
        projectAt(bubbleTag, LOC, true, bubbleBelow ? 22 : -6);
        bubbleBelow = parseFloat(bubbleTag.style.top) < 110;
        const txt = p.thinkingText ?? "";
        if (txt !== bubbleText) {
          bubbleText = txt;
          bubbleTag.textContent = txt;
        }
      } else {
        bubbleTag.style.opacity = "0";
      }
      projectAt(judgeTag, judge.group.position, judgeMode.mode === "verdict", -10);
      for (const entry of fundStacks.values()) {
        mixTop(entry.ll, 1.014, 0.032, morphK, LOC);
        projectAt(entry.el, LOC, entry.stack.bills > 0, -4);
      }
      // Épingles de suspicion (S9) au-dessus des délégués suspectés.
      const suspicion = p.suspicion ?? {};
      for (const r of robots.values()) {
        const level = suspicion[r.slug] ?? 0;
        let pin = pinTags.get(r.slug);
        const cap = CAPITALS[r.slug];
        if (level > 0 && cap) {
          if (!pin) {
            pin = makeTag("padding:2px 6px;font-size:10px;");
            pinTags.set(r.slug, pin);
          }
          const label = level >= 2 ? "🔍‼" : "🔍";
          if (pin.textContent !== label) pin.textContent = label;
          pin.style.borderColor =
            level >= 2 ? "rgba(248,113,113,.65)" : "rgba(255,193,77,.55)";
          mixTop(cap, 1 + ROBOT_H * 1.5, ROBOT_H * 1.5, morphK, LOC);
          projectAt(pin, LOC, true, -2);
        } else if (pin) {
          pin.style.opacity = "0";
        }
      }
      // Décompte de la motion (S9), au-dessus du barycentre du sommet.
      const votes = p.motionVotes ?? [];
      if (votes.length > 0) {
        const pour = votes.filter((v) => v.vote === "pour").length;
        const contre = votes.filter((v) => v.vote === "contre").length;
        const abst = votes.length - pour - contre;
        const txt = `⚖ pour ${pour} · contre ${contre}${abst ? ` · abst. ${abst}` : ""}`;
        if (txt !== tallyText) {
          tallyText = txt;
          tallyTag.textContent = txt;
        }
        const center = summitCenter(p.countries);
        if (center) {
          mixTop(center, 1.09, 0.09, morphK, LOC);
          projectAt(tallyTag, LOC, true, 0);
        }
      } else {
        tallyTag.style.opacity = "0";
      }

      renderer.render(scene, camera);
    };
    frame();

    return () => {
      dead = true;
      handleRef.current = null;
      cancelAnimationFrame(raf);
      ro.disconnect();
      renderer.domElement.removeEventListener("pointerdown", onPointerDown);
      renderer.domElement.removeEventListener("pointermove", onHover);
      renderer.domElement.removeEventListener("click", onClick);
      renderer.domElement.removeEventListener("wheel", onWheel);
      window.removeEventListener("pointerup", onPointerUp);
      window.removeEventListener("pointermove", onWindowMove);
      window.removeEventListener("keydown", onKeyDown);
      scene.traverse((o) => {
        const mesh = o as Partial<THREE.Mesh>;
        if (mesh.geometry) mesh.geometry.dispose();
        const mats = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
        for (const m of mats) {
          if (!m) continue;
          const tex = (m as THREE.MeshBasicMaterial).map;
          if (tex) tex.dispose();
          m.dispose();
        }
      });
      renderer.dispose();
      for (const el of [tooltip, eventTag, speakerTag, judgeTag, bubbleTag, tallyTag, chosenTag])
        el.remove();
      for (const entry of fundStacks.values()) entry.el.remove();
      for (const pin of pinTags.values()) pin.remove();
      renderer.domElement.remove();
    };
    // Montage unique : les changements d'état passent par les effets ci-dessous.
  }, []);

  // Changements d'état de jeu → repeindre / suivre l'orateur (via la poignée,
  // jamais de setState : la boucle three reste seule maîtresse du temps).
  // Une SEULE dépendance composite : le tableau garde une taille constante à
  // jamais (chaque ajout d'état étend la chaîne, pas le tableau — sinon chaque
  // hot-reload d'un effet vivant déclenche l'avertissement React « size
  // changed between renders »).
  const sceneKey = [
    tintKey,
    speaking ?? "",
    thinking ?? "",
    followSpeaker ? "1" : "0",
    JSON.stringify(props.scars ?? []),
    (props.pickable ?? []).join("|"),
    props.lisere ?? "",
  ].join("§");
  useEffect(() => {
    const h = handleRef.current;
    if (!h) return;
    h.refresh();
    const p = propsRef.current;
    const target = p.speaking ?? p.thinking;
    if (target && (p.followSpeaker ?? true)) h.flyToCountry(target);
  }, [sceneKey]);

  useEffect(() => {
    handleRef.current?.setEvent();
  }, [eventKey, eventTitle, pulse]);

  useEffect(() => {
    handleRef.current?.setArc();
  }, [arcKey]);

  // Front montant seulement : le verdict est un événement, pas un état.
  useEffect(() => {
    if (frozen) handleRef.current?.verdict();
  }, [frozen]);

  // La vue du joueur : le monde se déplie ou se replie (spec §5).
  useEffect(() => {
    handleRef.current?.setView(view === "2d");
  }, [view]);

  // Cagnottes et balayage satellite (S8) — clés stables, la scène rejoue.
  const fundsKey = JSON.stringify(props.funds ?? []);
  useEffect(() => {
    handleRef.current?.syncFunds();
  }, [fundsKey]);
  const scanKey = props.scan?.key ?? null;
  useEffect(() => {
    handleRef.current?.setScan();
  }, [scanKey]);

  // Chorégraphie caméra (full immersion) : chaque nouvelle intention `flyTo` (poussée par
  // le StageDirector au changement de phase) déclenche un vol vers la région cadrée.
  const flyToKey = props.flyTo?.key ?? null;
  useEffect(() => {
    const f = propsRef.current.flyTo;
    if (f) handleRef.current?.flyTo(f.lon, f.lat, f.dist, f.dur);
  }, [flyToKey]);

  return (
    <div
      ref={hostRef}
      role="img"
      aria-label={t("theatre.aria-globe")}
      className={props.className ?? "relative h-full w-full overflow-hidden"}
      style={{ position: "relative", overflow: "hidden", touchAction: "none" }}
    />
  );
}
