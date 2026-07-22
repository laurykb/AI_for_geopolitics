/** Le dépliage sphère ⇄ carte (spec théâtre-globe §1/§5 — décision full-three,
 * 2026-07-21) : UNE seule scène pour les deux vues, le 2D est le même monde
 * qui se déplie.
 *
 * Ici vivent les maths pures du morph, transposées du prototype :
 * - le plan équirectangulaire 2:1 (`planeXYZ`) et l'avancée du morph ;
 * - les ANCRES : tout objet « posé sur le monde » (délégué, anneau, pile)
 *   interpole position (lerp) ET orientation (slerp) entre ses deux repères ;
 * - les points MIXTES : les objets volants (drone, satellite) gardent leur
 *   machine à états en espace sphère et sont re-projetés au rendu ;
 * - la caméra plate : vue oblique « table tactique » (une vue de face
 *   perpendiculaire réduirait les délégués debout à des têtes), pan/zoom
 *   bornés à la carte, bascule qui PRÉSERVE le point de vue ;
 * - l'arc diplomatique reconstruit selon le morph.
 * Le vertex shader du globe (`uFlat`) vit dans globe-stage ; lui et ces
 * fonctions doivent déplier vers le MÊME plan. */

import * as THREE from "three";

import { clampDist, clampLat, easeInOutCubic, type CamState } from "./camera";
import { inverseLL, toXYZ } from "./picking";

/** Carte dépliée 2:1 (rayon 1) : x ∈ [−π, π], y ∈ [−π/2, π/2], z = altitude. */
export const FLAT_W = Math.PI * 2;
export const FLAT_H = Math.PI;

/** lon/lat (degrés) → point de la carte dépliée, `lift` au-dessus du plan. */
export function planeXYZ(lon: number, lat: number, lift = 0): [number, number, number] {
  return [(lon / 180) * (FLAT_W / 2), (lat / 90) * (FLAT_H / 2), lift];
}

/** Redresse un objet Y-up (délégué) : à plat, sa tête pointe vers la caméra. */
export const Q_FLAT = new THREE.Quaternion().setFromUnitVectors(
  new THREE.Vector3(0, 1, 0),
  new THREE.Vector3(0, 0, 1),
);
/** Orientation « au sol » : un anneau posé à plat garde son +Z vers le ciel. */
export const Q_ID = new THREE.Quaternion();

/** Avance du dépliage : lissage indépendant du framerate, collé en butée. */
export function stepMorph(k: number, target: number, dt: number): number {
  if (k === target) return k;
  const next = k + (target - k) * (1 - Math.exp(-3.4 * dt));
  return Math.abs(next - target) < 0.004 ? target : next;
}

type AnchorData = {
  pS: THREE.Vector3;
  qS: THREE.Quaternion;
  pF: THREE.Vector3;
  qF: THREE.Quaternion;
};

/** Registre des objets posés sur le monde : `apply(k)` les place chaque frame
 * (les ancres créées en plein dépliage se placent donc aussi). */
export class AnchorRegistry {
  private anchors = new Map<THREE.Object3D, AnchorData>();

  /** (Ré)ancre l'objet à lon/lat. `flatQ` : Q_FLAT debout (défaut), Q_ID au sol. */
  anchor(
    obj: THREE.Object3D,
    lon: number,
    lat: number,
    opts: { lift?: number; flatQ?: THREE.Quaternion } = {},
  ): void {
    const { lift = 0.001, flatQ = Q_FLAT } = opts;
    const pS = new THREE.Vector3(...toXYZ(lon, lat, 1 + lift));
    const normal = pS.clone().normalize();
    // Sur la sphère : un objet debout aligne +Y sur la normale ; un objet au
    // sol (Q_ID à plat) aligne +Z dessus (il « regarde le ciel »).
    const qS =
      flatQ === Q_ID
        ? new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 0, 1), normal)
        : new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), normal);
    this.anchors.set(obj, {
      pS,
      qS,
      pF: new THREE.Vector3(...planeXYZ(lon, lat, lift)),
      qF: flatQ,
    });
    obj.position.copy(pS);
    obj.quaternion.copy(qS);
  }

  remove(obj: THREE.Object3D): void {
    this.anchors.delete(obj);
  }

  get size(): number {
    return this.anchors.size;
  }

  apply(k: number): void {
    for (const [obj, a] of this.anchors) {
      obj.position.lerpVectors(a.pS, a.pF, k);
      obj.quaternion.slerpQuaternions(a.qS, a.qF, k);
    }
  }
}

/** Position mixte d'un point d'ESPACE SPHÈRE quelconque (drone, satellite) :
 * l'altitude au-dessus du globe devient l'altitude au-dessus de la carte. */
export function mixPoint(sphereP: THREE.Vector3, k: number, out: THREE.Vector3): THREE.Vector3 {
  if (k <= 0) return out.copy(sphereP);
  const ll = inverseLL([sphereP.x, sphereP.y, sphereP.z]);
  const alt = Math.max(0, sphereP.length() - 1);
  return out.copy(sphereP).lerp(new THREE.Vector3(...planeXYZ(ll[0], ll[1], alt)), k);
}

/** Point « haut » d'une étiquette : rayon `liftS` sur la sphère ⇄ altitude
 * `liftF` sur la carte. */
export function mixTop(
  ll: [number, number],
  liftS: number,
  liftF: number,
  k: number,
  out: THREE.Vector3,
): THREE.Vector3 {
  out.set(...toXYZ(ll[0], ll[1], liftS));
  if (k <= 0) return out;
  return out.lerp(new THREE.Vector3(...planeXYZ(ll[0], ll[1], liftF)), k);
}

/** L'arc orateur → destinataire, reconstruit pour l'état de morph courant :
 * bombé au-dessus de la sphère à k=0, planant au-dessus de la carte à k=1. */
export function arcCurveAt(
  from: [number, number],
  to: [number, number],
  k: number,
): THREE.QuadraticBezierCurve3 {
  const a = mixTop(from, 1.004, 0.004, k, new THREE.Vector3());
  const b = mixTop(to, 1.004, 0.004, k, new THREE.Vector3());
  const d = a.distanceTo(b);
  const midS = a
    .clone()
    .add(b)
    .multiplyScalar(0.5)
    .normalize()
    .multiplyScalar(1.05 + d * 0.35);
  const midF = a.clone().add(b).multiplyScalar(0.5);
  midF.z = 0.06 + d * 0.3;
  return new THREE.QuadraticBezierCurve3(a, midS.lerp(midF, k), b);
}

// --- caméra plate (vue oblique « table tactique ») ---------------------------

export type FlatCamState = { x: number; y: number; dist: number };

export const FLAT_DIST_MIN = 0.7;
export const FLAT_DIST_MAX = 6.5;
/** Cadrages à plat du prototype (orateur serré, événement large, Juge global). */
export const FLAT_SPEAKER_DIST = 1.35;
export const FLAT_EVENT_DIST = 2.0;
export const FLAT_JUDGE_VIEW = { lon: 0, lat: 14, dist: 4.6 };

export function clampFlat(f: FlatCamState): FlatCamState {
  return {
    x: Math.max(-FLAT_W / 2, Math.min(FLAT_W / 2, f.x)),
    y: Math.max(-FLAT_H / 2, Math.min(FLAT_H / 2, f.y)),
    dist: Math.max(FLAT_DIST_MIN, Math.min(FLAT_DIST_MAX, f.dist)),
  };
}

/** Pose oblique : caméra en retrait SOUS la cible, qui vise un point au-delà —
 * la carte se lit et les délégués restent debout et lisibles. */
export function flatCameraPose(f: FlatCamState): {
  position: [number, number, number];
  target: [number, number, number];
} {
  return {
    position: [f.x, f.y - f.dist * 0.42, f.dist * 0.9],
    target: [f.x, f.y + f.dist * 0.1, 0],
  };
}

/** Monde par pixel à plat (fov 42° → demi-angle 21°) : le drag suit le doigt. */
export function flatWorldPerPixel(dist: number, viewportHeightPx: number): number {
  return (2 * dist * Math.tan((21 * Math.PI) / 180)) / viewportHeightPx;
}

/** Bascule 3D→2D : le point de vue orbital devient un cadrage plat équivalent. */
export function enterFlatView(cam: CamState): FlatCamState {
  return clampFlat({
    x: planeXYZ(cam.lon, 0)[0],
    y: planeXYZ(0, Math.max(-70, Math.min(70, cam.lat)))[1],
    dist: Math.max(1.1, Math.min(5.5, cam.dist * 1.35)),
  });
}

/** Bascule 2D→3D : l'inverse exact (aux bornes près) — le regard ne saute pas. */
export function exitFlatView(f: FlatCamState): CamState {
  return {
    lon: (f.x / (FLAT_W / 2)) * 180,
    lat: clampLat((f.y / (FLAT_H / 2)) * 90),
    dist: clampDist(f.dist / 1.35),
  };
}

export type FlatFly = {
  t: number;
  dur: number;
  from: FlatCamState;
  d: FlatCamState;
};

/** Vol plané vers un lieu de la carte (cible en lon/lat, altitude = dist). */
export function flatFlyTowards(
  f: FlatCamState,
  target: { lon: number; lat: number; dist: number },
  dur = 1.1,
): FlatFly {
  const [x, y] = planeXYZ(target.lon, target.lat);
  return {
    t: 0,
    dur,
    from: { ...f },
    d: { x: x - f.x, y: y - f.y, dist: target.dist - f.dist },
  };
}

export function stepFlatFly(
  f: FlatCamState,
  fly: FlatFly,
  dt: number,
): { fcam: FlatCamState; fly: FlatFly | null } {
  const t = fly.t + dt;
  const k = easeInOutCubic(Math.min(1, t / fly.dur));
  const fcam = clampFlat({
    x: fly.from.x + fly.d.x * k,
    y: fly.from.y + fly.d.y * k,
    dist: fly.from.dist + fly.d.dist * k,
  });
  if (t >= fly.dur) {
    return {
      fcam: clampFlat({
        x: fly.from.x + fly.d.x,
        y: fly.from.y + fly.d.y,
        dist: fly.from.dist + fly.d.dist,
      }),
      fly: null,
    };
  }
  return { fcam, fly: { ...fly, t } };
}
