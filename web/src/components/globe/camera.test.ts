/** Caméra orbitale du globe (spec théâtre-globe §2) — état pur {lon,lat,dist} :
 * bornes, zoom, fly-to easeInOutCubic en temps réel (dt), position 3D. */

import { describe, expect, it } from "vitest";

import {
  CAM_HOME,
  DIST_MAX,
  DIST_MIN,
  LAT_LIMIT,
  camPosition,
  clampDist,
  clampLat,
  easeInOutCubic,
  flyTowards,
  stepFly,
  zoomBy,
} from "./camera";
import { toXYZ } from "./picking";

describe("bornes de l'orbite", () => {
  it("borne la distance aux rails du prototype (1.28–4.6)", () => {
    expect(clampDist(0.5)).toBe(DIST_MIN);
    expect(clampDist(9)).toBe(DIST_MAX);
    expect(clampDist(2.9)).toBe(2.9);
  });

  it("borne la latitude à ±72° (jamais zénithal)", () => {
    expect(clampLat(88)).toBe(LAT_LIMIT);
    expect(clampLat(-88)).toBe(-LAT_LIMIT);
  });

  it("zoome par crans de 9 % en restant borné", () => {
    const closer = zoomBy({ ...CAM_HOME, dist: 2 }, -1);
    expect(closer.dist).toBeCloseTo(2 * 0.91, 6);
    const walled = zoomBy({ ...CAM_HOME, dist: DIST_MAX }, 1);
    expect(walled.dist).toBe(DIST_MAX);
  });
});

describe("easeInOutCubic", () => {
  it("part de 0, finit à 1, symétrique au centre", () => {
    expect(easeInOutCubic(0)).toBe(0);
    expect(easeInOutCubic(1)).toBe(1);
    expect(easeInOutCubic(0.5)).toBeCloseTo(0.5, 6);
    expect(easeInOutCubic(0.25)).toBeCloseTo(0.0625, 6);
  });
});

describe("flyTowards / stepFly (fly-to en temps réel)", () => {
  it("prend le chemin le plus court à travers l'antiméridien", () => {
    const fly = flyTowards({ lon: 170, lat: 0, dist: 2.9 }, { lon: -170, lat: 0 });
    expect(fly.d.lon).toBeCloseTo(20, 6);
    const back = flyTowards({ lon: -170, lat: 0, dist: 2.9 }, { lon: 170, lat: 0 });
    expect(back.d.lon).toBeCloseTo(-20, 6);
  });

  it("atterrit exactement sur la cible à la fin de la durée", () => {
    let cam = { lon: 0, lat: 0, dist: 2.9 };
    let fly: ReturnType<typeof flyTowards> | null = flyTowards(
      cam,
      { lon: 51.39, lat: 22.7, dist: 1.85 },
      1.0,
    );
    for (let i = 0; i < 10 && fly; i++) {
      const next = stepFly(cam, fly, 0.13);
      cam = next.cam;
      fly = next.fly;
    }
    expect(fly).toBeNull();
    expect(cam.lon).toBeCloseTo(51.39, 6);
    expect(cam.lat).toBeCloseTo(22.7, 6);
    expect(cam.dist).toBeCloseTo(1.85, 6);
  });

  it("garde la distance courante si la cible n'en donne pas", () => {
    const fly = flyTowards({ lon: 0, lat: 0, dist: 3.3 }, { lon: 10, lat: 5 });
    expect(fly.d.dist).toBe(0);
  });
});

describe("camPosition", () => {
  it("est le même mapping sphérique que toXYZ, au rayon dist", () => {
    const cam = { lon: 43.3, lat: 12.6, dist: 2.25 };
    const [x, y, z] = camPosition(cam);
    const [ex, ey, ez] = toXYZ(cam.lon, cam.lat, cam.dist);
    expect(x).toBeCloseTo(ex, 6);
    expect(y).toBeCloseTo(ey, 6);
    expect(z).toBeCloseTo(ez, 6);
    expect(Math.hypot(x, y, z)).toBeCloseTo(2.25, 6);
  });
});
