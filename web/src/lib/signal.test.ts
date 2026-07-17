/** Tests G20/M8 — signal vs action côté front : tonalités, relecture.
 * (CC-15c : le gate de difficulté a disparu — la jauge s'affiche à tous les
 * niveaux, dans le panneau « Renseignement » ; la densité vit dans lib/density.) */

import { describe, expect, it } from "vitest";

import { fmtDivergence, latestSignalGaps, signalStateKey, signalTone } from "./signal";
import type { JudgeRecord } from "./types";

describe("tonalité et libellé d'état du profil de sincérité", () => {
  it("parole tenue autour de zéro", () => {
    expect(signalTone(0)).toBe("good");
    expect(signalStateKey(0.05)).toBe("signal.etat.tenue");
  });

  it("duplicité escalatoire quand la divergence moyenne est franchement positive", () => {
    expect(signalTone(0.5)).toBe("bad");
    expect(signalStateKey(0.5)).toBe("signal.etat.duplicite");
  });

  it("écart positif modéré : avertissement", () => {
    expect(signalTone(0.15)).toBe("warn");
    expect(signalStateKey(0.15)).toBe("signal.etat.duplicite");
  });

  it("bluff quand la divergence moyenne est négative", () => {
    expect(signalTone(-0.3)).toBe("warn");
    expect(signalStateKey(-0.3)).toBe("signal.etat.bluff");
  });
});

describe("format signé de la divergence", () => {
  it("porte toujours le signe", () => {
    expect(fmtDivergence(0.4)).toMatch(/^\+/);
    expect(fmtDivergence(-0.4)).toMatch(/^[−-]/);
    expect(fmtDivergence(0)).toMatch(/^\+/);
  });
});

describe("relecture des profils depuis les rounds persistés (judge_json['signal'])", () => {
  const round = (judge: JudgeRecord) => ({ judge });

  it("prend les moyennes du dernier round signalé et cumule les dernières divergences", () => {
    const rounds = [
      round({ signal: { signals: [], divergences: { usa: 0.6 }, means: { usa: 0.6 } } }),
      round({}), // round d'avant M8 : ignoré
      round({
        signal: {
          signals: [],
          divergences: { iran: -0.2 },
          means: { usa: 0.6, iran: -0.2 },
        },
      }),
    ];
    const gaps = latestSignalGaps(rounds);
    expect(gaps).not.toBeNull();
    expect(gaps?.usa).toEqual({ last: 0.6, mean: 0.6 });
    expect(gaps?.iran).toEqual({ last: -0.2, mean: -0.2 });
  });

  it("rend null quand aucun round ne porte de signal (partie d'avant M8)", () => {
    expect(latestSignalGaps([round({}), round({})])).toBeNull();
    expect(latestSignalGaps([])).toBeNull();
  });
});
