/** La vitrine publique /r/{id} parle le langage de tous (audit n°10) : la phrase du
 * monde remplace « U 0.42 → 0.61 », le delta d'un moment clé remplace « ΔU +0.003 ». */

import { describe, expect, it } from "vitest";

import { deltaSentence, worldSentence } from "./public";

describe("worldSentence — la phrase du monde", () => {
  it("dit « mieux » quand le monde a progressé, sur une échelle 0-100", () => {
    expect(worldSentence(0.42, 0.61)).toBe(
      "Le monde a fini mieux qu'il n'a commencé : 42 → 61 sur 100",
    );
  });

  it("dit « moins bien » quand le monde a reculé", () => {
    expect(worldSentence(0.61, 0.42)).toBe(
      "Le monde a fini moins bien qu'il n'a commencé : 61 → 42 sur 100",
    );
  });

  it("dit « comme il a commencé » quand rien n'a bougé", () => {
    expect(worldSentence(0.5, 0.5)).toBe(
      "Le monde a fini comme il a commencé : 50 → 50 sur 100",
    );
  });

  it("ne contient jamais le sigle U ni la notation brute", () => {
    expect(worldSentence(0.42, 0.61)).not.toMatch(/\bU\b|0\.\d/);
  });
});

describe("deltaSentence — un moment clé en points lisibles", () => {
  it("écrit les gains en dixièmes de point, virgule française", () => {
    expect(deltaSentence(0.003)).toBe("+0,3 pt pour le monde");
  });

  it("écrit les pertes avec le signe moins typographique", () => {
    expect(deltaSentence(-0.012)).toBe("−1,2 pt pour le monde");
  });
});
