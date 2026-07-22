/** Picking du globe (spec théâtre-globe §2) — géométrie pure sphère ↔ lon/lat
 * et pays-au-point via d3.geoContains, sans three ni DOM. Les tests utilisent
 * le fond 110m déjà décodé (même forme que le 50m servi au globe). */

import { describe, expect, it } from "vitest";

import { countryAt, inverseLL, summitFeatures, toXYZ } from "./picking";
import { WORLD_FEATURES } from "@/lib/world";

const SAMPLES: [number, number][] = [
  [2.35, 48.86], // Paris
  [-77, 38.9], // Washington
  [116.4, 39.9], // Pékin
  [139.69, 35.68], // Tokyo
  [-58.38, -34.6], // Buenos Aires
];

describe("toXYZ / inverseLL (le mapping sphère du prototype)", () => {
  it("place le pôle Nord en (0, r, 0) et respecte le rayon demandé", () => {
    const [x, y, z] = toXYZ(0, 90, 1.5);
    expect(x).toBeCloseTo(0, 6);
    expect(y).toBeCloseTo(1.5, 6);
    expect(z).toBeCloseTo(0, 6);
    const [a, b, c] = toXYZ(31.24, 30.04, 2.25);
    expect(Math.hypot(a, b, c)).toBeCloseTo(2.25, 6);
  });

  it("boucle lon/lat → xyz → lon/lat sans dérive", () => {
    for (const [lon, lat] of SAMPLES) {
      const [ilon, ilat] = inverseLL(toXYZ(lon, lat));
      expect(ilon).toBeCloseTo(lon, 5);
      expect(ilat).toBeCloseTo(lat, 5);
    }
  });

  it("survit à l'antiméridien (±180 se rejoignent)", () => {
    const [lon, lat] = inverseLL(toXYZ(180, 10));
    expect(Math.abs(lon)).toBeCloseTo(180, 5);
    expect(lat).toBeCloseTo(10, 5);
  });
});

describe("summitFeatures (casting → features du fond de carte)", () => {
  it("résout chaque slug du sommet par son ISO numérique", () => {
    const feats = summitFeatures(["usa", "france"], WORLD_FEATURES);
    expect(feats.map((f) => f.slug)).toEqual(["usa", "france"]);
    expect(String(feats[0].feat?.id)).toBe("840");
    expect(String(feats[1].feat?.id)).toBe("250");
  });

  it("laisse un pays inventé sans feature (pas de robot, règle existante)", () => {
    const feats = summitFeatures(["neo_atlantis"], WORLD_FEATURES);
    expect(feats[0].feat).toBeUndefined();
  });
});

describe("countryAt (clic océan vs clic pays)", () => {
  const feats = summitFeatures(["france", "usa"], WORLD_FEATURES);

  it("trouve le pays du sommet sous le point", () => {
    expect(countryAt([2.35, 48.86], feats)).toBe("france");
    expect(countryAt([-77, 38.9], feats)).toBe("usa");
  });

  it("rend null en plein océan ou hors sommet", () => {
    expect(countryAt([-30, 25], feats)).toBeNull(); // Atlantique
    expect(countryAt([116.4, 39.9], feats)).toBeNull(); // Pékin, hors sommet
  });

  it("rend null sans point (pick raté)", () => {
    expect(countryAt(null, feats)).toBeNull();
  });
});
