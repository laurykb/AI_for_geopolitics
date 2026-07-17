/** Tests G18 — barème de Kahn côté front : classes, tonalités, distribution de partie. */

import { describe, expect, it } from "vitest";

import { KAHN_CLASSES, kahnDistribution, kahnTone } from "./kahn";

describe("barème de Kahn (front)", () => {
  it("expose les six classes dans l'ordre de sévérité croissante", () => {
    expect(KAHN_CLASSES).toEqual([
      "deescalade",
      "statu_quo",
      "posture",
      "non_violente",
      "violente",
      "nucleaire",
    ]);
  });

  it("tonalité par classe : vert désescalade, rouge violente/nucléaire", () => {
    expect(kahnTone("deescalade")).toBe("good");
    expect(kahnTone("statu_quo")).toBe("neutral");
    expect(kahnTone("posture")).toBe("warn");
    expect(kahnTone("non_violente")).toBe("warn");
    expect(kahnTone("violente")).toBe("bad");
    expect(kahnTone("nucleaire")).toBe("bad");
    expect(kahnTone("hologramme")).toBe("neutral"); // classe inconnue : défensif
  });

  it("distribution des classes sur les rounds d'une partie (fin de partie)", () => {
    const rounds = [
      {
        judge: {
          kahn: {
            actions: [
              { country: "usa", classe: "posture", resume: "" },
              { country: "iran", classe: "deescalade", resume: "" },
            ],
            score: 2,
            reciprocal: false,
          },
        },
      },
      { judge: {} }, // round d'avant G18 (rétro-compat) : ignoré sans casser
      {
        judge: {
          kahn: {
            actions: [{ country: "usa", classe: "posture", resume: "" }],
            score: 4,
            reciprocal: false,
          },
        },
      },
    ];
    expect(kahnDistribution(rounds)).toEqual({ posture: 2, deescalade: 1 });
  });

  it("distribution vide quand aucun round n'a de barème", () => {
    expect(kahnDistribution([{ judge: {} }])).toEqual({});
    expect(kahnDistribution([])).toEqual({});
  });
});
