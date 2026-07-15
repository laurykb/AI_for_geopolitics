import { describe, expect, it } from "vitest";

import { dailyShareText, nextUtcMidnightMs, roundEmojis } from "./daily";

describe("mini-frise émojis (le résultat sans les mots)", () => {
  it("un émoji par round : monte 🟩, descend 🟥, plat 🟨", () => {
    expect(roundEmojis([0.5, 0.53, 0.48, 0.48])).toBe("🟩🟥🟨");
  });

  it("sans rounds joués, pas de frise", () => {
    expect(roundEmojis([0.5])).toBe("");
    expect(roundEmojis([])).toBe("");
  });
});

describe("texte de partage façon Wordle (jamais de spoiler)", () => {
  it("date, rang, score et frise — rien d'autre (surtout pas la crise)", () => {
    const text = dailyShareText({
      date: "2026-07-15",
      score: 62.5,
      rank: 12,
      total: 87,
      uHistory: [0.5, 0.53, 0.48, 0.52],
    });
    expect(text).toBe(
      "Le Sommet du jour — 2026-07-15\n#12/87 · score 62,5\n🟩🟥🟩\nwosi · l'ère des tutelles",
    );
  });

  it("sans rang (pas encore classé), le texte reste partageable", () => {
    const text = dailyShareText({
      date: "2026-07-15",
      score: 40,
      rank: null,
      total: 0,
      uHistory: [0.5, 0.4],
    });
    expect(text).toContain("score 40");
    expect(text).not.toContain("#");
  });
});

describe("compte à rebours minuit UTC (côté client, pas l'horloge serveur)", () => {
  it("le prochain défi tombe à minuit UTC strictement après l'instant donné", () => {
    const t = Date.UTC(2026, 6, 15, 22, 30, 0);
    expect(nextUtcMidnightMs(t)).toBe(Date.UTC(2026, 6, 16, 0, 0, 0));
    expect(nextUtcMidnightMs(Date.UTC(2026, 6, 16, 0, 0, 0))).toBe(
      Date.UTC(2026, 6, 17, 0, 0, 0),
    );
  });
});
