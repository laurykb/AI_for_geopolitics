import { describe, expect, it } from "vitest";

import { buildCreateBody, DEFAULT_SETTINGS } from "./flow";
import { TABLES, temperamentMeta } from "./temperament";

describe("pastilles de tempérament (G17)", () => {
  it("chaque tempérament a son glyphe et son libellé", () => {
    expect(temperamentMeta("colombe")).toEqual({ glyph: "🕊", label: "colombe" });
    expect(temperamentMeta("faucon")).toEqual({ glyph: "🦅", label: "faucon" });
    expect(temperamentMeta("opportuniste")).toEqual({ glyph: "🦎", label: "opportuniste" });
  });

  it("un tempérament inconnu retombe sur l'opportuniste (défaut sûr)", () => {
    expect(temperamentMeta("berserk")).toEqual(temperamentMeta("opportuniste"));
  });

  it("les quatre compositions de table sont proposées", () => {
    expect(TABLES.map((t) => t.value)).toEqual([
      "equilibree",
      "colombes",
      "faucons",
      "aleatoire",
    ]);
  });
});

describe("la composition de table ne part qu'en partie libre", () => {
  const base = {
    scenario: "red_sea",
    baseMode: "classic" as const,
    role: "gm" as const,
    selected: ["usa", "iran"],
  };

  it("partie libre : le réglage Table voyage", () => {
    const body = buildCreateBody({
      ...base,
      settings: { ...DEFAULT_SETTINGS, free: true, table: "faucons" },
    });
    expect(body.table).toBe("faucons");
  });

  it("hors partie libre : rien n'est envoyé (le backend forcerait équilibrée)", () => {
    const body = buildCreateBody({
      ...base,
      settings: { ...DEFAULT_SETTINGS, free: false, table: "faucons" },
    });
    expect(body.table).toBeUndefined();
  });
});
