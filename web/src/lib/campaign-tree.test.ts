/** tiersOf (G12-b §4) : rangement en paliers de l'arbre de campagne. */

import { describe, expect, it } from "vitest";

import { tiersOf } from "./campaign-tree";
import type { ChapterView } from "./types";

function chap(id: string, requires: string[] = []): ChapterView {
  return {
    id,
    crisis_id: id,
    title: id,
    mode: "crisis",
    difficulty: 1,
    horizon: 5,
    countries: ["usa", "iran"],
    blurb: "",
    best: null,
    improvement: null,
    medal: null,
    unlocked: true,
    requires,
    coming_soon: false,
  };
}

/** ids d'un palier, triés (l'ordre d'insertion n'est pas garanti). */
function idsAt(tiers: Map<number, ChapterView[]>, tier: number): string[] {
  return (tiers.get(tier) ?? []).map((c) => c.id).sort();
}

describe("tiersOf", () => {
  it("place les racines (requires vide) au palier 0", () => {
    const tiers = tiersOf([chap("a"), chap("b")]);
    expect(idsAt(tiers, 0)).toEqual(["a", "b"]);
  });

  it("gère un chemin en Y : un chapitre qui exige DEUX prérequis est au palier suivant", () => {
    // a -> b, a -> c, (b ET c) -> d  ==> d au palier 2
    const tiers = tiersOf([
      chap("a"),
      chap("b", ["a"]),
      chap("c", ["a"]),
      chap("d", ["b", "c"]),
    ]);
    expect(idsAt(tiers, 0)).toEqual(["a"]);
    expect(idsAt(tiers, 1)).toEqual(["b", "c"]);
    expect(idsAt(tiers, 2)).toEqual(["d"]);
  });

  it("prend le plus LONG chemin de prérequis (max, pas min)", () => {
    // e exige a (court) ET d (long, palier 2) => e au palier 3
    const tiers = tiersOf([
      chap("a"),
      chap("b", ["a"]),
      chap("c", ["a"]),
      chap("d", ["b", "c"]),
      chap("e", ["a", "d"]),
    ]);
    expect(idsAt(tiers, 3)).toEqual(["e"]);
  });

  it("ne boucle pas sur un cycle dans requires (arête cassée à 0)", () => {
    // x <-> y : garde anti-cycle — termine sans déborder la pile.
    const tiers = tiersOf([chap("x", ["y"]), chap("y", ["x"])]);
    const total = [...tiers.values()].reduce((n, cs) => n + cs.length, 0);
    expect(total).toBe(2); // les deux chapitres sont rangés, pas de récursion infinie
  });
});
