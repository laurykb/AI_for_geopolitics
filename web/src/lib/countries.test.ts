/** Verrous de cohérence du roster front (miroir de tests/test_country_data.py) :
 * chaque pays jouable a une identité, un tracé world-atlas et une capitale. */

import { describe, expect, it } from "vitest";
import type { Topology, GeometryCollection } from "topojson-specification";
import world from "world-atlas/countries-110m.json";

import {
  DEFAULT_COUNTRIES,
  ISO_NUM,
  ROSTER,
  SUMMIT_MAX,
  SUMMIT_MIN,
  speakerMeta,
} from "./countries";
import { CAPITALS } from "./stage";

describe("roster", () => {
  it("compte 23 pays uniques (danemark hors roster depuis 2026-07-07)", () => {
    expect(ROSTER).toHaveLength(23);
    expect(new Set(ROSTER).size).toBe(23);
    expect(ROSTER).not.toContain("denmark");
  });

  it("la sélection par défaut est un sommet valide", () => {
    expect(DEFAULT_COUNTRIES).toHaveLength(7);
    expect(DEFAULT_COUNTRIES.length).toBeGreaterThanOrEqual(SUMMIT_MIN);
    expect(DEFAULT_COUNTRIES.length).toBeLessThanOrEqual(SUMMIT_MAX);
    for (const id of DEFAULT_COUNTRIES) expect(ROSTER).toContain(id);
  });

  it("chaque pays a une identité visuelle connue (pas de repli haché)", () => {
    for (const id of ROSTER) {
      const meta = speakerMeta(id);
      expect(meta.label, id).toBeTruthy();
      expect(meta.code, id).toMatch(/^[A-Z]{2,3}$/);
      expect(meta.hue, id).toMatch(/^#[0-9a-f]{6}$/i);
    }
  });

  it("chaque pays a un tracé world-atlas (id topojson réel)", () => {
    const topo = world as unknown as Topology<{ countries: GeometryCollection }>;
    const ids = new Set(topo.objects.countries.geometries.map((g) => String(g.id)));
    for (const id of ROSTER) {
      expect(ISO_NUM[id], `${id}: pas d'entrée ISO_NUM`).toBeTruthy();
      expect(ids.has(ISO_NUM[id]), `${id}: id ${ISO_NUM[id]} absent de world-atlas`).toBe(true);
    }
  });

  it("chaque pays a une capitale projetable", () => {
    for (const id of ROSTER) {
      const capital = CAPITALS[id];
      expect(capital, `${id}: capitale manquante`).toBeTruthy();
      const [lon, lat] = capital;
      expect(Math.abs(lon), id).toBeLessThanOrEqual(180);
      expect(Math.abs(lat), id).toBeLessThanOrEqual(90);
    }
  });
});
