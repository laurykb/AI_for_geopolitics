/** Points de ligue (G11 §2) : les rangs et la progression, aux seuils exacts. */

import { describe, expect, it } from "vitest";

import { RANKS, rankFor } from "./league";

describe("rankFor", () => {
  it("0 LP = Attaché, progression vers Émissaire", () => {
    const r = rankFor(0);
    expect(r.rank.name).toBe("Attaché");
    expect(r.next?.name).toBe("Émissaire");
    expect(r.toNext).toBe(100);
    expect(r.progress).toBe(0);
  });

  it("place chaque seuil exact dans le bon rang", () => {
    expect(rankFor(99).rank.name).toBe("Attaché");
    expect(rankFor(100).rank.name).toBe("Émissaire");
    expect(rankFor(250).rank.name).toBe("Diplomate");
    expect(rankFor(450).rank.name).toBe("Ambassadeur");
    expect(rankFor(700).rank.name).toBe("Ministre");
    expect(rankFor(1000).rank.name).toBe("Chancelier");
    expect(rankFor(1400).rank.name).toBe("Éminence");
  });

  it("interpole la progression au milieu d'un rang", () => {
    const r = rankFor(175); // Émissaire [100, 250) → 75/150
    expect(r.rank.name).toBe("Émissaire");
    expect(r.progress).toBeCloseTo(0.5, 5);
    expect(r.toNext).toBe(75);
  });

  it("sature au rang maximal (Éminence)", () => {
    const r = rankFor(99999);
    expect(r.rank.name).toBe("Éminence");
    expect(r.next).toBeNull();
    expect(r.progress).toBe(1);
    expect(r.toNext).toBe(0);
  });

  it("borne les LP négatifs à Attaché (plancher 0)", () => {
    expect(rankFor(-50).rank.name).toBe("Attaché");
    expect(rankFor(-50).progress).toBe(0);
  });

  it("RANKS couvre les 7 rangs de la spec, décroissants", () => {
    expect(RANKS.map((r) => r.name)).toEqual([
      "Éminence",
      "Chancelier",
      "Ministre",
      "Ambassadeur",
      "Diplomate",
      "Émissaire",
      "Attaché",
    ]);
  });
});
