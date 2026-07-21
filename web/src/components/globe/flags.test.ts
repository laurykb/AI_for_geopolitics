import { describe, expect, it } from "vitest";

import { ROSTER } from "@/lib/countries";
import { FLAG_SPECS, flagSpec, type Emblem, type FlagSpec } from "./flags";

const HEX = /^#[0-9a-f]{6}$/;

function colorsOf(spec: FlagSpec): string[] {
  const emblemColors = (e?: Emblem): string[] => {
    if (!e) return [];
    switch (e.kind) {
      case "taeguk":
        return [];
      case "disc-crescent":
        return [e.disc, e.mark];
      case "disc-star":
        return [e.disc, e.star];
      default:
        return [e.color];
    }
  };
  switch (spec.kind) {
    case "bands":
      return [...spec.colors, ...emblemColors(spec.emblem)];
    case "field":
      return [spec.color, ...emblemColors(spec.emblem)];
    case "canton-stripes":
      return [...spec.stripes, spec.canton, spec.starColor];
    case "union-jack":
      return [];
  }
}

describe("FLAG_SPECS — les 33 pays du roster", () => {
  it("chaque pays du roster a un drapeau déclaré", () => {
    for (const slug of ROSTER) {
      expect(FLAG_SPECS[slug], `drapeau manquant : ${slug}`).toBeDefined();
    }
  });

  it("toutes les couleurs sont des hex valides, bandes entre 2 et 5", () => {
    for (const [slug, spec] of Object.entries(FLAG_SPECS)) {
      for (const color of colorsOf(spec)) {
        expect(color, `${slug} : ${color}`).toMatch(HEX);
      }
      if (spec.kind === "bands") {
        expect(spec.colors.length, slug).toBeGreaterThanOrEqual(2);
        expect(spec.colors.length, slug).toBeLessThanOrEqual(5);
      }
    }
  });

  it("un pays inventé retombe sur un aplat à sa teinte", () => {
    expect(flagSpec("atlantis", "#123abc")).toEqual({ kind: "field", color: "#123abc" });
  });
});
