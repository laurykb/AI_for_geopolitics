import * as THREE from "three";
import { describe, expect, it } from "vitest";

import { createMascot } from "./mascot";

describe("createMascot — Laury 3D (portage proto)", () => {
  it("construit la mascotte masquée, à l'échelle, ajoutée à la scène", () => {
    const scene = new THREE.Scene();
    const tex = new THREE.Texture();
    const m = createMascot(scene, tex);

    expect(m.g.visible).toBe(false); // masquée hors visite
    expect(m.g.scale.x).toBeCloseTo(0.68);
    expect(scene.children).toContain(m.g);
    // la poignée expose les parties animées par la boucle three
    expect(m.rig).toBeInstanceOf(THREE.Group);
    expect(m.armR).toBeInstanceOf(THREE.Group);
  });

  it("le petit monde dans la main porte LA texture du globe", () => {
    const tex = new THREE.Texture();
    const m = createMascot(new THREE.Scene(), tex);
    expect(m.mini.material.map).toBe(tex);
  });
});
