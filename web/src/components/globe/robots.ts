/** Les habitants du globe (spec théâtre-globe §1, §6) — délégués humanoïdes,
 * drone Game Master, entité Juge, anneau d'événement, arcs diplomatiques.
 *
 * Transposition du prototype maison (docs/prototypes/theatre-globe.html) :
 * mêmes proportions, mêmes états. Construction et machines à états vivent ici
 * (three pur, testable en node) ; le rendu, la caméra et le DOM restent dans
 * `globe-stage.tsx`. Les textures canvas (drapeau, halo) sont INJECTÉES :
 * aucun accès document ici. Metalness ≤ .25 — un métal élevé sans envMap rend
 * noir (leçon du prototype). */

import * as THREE from "three";

import { toXYZ } from "./picking";

export const ROBOT_SCALE = 1.7;
/** Hauteur utile du délégué (ancrage des étiquettes projetées). */
export const ROBOT_H = 0.105;

const PANEL_COLOR = "#cdd9ec";
const DARK_COLOR = "#46587a";
const SUSPENDED_PANEL = "#6f7684";
const SUSPENDED_DARK = "#3c4250";
const EYE_CYAN = "#59d7ff";
const EYE_AMBER = "#ffc14d";
const EYE_OFF = "#9ca3af";

export type RobotMood = "idle" | "thinking" | "speaking" | "suspended";

export type RobotHandle = {
  slug: string;
  group: THREE.Group;
  /** Pivot face caméra (le corps entier tourne sans décoller du sol). */
  spinner: THREE.Group;
  head: THREE.Group;
  eyes: THREE.Mesh<THREE.SphereGeometry, THREE.MeshBasicMaterial>[];
  armL: THREE.Group;
  armR: THREE.Group;
  base: THREE.Mesh<THREE.CylinderGeometry, THREE.MeshBasicMaterial>;
  /** Voile bleuté au sol : le délégué est trompé (fog). */
  veil: THREE.Mesh<THREE.CircleGeometry, THREE.MeshBasicMaterial>;
  /** Cadenas au sol : le délégué est suspendu (au banc). */
  lock: THREE.Group;
  mats: { panel: THREE.MeshStandardMaterial; dark: THREE.MeshStandardMaterial };
  mood: RobotMood;
};

export function makeRobot(opts: {
  slug: string;
  hue: string;
  lonlat: [number, number];
  flagMap: THREE.Texture | null;
}): RobotHandle {
  const { slug, hue, lonlat, flagMap } = opts;
  // Matériaux par robot (pas partagés) : la suspension grise CE délégué.
  const panel = new THREE.MeshStandardMaterial({ color: PANEL_COLOR, metalness: 0.2, roughness: 0.48 });
  const dark = new THREE.MeshStandardMaterial({ color: DARK_COLOR, metalness: 0.25, roughness: 0.55 });
  const visor = new THREE.MeshStandardMaterial({ color: "#0b1322", metalness: 0.9, roughness: 0.18 });

  const group = new THREE.Group();
  const spinner = new THREE.Group();
  group.add(spinner);
  const add = <T extends THREE.Object3D>(obj: T, x: number, y: number, z: number): T => {
    obj.position.set(x, y, z);
    spinner.add(obj);
    return obj;
  };

  // Jambes et pieds.
  for (const s of [-1, 1]) {
    add(new THREE.Mesh(new THREE.CylinderGeometry(0.0028, 0.0033, 0.016, 10), dark), s * 0.0055, 0.011, 0);
    add(new THREE.Mesh(new THREE.BoxGeometry(0.006, 0.003, 0.0095), panel), s * 0.0055, 0.0015, 0.001);
  }
  // Bassin, torse, sac dorsal, drapeau au torse.
  add(new THREE.Mesh(new THREE.BoxGeometry(0.0145, 0.005, 0.008), dark), 0, 0.0205, 0);
  add(new THREE.Mesh(new THREE.CylinderGeometry(0.0108, 0.0078, 0.019, 14), panel), 0, 0.0325, 0);
  add(new THREE.Mesh(new THREE.BoxGeometry(0.009, 0.011, 0.0045), dark), 0, 0.033, -0.0095);
  add(
    new THREE.Mesh(
      new THREE.PlaneGeometry(0.0125, 0.0085),
      flagMap
        ? new THREE.MeshBasicMaterial({ map: flagMap })
        : new THREE.MeshBasicMaterial({ color: hue }),
    ),
    0,
    0.0335,
    0.0102,
  );
  // Bras articulés aux épaules.
  const arms: Record<"L" | "R", THREE.Group> = { L: new THREE.Group(), R: new THREE.Group() };
  for (const s of [-1, 1] as const) {
    add(new THREE.Mesh(new THREE.SphereGeometry(0.004, 10, 8), dark), s * 0.0128, 0.0392, 0);
    const arm = new THREE.Group();
    arm.position.set(s * 0.0128, 0.0392, 0);
    const upper = new THREE.Mesh(new THREE.CylinderGeometry(0.0024, 0.0022, 0.0125, 8), panel);
    upper.position.y = -0.0065;
    arm.add(upper);
    const fore = new THREE.Mesh(new THREE.CylinderGeometry(0.0021, 0.0019, 0.011, 8), dark);
    fore.position.y = -0.0178;
    arm.add(fore);
    const hand = new THREE.Mesh(new THREE.SphereGeometry(0.0029, 8, 8), panel);
    hand.position.y = -0.0245;
    arm.add(hand);
    arm.rotation.z = s * 0.14;
    spinner.add(arm);
    arms[s < 0 ? "L" : "R"] = arm;
  }
  // Cou, tête (crâne, visière, yeux, antenne à la teinte du pays).
  add(new THREE.Mesh(new THREE.CylinderGeometry(0.003, 0.003, 0.004, 8), dark), 0, 0.0442, 0);
  const head = new THREE.Group();
  head.position.set(0, 0.0518, 0);
  spinner.add(head);
  const skull = new THREE.Mesh(new THREE.SphereGeometry(0.0094, 18, 14), panel);
  skull.scale.set(1, 0.94, 0.9);
  head.add(skull);
  const visorMesh = new THREE.Mesh(new THREE.BoxGeometry(0.0136, 0.0054, 0.0022), visor);
  visorMesh.position.set(0, 0.0005, 0.0082);
  head.add(visorMesh);
  const eyes = [-1, 1].map((s) => {
    const e = new THREE.Mesh(
      new THREE.SphereGeometry(0.00165, 8, 8),
      new THREE.MeshBasicMaterial({ color: EYE_CYAN }),
    );
    e.position.set(s * 0.0033, 0.0005, 0.0094);
    head.add(e);
    return e;
  });
  const ant = new THREE.Mesh(new THREE.CylinderGeometry(0.0008, 0.0008, 0.0085, 6), dark);
  ant.position.set(0, 0.0128, 0);
  head.add(ant);
  const tip = new THREE.Mesh(
    new THREE.SphereGeometry(0.0026, 8, 8),
    new THREE.MeshBasicMaterial({ color: hue }),
  );
  tip.position.set(0, 0.0178, 0);
  head.add(tip);
  // Socle lumineux.
  const base = new THREE.Mesh(
    new THREE.CylinderGeometry(0.0155, 0.0175, 0.0024, 22),
    new THREE.MeshBasicMaterial({ color: hue, transparent: true, opacity: 0.4 }),
  );
  base.position.y = 0.0012;
  spinner.add(base);
  // Voile de brouillard au sol (fog) — éteint par défaut.
  const veil = new THREE.Mesh(
    new THREE.CircleGeometry(0.024, 24),
    new THREE.MeshBasicMaterial({
      color: "#3b82f6",
      transparent: true,
      opacity: 0.3,
      side: THREE.DoubleSide,
      depthWrite: false,
    }),
  );
  veil.rotation.x = -Math.PI / 2;
  veil.position.y = 0.0008;
  veil.visible = false;
  spinner.add(veil);
  // Cadenas au sol (suspension) — éteint par défaut.
  const lock = new THREE.Group();
  const lockBody = new THREE.Mesh(
    new THREE.BoxGeometry(0.008, 0.0066, 0.003),
    new THREE.MeshBasicMaterial({ color: "#cbd5e1" }),
  );
  lockBody.position.y = 0.0033;
  lock.add(lockBody);
  const shackle = new THREE.Mesh(
    new THREE.TorusGeometry(0.0028, 0.0007, 6, 12, Math.PI),
    new THREE.MeshBasicMaterial({ color: "#cbd5e1" }),
  );
  shackle.position.y = 0.0068;
  lock.add(shackle);
  lock.position.set(0.02, 0, 0.004);
  lock.visible = false;
  spinner.add(lock);

  // Ancrage : debout sur la capitale, +Y aligné sur la normale au sol.
  const p = new THREE.Vector3(...toXYZ(lonlat[0], lonlat[1], 1.001));
  group.position.copy(p);
  group.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), p.clone().normalize());
  group.scale.setScalar(ROBOT_SCALE);
  group.userData.slug = slug;

  return {
    slug,
    group,
    spinner,
    head,
    eyes,
    armL: arms.L,
    armR: arms.R,
    base,
    veil,
    lock,
    mats: { panel, dark },
    mood: "idle",
  };
}

/** État discret : matériaux, cadenas. Idempotent, appelé au changement. */
export function setRobotMood(r: RobotHandle, mood: RobotMood): void {
  r.mood = mood;
  const suspended = mood === "suspended";
  r.mats.panel.color.set(suspended ? SUSPENDED_PANEL : PANEL_COLOR);
  r.mats.dark.color.set(suspended ? SUSPENDED_DARK : DARK_COLOR);
  r.lock.visible = suspended;
  if (suspended) {
    for (const e of r.eyes) e.material.color.set(EYE_OFF);
    r.spinner.position.y = 0;
    r.spinner.scale.setScalar(1);
    r.head.rotation.x = 0;
    r.armL.rotation.z = 0.14;
    r.armR.rotation.z = -0.14;
    r.base.material.opacity = 0.22;
  }
}

/** États continus (bob, bond, salut, pulsation des yeux) — boucle three. */
export function animateRobot(r: RobotHandle, t: number, reduced: boolean): void {
  if (r.mood === "suspended") return; // immobile, au banc
  const isSpk = r.mood === "speaking";
  const isThk = r.mood === "thinking";
  const bob = reduced ? 0 : Math.sin(t * 2.2 + r.group.position.x * 30) * 0.0009;
  r.spinner.position.y = bob + (isSpk && !reduced ? Math.abs(Math.sin(t * 5)) * 0.0018 : 0);
  const s = isSpk || isThk ? 1.22 : 1;
  r.spinner.scale.setScalar(s + (isSpk && !reduced ? Math.sin(t * 6) * 0.025 : 0));
  const eyeCol = isSpk ? EYE_AMBER : EYE_CYAN;
  const ep = reduced ? 1 : isThk ? 0.7 + Math.sin(t * 8) * 0.3 : isSpk ? 0.8 + Math.sin(t * 10) * 0.2 : 1;
  for (const e of r.eyes) {
    e.material.color.set(eyeCol);
    e.scale.setScalar(ep);
  }
  r.head.rotation.x = isThk ? -0.18 + (reduced ? 0 : Math.sin(t * 3) * 0.05) : 0;
  r.armR.rotation.z = isSpk && !reduced ? -0.25 + Math.sin(t * 7) * 0.55 : -0.14;
  r.armL.rotation.z = isSpk && !reduced ? 0.2 + Math.sin(t * 7 + 1.2) * 0.18 : 0.14;
  r.base.material.opacity = isSpk ? 0.85 : isThk ? 0.68 : 0.4;
}

// --- drone Game Master --------------------------------------------------------

export type DroneState = {
  mode: "orbit" | "announce";
  a: number;
  t: number;
  target: THREE.Vector3 | null;
};

export function makeGMDrone(): {
  drone: THREE.Group;
  ring: THREE.Mesh;
  beam: THREE.Mesh<THREE.ConeGeometry, THREE.MeshBasicMaterial>;
} {
  const drone = new THREE.Group();
  const core = new THREE.Mesh(
    new THREE.SphereGeometry(0.012, 14, 12),
    new THREE.MeshBasicMaterial({ color: "#ffd98a" }),
  );
  drone.add(core);
  const ring = new THREE.Mesh(
    new THREE.TorusGeometry(0.024, 0.0028, 10, 36),
    new THREE.MeshBasicMaterial({ color: "#ffc14d" }),
  );
  ring.rotation.x = Math.PI / 2;
  drone.add(ring);
  const fin = new THREE.Mesh(
    new THREE.ConeGeometry(0.006, 0.014, 10),
    new THREE.MeshStandardMaterial({ color: DARK_COLOR, metalness: 0.25, roughness: 0.55 }),
  );
  fin.position.y = 0.02;
  drone.add(fin);
  const beam = new THREE.Mesh(
    new THREE.ConeGeometry(0.05, 1, 20, 1, true),
    new THREE.MeshBasicMaterial({
      color: 0xffc14d,
      transparent: true,
      opacity: 0,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
      side: THREE.DoubleSide,
    }),
  );
  return { drone, ring, beam };
}

/** Une frame du drone : orbite haute, ou descente + faisceau vers le lieu.
 * Lerp indépendant du framerate (1−e^(−k·dt)), retour en orbite après 4,5 s. */
export function stepDrone(
  drone: THREE.Group,
  beam: THREE.Mesh<THREE.ConeGeometry, THREE.MeshBasicMaterial>,
  state: DroneState,
  dt: number,
): DroneState {
  if (state.mode === "orbit" || !state.target) {
    const a = state.a + dt * 0.25;
    drone.position.set(Math.cos(a) * 1.6, 0.55 * Math.sin(a * 0.7), Math.sin(a) * 1.6);
    beam.material.opacity = Math.max(0, beam.material.opacity - dt * 1.5);
    drone.lookAt(0, 0, 0);
    return { ...state, mode: "orbit", a };
  }
  const t = state.t + dt;
  const hover = state.target.clone().normalize().multiplyScalar(1.22);
  drone.position.lerp(hover, 1 - Math.exp(-2.2 * dt));
  const dir = drone.position.clone().sub(state.target);
  const len = dir.length();
  beam.scale.set(1, len, 1);
  beam.position.copy(state.target.clone().add(dir.multiplyScalar(0.5)));
  beam.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir.normalize());
  beam.material.opacity = Math.min(0.22, beam.material.opacity + dt * 0.4);
  drone.lookAt(0, 0, 0);
  if (t > 4.5) return { ...state, mode: "orbit", a: Math.atan2(drone.position.z, drone.position.x), t: 0 };
  return { ...state, t };
}

// --- le Juge — entité supérieure au-dessus du monde ---------------------------

export type JudgeHandle = {
  group: THREE.Group;
  core: THREE.Mesh<THREE.OctahedronGeometry, THREE.MeshStandardMaterial>;
  ringA: THREE.Mesh;
  ringB: THREE.Mesh;
  halo: THREE.Sprite | null;
};

export function makeJudge(haloMap: THREE.Texture | null): JudgeHandle {
  const group = new THREE.Group();
  const core = new THREE.Mesh(
    new THREE.OctahedronGeometry(0.052, 0),
    new THREE.MeshStandardMaterial({
      color: "#c7d2fe",
      metalness: 0.4,
      roughness: 0.25,
      emissive: "#6366f1",
      emissiveIntensity: 0.55,
    }),
  );
  group.add(core);
  const inner = new THREE.Mesh(
    new THREE.OctahedronGeometry(0.024, 0),
    new THREE.MeshBasicMaterial({ color: "#eef2ff" }),
  );
  group.add(inner);
  const ringA = new THREE.Mesh(
    new THREE.TorusGeometry(0.115, 0.0035, 10, 48),
    new THREE.MeshBasicMaterial({ color: "#818cf8", transparent: true, opacity: 0.8 }),
  );
  ringA.rotation.x = Math.PI / 2;
  group.add(ringA);
  const ringB = new THREE.Mesh(
    new THREE.TorusGeometry(0.082, 0.0025, 10, 44),
    new THREE.MeshBasicMaterial({ color: "#a5b4fc", transparent: true, opacity: 0.6 }),
  );
  ringB.rotation.x = Math.PI / 2.6;
  ringB.rotation.y = 0.6;
  group.add(ringB);
  let halo: THREE.Sprite | null = null;
  if (haloMap) {
    halo = new THREE.Sprite(
      new THREE.SpriteMaterial({
        map: haloMap,
        transparent: true,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
        opacity: 0.5,
      }),
    );
    halo.scale.setScalar(0.42);
    group.add(halo);
  }
  group.position.set(0, 1.72, 0);
  return { group, core, ringA, ringB, halo };
}

/** L'onde planétaire du verdict : une sphère BackSide additive qui enfle. */
export function makeVerdictWave(): THREE.Mesh<THREE.SphereGeometry, THREE.MeshBasicMaterial> {
  const w = new THREE.Mesh(
    new THREE.SphereGeometry(1, 48, 32),
    new THREE.MeshBasicMaterial({
      color: 0x818cf8,
      transparent: true,
      opacity: 0.2,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
      side: THREE.BackSide,
    }),
  );
  w.scale.setScalar(1.02);
  return w;
}

/** Fait vivre les ondes ; rend celles encore visibles (les mortes sont à
 * retirer de la scène par l'appelant). */
export function stepVerdictWaves(
  waves: THREE.Mesh<THREE.SphereGeometry, THREE.MeshBasicMaterial>[],
  dt: number,
): THREE.Mesh<THREE.SphereGeometry, THREE.MeshBasicMaterial>[] {
  const alive: typeof waves = [];
  for (const w of waves) {
    const s = w.scale.x + dt * 0.28;
    w.scale.setScalar(s);
    w.material.opacity = Math.max(0, 0.2 * (1 - (s - 1.02) / 0.55));
    if (w.material.opacity > 0) alive.push(w);
  }
  return alive;
}

// --- anneau d'événement --------------------------------------------------------

export type EventGroupHandle = {
  group: THREE.Group;
  rings: THREE.Mesh<THREE.RingGeometry, THREE.MeshBasicMaterial>[];
  core: THREE.Mesh;
};

export function makeEventGroup(): EventGroupHandle {
  const group = new THREE.Group();
  const rings = [0, 1].map((i) => {
    const m = new THREE.Mesh(
      new THREE.RingGeometry(0.016, 0.021, 48),
      new THREE.MeshBasicMaterial({
        color: 0xffc14d,
        transparent: true,
        side: THREE.DoubleSide,
        depthWrite: false,
      }),
    );
    m.userData.phase = i * 0.5;
    group.add(m);
    return m;
  });
  const core = new THREE.Mesh(
    new THREE.SphereGeometry(0.011, 12, 12),
    new THREE.MeshBasicMaterial({ color: 0xffd98a }),
  );
  group.add(core);
  group.visible = false;
  return { group, rings, core };
}

export function placeEventGroup(ev: EventGroupHandle, lon: number, lat: number): void {
  const p = new THREE.Vector3(...toXYZ(lon, lat, 1.004));
  ev.group.position.copy(p);
  ev.group.lookAt(p.clone().multiplyScalar(2));
}

/** Pulsation des anneaux ; `pulse` faux (relecture, round clos) → état figé. */
export function stepEventRings(
  rings: EventGroupHandle["rings"],
  t: number,
  pulse: boolean,
): void {
  for (const rg of rings) {
    if (!pulse) {
      rg.scale.setScalar(3);
      rg.material.opacity = 0.5;
      continue;
    }
    const ph = (t * 0.9 + (rg.userData.phase as number)) % 1;
    rg.scale.setScalar(1 + ph * 7);
    rg.material.opacity = (1 - ph) * 0.85;
  }
}

// --- arc diplomatique orateur → destinataire -----------------------------------

export type ArcHandle = {
  curve: THREE.QuadraticBezierCurve3;
  line: THREE.Line;
  pulse: THREE.Mesh;
};

export function buildArc(from: [number, number], to: [number, number]): ArcHandle {
  const a = new THREE.Vector3(...toXYZ(from[0], from[1], 1.004));
  const b = new THREE.Vector3(...toXYZ(to[0], to[1], 1.004));
  const mid = a
    .clone()
    .add(b)
    .multiplyScalar(0.5)
    .normalize()
    .multiplyScalar(1.05 + a.distanceTo(b) * 0.35);
  const curve = new THREE.QuadraticBezierCurve3(a, mid, b);
  const line = new THREE.Line(
    new THREE.BufferGeometry().setFromPoints(curve.getPoints(72)),
    new THREE.LineBasicMaterial({ color: 0xffc14d, transparent: true, opacity: 0.6 }),
  );
  const pulse = new THREE.Mesh(
    new THREE.SphereGeometry(0.007, 10, 10),
    new THREE.MeshBasicMaterial({ color: 0xffe0a3 }),
  );
  return { curve, line, pulse };
}
