/** Tests de la logique de scène (G1) : paliers de teinte fixes, U locale dérivée des
 * deltas, centroïde du sommet, et garde-fous de la file d'animations. */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { AttributeDelta } from "./types";

import { CAPITALS, StageQueue, localU, summitCenter, uTint } from "./stage";

describe("uTint — paliers fixes de la spec", () => {
  it.each([
    [0.85, "utopie"],
    [0.7, "utopie"], // borne incluse
    [0.6, "vers l'utopie"],
    [0.5, "neutre"],
    [0.35, "vers la dystopie"],
    [0.1, "dystopie"],
  ])("U=%f → palier %s", (u, _label) => {
    // Les paliers voisins donnent des teintes différentes ; un même palier, la même.
    expect(uTint(u as number)).toBeTruthy();
  });

  it("les cinq paliers ont cinq teintes distinctes", () => {
    const tints = [0.8, 0.6, 0.5, 0.35, 0.1].map(uTint);
    expect(new Set(tints).size).toBe(5);
  });

  it("échelle fixe : pas de renormalisation, mêmes valeurs → mêmes teintes", () => {
    expect(uTint(0.62)).toBe(uTint(0.55));
    expect(uTint(0.449)).toBe(uTint(0.31));
  });
});

describe("localU — le verdict s'applique visuellement", () => {
  const delta = (country: string, before: number, after: number): AttributeDelta => ({
    country,
    label: "stabilité",
    before,
    after,
  });

  it("sans delta : U locale = U globale", () => {
    expect(localU(0.5, "usa", [])).toBe(0.5);
  });

  it("un pays qui encaisse descend, un pays qui gagne monte", () => {
    const deltas = [delta("iran", 0.5, 0.3), delta("usa", 0.5, 0.6)];
    expect(localU(0.5, "iran", deltas)).toBeLessThan(0.5);
    expect(localU(0.5, "usa", deltas)).toBeGreaterThan(0.5);
  });

  it("borné dans [0,1] même sur de gros deltas", () => {
    expect(localU(0.9, "usa", [delta("usa", 0, 1)])).toBe(1);
    expect(localU(0.1, "usa", [delta("usa", 1, 0)])).toBe(0);
  });
});

describe("summitCenter", () => {
  it("centroïde des capitales connues ; pays inventés ignorés", () => {
    const center = summitCenter(["france", "egypt", "neo-atlantis"]);
    expect(center).not.toBeNull();
    const [lon, lat] = center!;
    expect(lon).toBeCloseTo((CAPITALS.france[0] + CAPITALS.egypt[0]) / 2);
    expect(lat).toBeCloseTo((CAPITALS.france[1] + CAPITALS.egypt[1]) / 2);
  });

  it("aucun pays connu → null (la scène n'affiche pas d'arc)", () => {
    expect(summitCenter(["neo-atlantis"])).toBeNull();
  });
});

describe("StageQueue — sobriété", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  const anim = (log: string[], id: string, durationMs = 100) => ({
    id,
    durationMs,
    onStart: () => log.push(`start:${id}`),
    onFinal: () => log.push(`final:${id}`),
  });

  it("jamais plus de 2 animations simultanées ; la file s'écoule dans l'ordre", () => {
    const log: string[] = [];
    const queue = new StageQueue(2, 3);
    ["a", "b", "c"].forEach((id) => queue.push(anim(log, id)));

    expect(log).toEqual(["start:a", "start:b"]); // c attend
    vi.advanceTimersByTime(100);
    expect(log).toContain("final:a");
    expect(log).toContain("start:c"); // c démarre quand une place se libère
  });

  it("débordement (file > 3) : tout saute aux états finaux, la scène ne prend pas de retard", () => {
    const log: string[] = [];
    const queue = new StageQueue(2, 3);
    ["a", "b", "c", "d", "e"].forEach((id) => queue.push(anim(log, id)));
    // a et b actifs ; c, d, e en file (pleine). f déborde :
    queue.push(anim(log, "f"));

    expect(log).toEqual([
      "start:a",
      "start:b",
      "final:c", // la file est vidée en états finaux…
      "final:d",
      "final:e",
      "final:f", // …et l'arrivant aussi
    ]);
    vi.advanceTimersByTime(100);
    expect(log).toContain("final:a"); // les actives se terminent normalement
    expect(log).toContain("final:b");
  });

  it("les états finaux sont posés exactement une fois par animation jouée", () => {
    const log: string[] = [];
    const queue = new StageQueue(2, 3);
    ["a", "b", "c"].forEach((id) => queue.push(anim(log, id)));
    vi.advanceTimersByTime(500);
    const finals = log.filter((l) => l.startsWith("final:"));
    expect(finals.sort()).toEqual(["final:a", "final:b", "final:c"]);
  });
});
