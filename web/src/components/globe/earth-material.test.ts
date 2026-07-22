/** Matériau Terre réaliste (spec planète réaliste A2) : les uniforms jour/nuit/
 * surcouche/soleil/morph existent et les poignées setSun/setFlat écrivent bien
 * dans les uniforms. Le morph vertex est préservé verbatim ; on ne teste ici
 * que le contrat public (pas de GPU en jsdom). */

import * as THREE from "three";
import { describe, expect, it } from "vitest";

import { createEarthMaterial } from "./earth-material";

describe("matériau Terre réaliste", () => {
  it("expose les uniforms attendus et les setters", () => {
    const t = () => new THREE.Texture();
    const m = createEarthMaterial({ day: t(), night: t(), overlay: t(), flatW: 6, flatH: 3 });
    expect(m.material.uniforms.uDay).toBeDefined();
    expect(m.material.uniforms.uNight).toBeDefined();
    expect(m.material.uniforms.uOverlay).toBeDefined();
    expect(m.material.uniforms.uSun).toBeDefined();
    expect(m.material.uniforms.uFlat).toBeDefined();
    m.setFlat(1);
    expect(m.material.uniforms.uFlat.value).toBe(1);
    m.setSun(new THREE.Vector3(1, 0, 0));
    expect(m.material.uniforms.uSun.value.x).toBe(1);
  });
});
