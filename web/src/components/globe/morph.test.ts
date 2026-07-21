/** Le dépliage (spec théâtre-globe §1/§5, décision full-three 2026-07-21) —
 * maths PURES du morph sphère ⇄ carte : plan équirectangulaire 2:1, ancres
 * (position lerp + orientation slerp), points mixtes des objets volants,
 * caméra oblique « table tactique » et arc reconstruit selon le morph. */

import * as THREE from "three";
import { describe, expect, it } from "vitest";

import {
  AnchorRegistry,
  FLAT_H,
  FLAT_W,
  Q_FLAT,
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
} from "./morph";
import { toXYZ } from "./picking";

const TEHRAN: [number, number] = [51.39, 35.7];

describe("planeXYZ (dépliage équirectangulaire 2:1)", () => {
  it("déplie Greenwich-équateur au centre, les bords aux bords", () => {
    expect(planeXYZ(0, 0, 0.02)).toEqual([0, 0, 0.02]);
    const [e] = planeXYZ(180, 0);
    expect(e).toBeCloseTo(FLAT_W / 2, 6);
    const [, n] = planeXYZ(0, 90);
    expect(n).toBeCloseTo(FLAT_H / 2, 6);
    expect(FLAT_W).toBeCloseTo(2 * FLAT_H, 6); // carte 2:1
  });
});

describe("stepMorph (le dépliage avance vers sa cible)", () => {
  it("converge vers la cible et s'y colle en fin de course", () => {
    let k = 0;
    k = stepMorph(k, 1, 0.1);
    expect(k).toBeGreaterThan(0);
    expect(k).toBeLessThan(1);
    for (let i = 0; i < 60; i++) k = stepMorph(k, 1, 0.1);
    expect(k).toBe(1);
    k = stepMorph(k, 0, 5);
    for (let i = 0; i < 60; i++) k = stepMorph(k, 0, 0.1);
    expect(k).toBe(0);
  });
});

describe("AnchorRegistry (les objets posés sur le monde suivent le dépliage)", () => {
  it("un robot ancré : debout sur la sphère à k=0, debout sur la carte à k=1", () => {
    const reg = new AnchorRegistry();
    const g = new THREE.Group();
    reg.anchor(g, TEHRAN[0], TEHRAN[1], { lift: 0.001 });
    reg.apply(0);
    expect(g.position.distanceTo(new THREE.Vector3(...toXYZ(TEHRAN[0], TEHRAN[1], 1.001)))).toBeLessThan(1e-6);
    reg.apply(1);
    expect(g.position.distanceTo(new THREE.Vector3(...planeXYZ(TEHRAN[0], TEHRAN[1], 0.001)))).toBeLessThan(1e-6);
    // À plat, le +Y local (la tête du robot) pointe vers +Z (la caméra).
    const up = new THREE.Vector3(0, 1, 0).applyQuaternion(g.quaternion);
    expect(up.distanceTo(new THREE.Vector3(0, 0, 1))).toBeLessThan(1e-6);
  });

  it("un anneau ancré Q_ID : face au ciel à plat (quaternion identité)", () => {
    const reg = new AnchorRegistry();
    const ring = new THREE.Group();
    reg.anchor(ring, 56.5, 26.6, { lift: 0.004, flatQ: Q_ID });
    reg.apply(0);
    // Sur la sphère : le +Z local suit la normale au sol.
    const outward = new THREE.Vector3(0, 0, 1).applyQuaternion(ring.quaternion);
    expect(outward.distanceTo(ring.position.clone().normalize())).toBeLessThan(1e-5);
    reg.apply(1);
    expect(ring.quaternion.angleTo(new THREE.Quaternion())).toBeLessThan(1e-6);
  });

  it("se ré-ancre sans doublon et s'oublie proprement", () => {
    const reg = new AnchorRegistry();
    const g = new THREE.Group();
    reg.anchor(g, 0, 0);
    reg.anchor(g, 10, 10);
    expect(reg.size).toBe(1);
    reg.remove(g);
    expect(reg.size).toBe(0);
  });
});

describe("mixPoint / mixTop (objets volants et étiquettes)", () => {
  it("mixPoint garde l'altitude : l'orbite du drone survole la carte", () => {
    const sphereP = new THREE.Vector3(...toXYZ(30, 40, 1.22));
    const out = new THREE.Vector3();
    mixPoint(sphereP, 0, out);
    expect(out.distanceTo(sphereP)).toBeLessThan(1e-6);
    mixPoint(sphereP, 1, out);
    const flat = new THREE.Vector3(...planeXYZ(30, 40, 0.22));
    expect(out.distanceTo(flat)).toBeLessThan(1e-4);
  });

  it("mixTop relie le point haut sphère au point haut carte", () => {
    const out = new THREE.Vector3();
    mixTop(TEHRAN, 1.008, 0.008, 0, out);
    expect(out.distanceTo(new THREE.Vector3(...toXYZ(TEHRAN[0], TEHRAN[1], 1.008)))).toBeLessThan(1e-6);
    mixTop(TEHRAN, 1.008, 0.008, 1, out);
    expect(out.distanceTo(new THREE.Vector3(...planeXYZ(TEHRAN[0], TEHRAN[1], 0.008)))).toBeLessThan(1e-6);
  });
});

describe("arcCurveAt (l'arc suit le dépliage)", () => {
  const WASHINGTON: [number, number] = [-77.04, 38.9];

  it("à k=0, l'arc sphérique historique ; à k=1, l'arc plane au-dessus de la carte", () => {
    const sphere = arcCurveAt(WASHINGTON, TEHRAN, 0);
    expect(
      sphere.getPointAt(0).distanceTo(new THREE.Vector3(...toXYZ(WASHINGTON[0], WASHINGTON[1], 1.004))),
    ).toBeLessThan(1e-6);
    expect(sphere.getPointAt(0.5).length()).toBeGreaterThan(1.04);
    const flat = arcCurveAt(WASHINGTON, TEHRAN, 1);
    expect(
      flat.getPointAt(1).distanceTo(new THREE.Vector3(...planeXYZ(TEHRAN[0], TEHRAN[1], 0.004))),
    ).toBeLessThan(1e-6);
    expect(flat.getPointAt(0.5).z).toBeGreaterThan(0.06);
  });
});

describe("caméra plate (vue oblique, bornes, bascule aller-retour)", () => {
  it("la pose est oblique : caméra en retrait sous la cible, jamais zénithale", () => {
    const { position, target } = flatCameraPose({ x: 1, y: 0.5, dist: 2 });
    expect(position[2]).toBeCloseTo(1.8, 6); // recul .9·dist
    expect(position[1]).toBeLessThan(target[1]); // vise au-dessus d'elle : oblique
  });

  it("clampFlat borne le pan à la carte et le zoom aux rails", () => {
    const f = clampFlat({ x: 99, y: -99, dist: 0.1 });
    expect(f.x).toBeCloseTo(FLAT_W / 2, 6);
    expect(f.y).toBeCloseTo(-FLAT_H / 2, 6);
    expect(f.dist).toBeCloseTo(0.7, 6);
  });

  it("le point de vue est préservé à la bascule (aller puis retour)", () => {
    const cam = { lon: 51, lat: 35, dist: 2.2 };
    const f = enterFlatView(cam);
    const back = exitFlatView(f);
    expect(back.lon).toBeCloseTo(51, 4);
    expect(back.lat).toBeCloseTo(35, 4);
    expect(back.dist).toBeCloseTo(2.2, 4);
  });

  it("flatWorldPerPixel suit le fov 42° du théâtre", () => {
    expect(flatWorldPerPixel(2, 800)).toBeCloseTo((2 * 2 * Math.tan((21 * Math.PI) / 180)) / 800, 10);
  });

  it("flatFlyTowards / stepFlatFly atterrit exactement sur la cible", () => {
    let f = { x: 0, y: 0, dist: 2.2 };
    let fly: ReturnType<typeof flatFlyTowards> | null = flatFlyTowards(f, { lon: 56.5, lat: 26.6, dist: 2 }, 1);
    for (let i = 0; i < 12 && fly; i++) {
      const next = stepFlatFly(f, fly, 0.1);
      f = next.fcam;
      fly = next.fly;
    }
    expect(fly).toBeNull();
    expect(f.x).toBeCloseTo(planeXYZ(56.5, 26.6)[0], 6);
    expect(f.y).toBeCloseTo(planeXYZ(56.5, 26.6)[1], 6);
    expect(f.dist).toBeCloseTo(2, 6);
  });
});

describe("Q_FLAT / Q_ID (les deux orientations à plat)", () => {
  it("Q_FLAT redresse +Y vers +Z ; Q_ID ne touche à rien", () => {
    const up = new THREE.Vector3(0, 1, 0).applyQuaternion(Q_FLAT);
    expect(up.distanceTo(new THREE.Vector3(0, 0, 1))).toBeLessThan(1e-6);
    expect(Q_ID.angleTo(new THREE.Quaternion())).toBe(0);
  });
});
