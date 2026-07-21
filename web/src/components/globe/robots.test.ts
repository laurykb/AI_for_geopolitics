/** Délégués, drone GM, Juge, arcs, anneau d'événement (spec théâtre-globe §1-§2).
 * three tourne sans WebGL en node : on teste la CONSTRUCTION (postures, ancrage
 * sphérique) et les machines à états, pas le rendu. Les textures canvas sont
 * injectées (null ici — pas de DOM). */

import * as THREE from "three";
import { describe, expect, it } from "vitest";

import {
  animateRobot,
  buildArc,
  makeEventGroup,
  makeGMDrone,
  makeJudge,
  makeRobot,
  placeEventGroup,
  setRobotMood,
  stepDrone,
  stepVerdictWaves,
} from "./robots";
import { toXYZ } from "./picking";

const TEHRAN: [number, number] = [51.39, 35.7];

function robot() {
  return makeRobot({ slug: "iran", hue: "#34d399", lonlat: TEHRAN, flagMap: null });
}

describe("makeRobot (délégué humanoïde ancré sur sa capitale)", () => {
  it("se plante sur la capitale, à la verticale du sol", () => {
    const r = robot();
    expect(r.group.userData.slug).toBe("iran");
    expect(r.group.position.length()).toBeCloseTo(1.001, 3);
    // Le quaternion aligne +Y sur la normale au sol (le robot est debout).
    const up = new THREE.Vector3(0, 1, 0).applyQuaternion(r.group.quaternion);
    const normal = r.group.position.clone().normalize();
    expect(up.dot(normal)).toBeCloseTo(1, 5);
    expect(r.group.scale.x).toBeCloseTo(1.7, 6);
  });

  it("a deux yeux, deux bras, une tête articulée et un socle", () => {
    const r = robot();
    expect(r.eyes).toHaveLength(2);
    expect(r.armL).not.toBe(r.armR);
    expect(r.head.children.length).toBeGreaterThan(2);
    expect(r.base.material).toBeInstanceOf(THREE.MeshBasicMaterial);
    // Voile de brouillard et cadenas : posés mais éteints par défaut.
    expect(r.veil.visible).toBe(false);
    expect(r.lock.visible).toBe(false);
  });
});

describe("setRobotMood (états discrets — matériaux)", () => {
  it("suspendu : gris, yeux éteints, cadenas ; retour idle : restauré", () => {
    const r = robot();
    const panelBefore = r.mats.panel.color.getHexString();
    setRobotMood(r, "suspended");
    expect(r.mats.panel.color.getHexString()).not.toBe(panelBefore);
    expect(r.lock.visible).toBe(true);
    setRobotMood(r, "idle");
    expect(r.mats.panel.color.getHexString()).toBe(panelBefore);
    expect(r.lock.visible).toBe(false);
  });
});

describe("animateRobot (états continus — la boucle three)", () => {
  it("parle : ambre, bond, salut du bras", () => {
    const r = robot();
    setRobotMood(r, "speaking");
    animateRobot(r, 0.42, false);
    expect(r.eyes[0].material).toBeInstanceOf(THREE.MeshBasicMaterial);
    expect((r.eyes[0].material as THREE.MeshBasicMaterial).color.getHexString()).toBe("ffc14d");
    expect(r.spinner.scale.x).toBeGreaterThan(1.15);
    expect(r.base.material.opacity).toBeCloseTo(0.85, 6);
  });

  it("pense : tête levée, yeux cyan", () => {
    const r = robot();
    setRobotMood(r, "thinking");
    animateRobot(r, 0.42, false);
    expect(r.head.rotation.x).toBeLessThan(0);
    expect((r.eyes[0].material as THREE.MeshBasicMaterial).color.getHexString()).toBe("59d7ff");
  });

  it("suspendu : immobile (pas de bob, échelle 1)", () => {
    const r = robot();
    setRobotMood(r, "suspended");
    animateRobot(r, 0.42, false);
    expect(r.spinner.position.y).toBe(0);
    expect(r.spinner.scale.x).toBe(1);
  });
});

describe("drone GM (orbite ↔ annonce)", () => {
  it("en orbite, avance son angle et éteint le faisceau", () => {
    const { drone, beam } = makeGMDrone();
    beam.material.opacity = 0.2;
    const state = { mode: "orbit" as const, a: 0, t: 0, target: null };
    const next = stepDrone(drone, beam, state, 0.1);
    expect(next.a).toBeCloseTo(0.025, 6);
    expect(beam.material.opacity).toBeLessThan(0.2);
  });

  it("en annonce, descend vers le lieu, allume le faisceau, puis rentre", () => {
    const { drone, beam } = makeGMDrone();
    drone.position.set(1.6, 0, 0);
    const target = new THREE.Vector3(...toXYZ(56.5, 26.6, 1));
    const state = { mode: "announce" as const, a: 0, t: 0, target };
    const before = drone.position.distanceTo(target.clone().multiplyScalar(1.22));
    let next = stepDrone(drone, beam, state, 0.1);
    expect(drone.position.distanceTo(target.clone().multiplyScalar(1.22))).toBeLessThan(before);
    expect(beam.material.opacity).toBeGreaterThan(0);
    next = stepDrone(drone, beam, { ...next, t: 4.6 }, 0.1);
    expect(next.mode).toBe("orbit");
  });
});

describe("le Juge et ses ondes de verdict", () => {
  it("flotte au-dessus du monde, halo optionnel injecté", () => {
    const j = makeJudge(null);
    expect(j.group.position.y).toBeCloseTo(1.72, 6);
    expect(j.core).toBeDefined();
    expect(j.ringA).not.toBe(j.ringB);
  });

  it("stepVerdictWaves : l'onde enfle, pâlit, puis meurt", () => {
    const wave = new THREE.Mesh(
      new THREE.SphereGeometry(1, 8, 6),
      new THREE.MeshBasicMaterial({ transparent: true, opacity: 0.2 }),
    );
    wave.scale.setScalar(1.02);
    let alive = stepVerdictWaves([wave], 0.1);
    expect(alive).toHaveLength(1);
    expect(wave.scale.x).toBeGreaterThan(1.02);
    for (let i = 0; i < 40; i++) alive = stepVerdictWaves(alive, 0.1);
    expect(alive).toHaveLength(0);
  });
});

describe("anneau d'événement et arc diplomatique", () => {
  it("l'anneau se pose tangent à la sphère au lieu de crise", () => {
    const ev = makeEventGroup();
    placeEventGroup(ev, 56.5, 26.6);
    const expected = new THREE.Vector3(...toXYZ(56.5, 26.6, 1.004));
    expect(ev.group.position.distanceTo(expected)).toBeLessThan(1e-6);
    expect(ev.rings).toHaveLength(2);
  });

  it("l'arc relie les deux capitales en passant au-dessus de la surface", () => {
    const arc = buildArc([-77.04, 38.9], [51.39, 35.7]);
    const a = new THREE.Vector3(...toXYZ(-77.04, 38.9, 1.004));
    const b = new THREE.Vector3(...toXYZ(51.39, 35.7, 1.004));
    expect(arc.curve.getPointAt(0).distanceTo(a)).toBeLessThan(1e-6);
    expect(arc.curve.getPointAt(1).distanceTo(b)).toBeLessThan(1e-6);
    expect(arc.curve.getPointAt(0.5).length()).toBeGreaterThan(1.04);
  });
});
