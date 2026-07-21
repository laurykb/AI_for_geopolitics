"use client";

/** GlobeStage (spec théâtre-globe §1-§2) — la planète futuriste du théâtre.
 *
 * S1 : globe à texture canvas (palette naturelle assombrie, côtes lumineuses,
 * liserés U), halo atmosphérique, anneaux orbitaux, étoiles, caméra orbitale
 * (drag + inertie + molette + fly-to) et picking pays (clic → fiche).
 * Les délégués, le drone GM, le Juge et les arcs arrivent en S2 — le contrat
 * de props (superset StageMap, spec §2) est déjà complet et stable.
 *
 * Règles non négociables (runbook) : composant client only (l'hôte l'importe
 * via `dynamic(…, { ssr: false })`), AUCUNE animation pilotée par setState —
 * tout vit dans la boucle three ; pixelRatio ≤ 1.5 ; `low-power` ; pause si
 * `document.hidden` ; texture repeinte seulement aux changements d'état. */

import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import { feature } from "topojson-client";
import type { GeometryCollection, Topology } from "topojson-specification";

import { speakerMeta } from "@/lib/countries";
import type { EventGeo } from "@/lib/globe-view";
import { CAPITALS, prefersReducedMotion } from "@/lib/stage";

import {
  CAM_HOME,
  EVENT_VIEW,
  JUDGE_VIEW,
  SPEAKER_VIEW,
  camPosition,
  clampLat,
  flyTowards,
  stepFly,
  zoomBy,
  type CameraFly,
  type CamState,
} from "./camera";
import { paintFlag } from "./flags";
import { countryAt, inverseLL, summitFeatures, toXYZ, type GlobeFeature } from "./picking";
import {
  ROBOT_H,
  animateRobot,
  buildArc,
  makeEventGroup,
  makeGMDrone,
  makeJudge,
  makeRobot,
  makeVerdictWave,
  placeEventGroup,
  setRobotMood,
  stepDrone,
  stepEventRings,
  stepVerdictWaves,
  type ArcHandle,
  type DroneState,
  type RobotHandle,
  type RobotMood,
} from "./robots";
import { TEX_H, TEX_W, createGlobePainter } from "./texture";

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
  /** Clic sur un pays du sommet (ou son délégué) → fiche. */
  onCountryClick?: (slug: string) => void;
  /** La caméra suit l'orateur. Le réglage appartient à l'hôte : `onUserDrag`
   * lui signale un drag pour qu'il coupe le suivi (sémantique prototype). */
  followSpeaker?: boolean;
  onUserDrag?: () => void;
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
  setEvent: () => void;
  setArc: () => void;
  verdict: () => void;
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

  // La boucle three et les handlers lisent toujours les DERNIÈRES props via la
  // ref, synchronisée hors rendu (règle react-hooks/refs). Déclaré en premier :
  // les effets suivants la trouvent à jour.
  useEffect(() => {
    propsRef.current = props;
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

    // Anneaux orbitaux décoratifs — la planète est un nœud technologique.
    const ring1 = new THREE.Mesh(
      new THREE.TorusGeometry(1.38, 0.0016, 8, 128),
      new THREE.MeshBasicMaterial({ color: 0x4ea8ff, transparent: true, opacity: 0.14 }),
    );
    ring1.rotation.x = Math.PI / 2.25;
    scene.add(ring1);
    const ring2 = new THREE.Mesh(
      new THREE.TorusGeometry(1.55, 0.0012, 8, 128),
      new THREE.MeshBasicMaterial({ color: 0x59e0c8, transparent: true, opacity: 0.09 }),
    );
    ring2.rotation.x = Math.PI / 1.8;
    ring2.rotation.y = 0.5;
    scene.add(ring2);

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

    // Halo atmosphérique (fresnel BackSide additif).
    const atmo = new THREE.Mesh(
      new THREE.SphereGeometry(1.055, 72, 48),
      new THREE.ShaderMaterial({
        side: THREE.BackSide,
        transparent: true,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
        vertexShader: `varying vec3 vN; void main(){ vN=normalize(normalMatrix*normal);
          gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}`,
        fragmentShader: `varying vec3 vN; void main(){
          float i=pow(0.72-dot(vN,vec3(0.,0.,1.)),3.2);
          gl_FragColor=vec4(0.36,0.65,1.0,1.0)*i*1.2;}`,
      }),
    );
    scene.add(atmo);

    // Texture du globe — peinte au chargement du fond 50m, puis aux
    // changements d'état seulement (`refresh`).
    const tcan = document.createElement("canvas");
    tcan.width = TEX_W;
    tcan.height = TEX_H;
    const tctx = tcan.getContext("2d")!;
    const texture = new THREE.CanvasTexture(tcan);
    texture.anisotropy = 4;
    texture.colorSpace = THREE.SRGBColorSpace;
    const globe = new THREE.Mesh(
      new THREE.SphereGeometry(1, 72, 48),
      new THREE.MeshBasicMaterial({ map: texture }),
    );
    scene.add(globe);

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

    // Les habitants du globe (S2) : délégués, drone GM, Juge, événement, arc.
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
    const { drone: gmDrone, beam: gmBeam } = makeGMDrone();
    scene.add(gmDrone);
    scene.add(gmBeam);
    let droneState: DroneState = { mode: "orbit", a: 0, t: 0, target: null };
    const judge = makeJudge(glowTexture("rgb(129,140,248)"));
    scene.add(judge.group);
    let judgeMode: { mode: "idle" | "verdict"; t: number } = { mode: "idle", t: 0 };
    let waves: ReturnType<typeof makeVerdictWave>[] = [];
    const eventGroup = makeEventGroup();
    scene.add(eventGroup.group);
    let arcHandle: ArcHandle | null = null;

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

    const PROJ = new THREE.Vector3();
    const CAMV = new THREE.Vector3();
    const LOC = new THREE.Vector3();
    const projectAt = (el: HTMLElement, pos: THREE.Vector3, visible: boolean, dy = 0): void => {
      if (!visible) {
        el.style.opacity = "0";
        return;
      }
      PROJ.copy(pos).project(camera);
      const behind =
        PROJ.z > 1 || pos.clone().normalize().dot(camera.position.clone().normalize()) < 0.12;
      const w = host.clientWidth;
      const h = host.clientHeight;
      el.style.left = `${((PROJ.x + 1) / 2) * w}px`;
      el.style.top = `${((-PROJ.y + 1) / 2) * h + dy}px`;
      el.style.opacity = behind ? "0" : "1";
    };

    // État interne de la scène (refs, pas de React).
    let cam: CamState = { ...CAM_HOME };
    let fly: CameraFly | null = null;
    let vlon = 0;
    let vlat = 0;
    let dragging = false;
    let moved = 0;
    let px = 0;
    let py = 0;
    let hoverT = 0;
    let dragSignaled = false;
    let painter: ReturnType<typeof createGlobePainter> | null = null;
    let feats: ReturnType<typeof summitFeatures> = [];
    let raf = 0;

    const summitTints = () => {
      const p = propsRef.current;
      return feats.map((f) => ({ ...f, u: p.uByCountry[f.slug] ?? p.utopia }));
    };

    const refresh = () => {
      if (!painter) return;
      const p = propsRef.current;
      feats = summitFeatures(p.countries, allFeatures);
      painter.paint(summitTints(), p.speaking ?? null);
      texture.needsUpdate = true;
      // Délégués : un robot par pays du sommet à capitale connue (un pays
      // inventé n'en a pas — règle existante, conservée).
      const want = new Set(p.countries.filter((c) => CAPITALS[c]));
      for (const [slug, r] of robots) {
        if (want.has(slug)) continue;
        scene.remove(r.group);
        robots.delete(slug);
      }
      for (const slug of want) {
        if (robots.has(slug)) continue;
        const meta = speakerMeta(slug);
        const r = makeRobot({
          slug,
          hue: meta.hue,
          lonlat: CAPITALS[slug],
          flagMap: flagTextureOf(slug),
        });
        scene.add(r.group);
        robots.set(slug, r);
      }
      const cap = p.speaking ? CAPITALS[p.speaking] : null;
      if (cap && p.speaking) {
        speakerGlow.position.set(...toXYZ(cap[0], cap[1], 1.008));
        speakerGlow.material.opacity = 0.95;
        speakerTag.textContent = `🗣 ${speakerMeta(p.speaking).label}`;
      } else {
        speakerGlow.material.opacity = 0;
      }
    };

    const flyToCountry = (slug: string) => {
      const cap = CAPITALS[slug];
      if (!cap || dragging) return;
      const target = { lon: cap[0], lat: cap[1] + SPEAKER_VIEW.latOffset, dist: SPEAKER_VIEW.dist };
      if (reduced) {
        cam = { lon: target.lon, lat: clampLat(target.lat), dist: target.dist };
        return;
      }
      fly = flyTowards(cam, target, 1.15);
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
        eventTag.style.opacity = "0";
        return;
      }
      placeEventGroup(eventGroup, p.eventGeo.lon, p.eventGeo.lat);
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
      }
      const a = propsRef.current.arc;
      if (!a || a.from === a.to) return;
      const from = CAPITALS[a.from];
      const to = CAPITALS[a.to];
      if (!from || !to) return;
      arcHandle = buildArc(from, to);
      scene.add(arcHandle.line);
      scene.add(arcHandle.pulse);
    };

    // Verdict : le Juge s'emballe, onde planétaire, plan large « au-dessus
    // de la mêlée ».
    const verdict = () => {
      judgeMode = { mode: "verdict", t: 0 };
      judgeTag.textContent = "⚖ Le Juge délibère";
      if (!reduced) {
        const w = makeVerdictWave();
        scene.add(w);
        waves.push(w);
      }
      const p = propsRef.current;
      if ((p.followSpeaker ?? true) && !dragging) {
        if (reduced) cam = { ...cam, lat: JUDGE_VIEW.lat, dist: JUDGE_VIEW.dist };
        else fly = flyTowards(cam, { lon: cam.lon, lat: JUDGE_VIEW.lat, dist: JUDGE_VIEW.dist }, 1.5);
      }
    };

    let allFeatures: GlobeFeature[] = [];
    loadFeatures50m().then((loaded) => {
      if (dead) return;
      allFeatures = loaded;
      painter = createGlobePainter({ ctx: tctx, features: allFeatures });
      refresh();
      setEvent();
      setArc();
      handleRef.current = { refresh, flyToCountry, setEvent, setArc, verdict };
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
    // Robots d'abord (gros hitbox), sinon la sphère → lon/lat → geoContains.
    const slugAt = (e: PointerEvent | MouseEvent): string | null => {
      if (!setRay(e)) return null;
      const pool = [...robots.values()].map((r) => r.group);
      const robotHit = ray.intersectObjects(pool, true)[0];
      if (robotHit) {
        let o: THREE.Object3D | null = robotHit.object;
        while (o && !o.userData.slug) o = o.parent;
        if (o) return o.userData.slug as string;
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
      vlon = -dx * 0.22;
      vlat = dy * 0.22;
      cam = { ...cam, lon: cam.lon + vlon, lat: clampLat(cam.lat + vlat) };
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
        tooltip.textContent = `${speakerMeta(slug).label} — clic : fiche du délégué`;
        tooltip.style.left = `${e.clientX - r.left}px`;
        tooltip.style.top = `${e.clientY - r.top}px`;
        tooltip.style.opacity = "1";
      } else {
        tooltip.style.opacity = "0";
      }
    };
    const onClick = (e: MouseEvent) => {
      if (moved > 6) return;
      const slug = slugAt(e);
      if (slug) propsRef.current.onCountryClick?.(slug);
    };
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      cam = zoomBy(cam, Math.sign(e.deltaY));
    };

    renderer.domElement.addEventListener("pointerdown", onPointerDown);
    renderer.domElement.addEventListener("pointermove", onHover);
    renderer.domElement.addEventListener("click", onClick);
    renderer.domElement.addEventListener("wheel", onWheel, { passive: false });
    window.addEventListener("pointerup", onPointerUp);
    window.addEventListener("pointermove", onWindowMove);

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

      if (!dragging) {
        vlon *= Math.pow(0.05, dt);
        vlat *= Math.pow(0.05, dt);
        if (Math.abs(vlon) > 0.002 || Math.abs(vlat) > 0.002) {
          cam = { ...cam, lon: cam.lon + vlon, lat: clampLat(cam.lat + vlat) };
        }
      }
      if (fly) {
        const step = stepFly(cam, fly, dt);
        cam = step.cam;
        fly = step.fly;
      }
      camera.position.set(...camPosition(cam));
      camera.lookAt(0, 0, 0);

      const t = clock.elapsedTime;
      const p = propsRef.current;

      // Drone GM (orbite ↔ annonce) et Juge (idle ↔ verdict + ondes).
      droneState = stepDrone(gmDrone, gmBeam, droneState, dt);
      const verdictOn = judgeMode.mode === "verdict";
      judge.core.rotation.y += dt * (verdictOn ? 1.6 : 0.35);
      judge.ringA.rotation.z += dt * (verdictOn ? 1.8 : 0.3);
      judge.ringB.rotation.z -= dt * (verdictOn ? 1.4 : 0.22);
      judge.group.position.y = 1.72 + (reduced ? 0 : Math.sin(t * 0.9) * 0.02);
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
      const aliveWaves = stepVerdictWaves(waves, dt);
      for (const w of waves) {
        if (aliveWaves.includes(w)) continue;
        scene.remove(w);
        w.geometry.dispose();
        w.material.dispose();
      }
      waves = aliveWaves;

      // Délégués : humeur (suspendu > pense > parle > repos) + face caméra.
      const suspendedSet = new Set(p.suspended ?? []);
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
      }

      // Anneau d'événement, arc voyageur, glow d'orateur.
      if (eventGroup.group.visible) {
        stepEventRings(eventGroup.rings, t, !reduced && (p.pulse ?? false));
      }
      if (arcHandle) {
        const k = reduced ? 0.5 : (t * 0.55) % 1;
        arcHandle.pulse.position.copy(arcHandle.curve.getPointAt(k));
      }
      if (p.speaking && !reduced) {
        speakerGlow.material.opacity = 0.7 + Math.sin(t * 3.2) * 0.2;
      }

      // Étiquettes projetées (DOM piloté par la boucle).
      projectAt(eventTag, eventGroup.group.position, eventGroup.group.visible, -14);
      const spk = p.speaking ? robots.get(p.speaking) : undefined;
      if (spk) {
        LOC.copy(spk.group.position).normalize().multiplyScalar(1 + ROBOT_H * 1.12);
        projectAt(speakerTag, LOC, true, 8);
      } else {
        speakerTag.style.opacity = "0";
      }
      projectAt(judgeTag, judge.group.position, judgeMode.mode === "verdict", -10);

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
      for (const el of [tooltip, eventTag, speakerTag, judgeTag]) el.remove();
      renderer.domElement.remove();
    };
    // Montage unique : les changements d'état passent par l'effet ci-dessous.
  }, []);

  // Changements d'état de jeu → repeindre / suivre l'orateur (via la poignée,
  // jamais de setState : la boucle three reste seule maîtresse du temps).
  useEffect(() => {
    const h = handleRef.current;
    if (!h) return;
    h.refresh();
    const target = speaking ?? thinking;
    if (target && followSpeaker) h.flyToCountry(target);
  }, [tintKey, speaking, thinking, followSpeaker]);

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

  return (
    <div
      ref={hostRef}
      role="img"
      aria-label="Théâtre du sommet — planète interactive (décorative pour lecteurs d'écran)"
      className={props.className ?? "relative h-full w-full overflow-hidden"}
      style={{ position: "relative", overflow: "hidden", touchAction: "none" }}
    />
  );
}
