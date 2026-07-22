/** Caméra orbitale du globe (spec théâtre-globe §2) — état PUR {lon,lat,dist}.
 *
 * Bornes du prototype (dist 1.28–4.6, lat ±72° : la vue reste trois-quarts,
 * jamais zénithale), zoom par crans de 9 %, fly-to easeInOutCubic avancé en
 * temps réel (dt) et chemin le plus court à travers l'antiméridien. La scène
 * three ne fait qu'appliquer `camPosition` — aucune animation par setState. */

import { toXYZ } from "./picking";

export type CamState = { lon: number; lat: number; dist: number };

export const DIST_MIN = 1.28;
export const DIST_MAX = 4.6;
export const LAT_LIMIT = 72;

/** Vue d'ouverture du prototype (Méditerranée orientale, recul confortable). */
export const CAM_HOME: CamState = { lon: 20, lat: 18, dist: 2.9 };

/** Cadrages du prototype : orateur serré, événement plus large (lat − offset :
 * la caméra vise SOUS le sujet pour garder l'horizon en haut du cadre). */
export const SPEAKER_VIEW = { latOffset: -13, dist: 2.35 };
export const EVENT_VIEW = { latOffset: -8, dist: 2.25 };
export const JUDGE_VIEW = { lat: 52, dist: 3.9 };

export function clampDist(dist: number): number {
  return Math.max(DIST_MIN, Math.min(DIST_MAX, dist));
}

export function clampLat(lat: number): number {
  return Math.max(-LAT_LIMIT, Math.min(LAT_LIMIT, lat));
}

/** Un cran de molette : ±9 % de distance, borné. `sign` > 0 éloigne. */
export function zoomBy(cam: CamState, sign: number): CamState {
  return { ...cam, dist: clampDist(cam.dist * (1 + Math.sign(sign) * 0.09)) };
}

export function easeInOutCubic(t: number): number {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
}

export type CameraFly = {
  t: number;
  dur: number;
  from: CamState;
  d: { lon: number; lat: number; dist: number };
};

/** Prépare un fly-to vers (lon, lat[, dist]) par le chemin le plus court. */
export function flyTowards(
  cam: CamState,
  target: { lon: number; lat: number; dist?: number },
  dur = 1.25,
): CameraFly {
  let dlon = target.lon - cam.lon;
  while (dlon > 180) dlon -= 360;
  while (dlon < -180) dlon += 360;
  return {
    t: 0,
    dur,
    from: { ...cam },
    d: {
      lon: dlon,
      lat: clampLat(target.lat) - cam.lat,
      dist: (target.dist !== undefined ? clampDist(target.dist) : cam.dist) - cam.dist,
    },
  };
}

/** Avance le vol de `dt` secondes ; `fly` devient null à l'arrivée (exacte). */
export function stepFly(
  cam: CamState,
  fly: CameraFly,
  dt: number,
): { cam: CamState; fly: CameraFly | null } {
  const t = fly.t + dt;
  const k = easeInOutCubic(Math.min(1, t / fly.dur));
  const next: CamState = {
    lon: fly.from.lon + fly.d.lon * k,
    lat: fly.from.lat + fly.d.lat * k,
    dist: fly.from.dist + fly.d.dist * k,
  };
  if (t >= fly.dur) {
    return {
      cam: {
        lon: fly.from.lon + fly.d.lon,
        lat: fly.from.lat + fly.d.lat,
        dist: fly.from.dist + fly.d.dist,
      },
      fly: null,
    };
  }
  return { cam: next, fly: { ...fly, t } };
}

/** Position 3D de la caméra : le même mapping sphérique que les objets posés. */
export function camPosition(cam: CamState): [number, number, number] {
  return toXYZ(cam.lon, cam.lat, cam.dist);
}
