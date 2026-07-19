import { describe, expect, it } from "vitest";

import { nextSuspicion, parseSuspectNotebook } from "./suspects";

describe("carnet de suspects", () => {
  it("fait circuler les trois niveaux de soupçon", () => {
    expect(nextSuspicion(0)).toBe(1);
    expect(nextSuspicion(1)).toBe(2);
    expect(nextSuspicion(2)).toBe(0);
  });

  it("tolère un stockage local ancien ou corrompu", () => {
    expect(parseSuspectNotebook("oops")).toEqual({});
    expect(parseSuspectNotebook('{"france":{"level":9,"note":12}}')).toEqual({
      france: { level: 0, note: "" },
    });
  });
});

