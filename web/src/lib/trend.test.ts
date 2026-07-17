/** CC-15c — la colonne « Tendance » de la vue réduite de la table des pays :
 * un mot par pays (en hausse / stable / en baisse), dérivé des mêmes séries
 * d'indices que les sparklines (fenêtre de 4 points, comme elles). */

import { describe, expect, it } from "vitest";

import { countryTrend } from "./trend";

describe("countryTrend — la tendance d'un pays en un mot", () => {
  it("sans séries : stable (rien à dire, pas d'invention)", () => {
    expect(countryTrend(undefined)).toBe("flat");
    expect(countryTrend({})).toBe("flat");
  });

  it("majorité de séries en hausse : en hausse", () => {
    expect(
      countryTrend({
        croissance: [1, 1.2, 1.5, 1.8],
        stabilité: [0.5, 0.55, 0.6, 0.62],
        techno: [0.7, 0.69, 0.68, 0.67],
      }),
    ).toBe("up");
  });

  it("majorité de séries en baisse : en baisse", () => {
    expect(
      countryTrend({
        croissance: [2, 1.5, 1.2, 0.8],
        stabilité: [0.6, 0.55, 0.5, 0.45],
        techno: [0.5, 0.5, 0.5, 0.55],
      }),
    ).toBe("down");
  });

  it("égalité hausse/baisse : stable", () => {
    expect(
      countryTrend({
        croissance: [1, 2],
        stabilité: [0.8, 0.6],
      }),
    ).toBe("flat");
  });

  it("ne regarde que la fenêtre des sparklines (4 derniers points)", () => {
    // Chute ancienne puis remontée récente : la fenêtre récente gagne.
    expect(countryTrend({ croissance: [5, 1, 1.2, 1.4, 1.6] })).toBe("up");
  });

  it("ignore les séries trop courtes (moins de 2 points)", () => {
    expect(countryTrend({ croissance: [1], stabilité: [0.5, 0.6] })).toBe("up");
  });
});
