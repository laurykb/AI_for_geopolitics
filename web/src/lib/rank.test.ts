/** Rangs de carrière (RG-1) : les blasons suivent le niveau d'XP, aux seuils exacts. */

import { describe, expect, it } from "vitest";

import { RANKS, rankForLevel } from "./rank";

describe("rankForLevel", () => {
  it("niveau 1 = Attaché, progression vers Émissaire", () => {
    const r = rankForLevel(1);
    expect(r.rank.name).toBe("Attaché");
    expect(r.next?.name).toBe("Émissaire");
    expect(r.progress).toBe(0);
  });

  it("les seuils exacts par niveau", () => {
    expect(rankForLevel(2).rank.name).toBe("Attaché");
    expect(rankForLevel(3).rank.name).toBe("Émissaire");
    expect(rankForLevel(6).rank.name).toBe("Diplomate");
    expect(rankForLevel(10).rank.name).toBe("Ambassadeur");
    expect(rankForLevel(15).rank.name).toBe("Ministre");
    expect(rankForLevel(22).rank.name).toBe("Chancelier");
    expect(rankForLevel(30).rank.name).toBe("Éminence");
  });

  it("progression au sein d'un rang", () => {
    const r = rankForLevel(4); // Émissaire [3, 6) → 1/3 du chemin
    expect(r.rank.name).toBe("Émissaire");
    expect(r.toNext).toBe(2); // niveau 6 attendu pour Diplomate
    expect(r.progress).toBeCloseTo(1 / 3, 5);
  });

  it("au rang maximal (Éminence) : plus de suivant, progression pleine", () => {
    const r = rankForLevel(99);
    expect(r.rank.name).toBe("Éminence");
    expect(r.next).toBeNull();
    expect(r.progress).toBe(1);
    expect(r.toNext).toBe(0);
  });

  it("borne un niveau aberrant à Attaché (plancher niveau 1)", () => {
    expect(rankForLevel(0).rank.name).toBe("Attaché");
    expect(rankForLevel(-5).rank.name).toBe("Attaché");
    expect(RANKS[RANKS.length - 1].name).toBe("Attaché");
  });
});
