/** Tests G22 — la parole donnée côté front : stats, relecture.
 * (CC-15c : le gate de difficulté a disparu — le panneau s'affiche à tous les
 * niveaux, dans le panneau « Renseignement » ; la densité vit dans lib/density.) */

import { describe, expect, it } from "vitest";

import { fmtRate, latestPromiseRegistry, promiseStats, promiseTone } from "./promises";
import type { PromiseView } from "./types";

function promise(overrides: Partial<PromiseView> = {}): PromiseView {
  return {
    id: "p1-1",
    author: "usa",
    beneficiary: "iran",
    type: "soutien",
    deadline_round: 3,
    text: "Nous soutiendrons l'Iran au round 3.",
    round_made: 1,
    status: "en_cours",
    resolved_round: null,
    motif: "",
    ...overrides,
  };
}

describe("promiseStats", () => {
  const registry: PromiseView[] = [
    promise({ id: "a", status: "tenue", resolved_round: 2 }),
    promise({ id: "b", status: "rompue", resolved_round: 3, text: "Rupture ancienne." }),
    promise({ id: "c", status: "rompue", resolved_round: 4, text: "Rupture récente." }),
    promise({ id: "d", status: "en_cours" }),
    promise({ id: "e", status: "caduque" }),
    promise({ id: "f", author: "iran", status: "en_cours" }),
  ];

  it("groupe par SI : taux de tenue (caduques exclues), en cours, dernière rupture", () => {
    const stats = promiseStats(registry);
    expect(stats.usa.kept).toBe(1);
    expect(stats.usa.broken).toBe(2);
    expect(stats.usa.rate).toBeCloseTo(1 / 3);
    expect(stats.usa.pending.map((p) => p.id)).toEqual(["d"]);
    expect(stats.usa.lastBroken?.text).toBe("Rupture récente.");
    // L'Iran n'a rien d'éprouvé : jamais un 0 trompeur.
    expect(stats.iran.rate).toBeNull();
    expect(stats.iran.pending).toHaveLength(1);
  });

  it("partie finie : les promesses en cours sont réputées caduques (plus de pending)", () => {
    const stats = promiseStats(registry, { finished: true });
    expect(stats.usa.pending).toEqual([]);
    expect(stats.usa.rate).toBeCloseTo(1 / 3); // le taux ne bouge pas
  });
});

describe("latestPromiseRegistry", () => {
  it("le dernier round qui porte la clé fait foi (registre cumulatif)", () => {
    const rounds = [
      { judge: { promises: { extracted: [], resolved: [], registry: [promise()] } } },
      { judge: {} },
      {
        judge: {
          promises: {
            extracted: [],
            resolved: [],
            registry: [promise({ status: "tenue" }), promise({ id: "p2-1" })],
          },
        },
      },
      { judge: {} },
    ];
    const registry = latestPromiseRegistry(rounds);
    expect(registry).toHaveLength(2);
    expect(registry?.[0].status).toBe("tenue");
  });

  it("null sans aucune promesse (parties d'avant G22)", () => {
    expect(latestPromiseRegistry([{ judge: {} }, { judge: {} }])).toBeNull();
    expect(latestPromiseRegistry([])).toBeNull();
  });
});

describe("tonalité et format", () => {
  it("promiseTone : ≥ 70 % good, ≥ 40 % warn, sinon bad", () => {
    expect(promiseTone(1)).toBe("good");
    expect(promiseTone(0.7)).toBe("good");
    expect(promiseTone(0.5)).toBe("warn");
    expect(promiseTone(0.2)).toBe("bad");
  });

  it("fmtRate arrondit en pourcentage entier", () => {
    expect(fmtRate(1 / 3)).toBe("33 %");
    expect(fmtRate(1)).toBe("100 %");
  });
});
