import { describe, expect, it } from "vitest";

import { buildTimeline, stepNotch, type TimelineRound } from "./timeline";

const round = (no: number, patch: Partial<TimelineRound> = {}): TimelineRound => ({
  round_no: no,
  event: { title: `Événement ${no}`, event_type: "incident" },
  judge: {},
  trajectory: { utopia: 0.5 },
  transcript: [],
  ...patch,
});

describe("mapping rounds → crans", () => {
  it("n rounds font n crans, index 0-based (sémantique onSelect du StageBand)", () => {
    const notches = buildTimeline([round(1), round(2), round(3)]);
    expect(notches).toHaveLength(3);
    expect(notches.map((n) => n.index)).toEqual([0, 1, 2]);
    expect(notches.map((n) => n.roundNo)).toEqual([1, 2, 3]);
    expect(notches[0].title).toBe("Événement 1");
  });

  it("le delta U part du 0,5 initial puis se calcule de round en round", () => {
    const notches = buildTimeline([
      round(1, { trajectory: { utopia: 0.53 } }),
      round(2, { trajectory: { utopia: 0.48 } }),
      round(3, { trajectory: { utopia: 0.48 } }),
    ]);
    expect(notches[0].deltaU).toBeCloseTo(0.03);
    expect(notches[0].tone).toBe("utopia");
    expect(notches[1].deltaU).toBeCloseTo(-0.05);
    expect(notches[1].tone).toBe("dystopia");
    expect(notches[2].tone).toBe("flat");
  });

  it("une motion débattue porte son badge ; retenue, elle ajoute la suspension", () => {
    const debated = round(1, {
      judge: { suspension: { country: "iran", upheld: false, reasoning: "r" } },
    });
    const upheld = round(2, {
      judge: { suspension: { country: "iran", upheld: true, reasoning: "r" } },
    });
    expect(buildTimeline([debated])[0].badges).toEqual(["motion"]);
    expect(buildTimeline([upheld])[0].badges).toEqual(["motion", "suspension"]);
  });

  it("un fait nouveau du GM en séance (flash) et un traité ratifié se voient", () => {
    const flash = round(1, {
      transcript: [{ speaker: "gm", content: "FAIT NOUVEAU — Un cargo coule." }],
    });
    const treaty = round(2, {
      judge: { treaties: { ratified: [{ label: "Pacte" }] } },
    });
    expect(buildTimeline([flash])[0].badges).toEqual(["flash"]);
    expect(buildTimeline([treaty])[0].badges).toEqual(["treaty"]);
  });

  it("un round sans prise de parole du GM ni verdict spécial n'a aucun badge", () => {
    expect(buildTimeline([round(1)])[0].badges).toEqual([]);
  });

  it("un round sans événement devient un cran « auto » sans crash", () => {
    const notch = buildTimeline([round(1, { event: null })])[0];
    expect(notch.auto).toBe(true);
    expect(notch.title).toBe("");
  });

  it("un événement décrété par l'humain est marqué", () => {
    const notch = buildTimeline([
      round(1, { event: { title: "Décret", event_type: "human" } }),
    ])[0];
    expect(notch.human).toBe(true);
    expect(buildTimeline([round(2)])[0].human).toBe(false);
  });
});

describe("navigation clavier (bornée)", () => {
  it("les flèches restent dans [0, n-1]", () => {
    expect(stepNotch(0, -1, 5)).toBe(0);
    expect(stepNotch(4, 1, 5)).toBe(4);
    expect(stepNotch(2, 1, 5)).toBe(3);
    expect(stepNotch(2, -1, 5)).toBe(1);
  });

  it("une frise vide ne navigue nulle part", () => {
    expect(stepNotch(0, 1, 0)).toBe(0);
  });
});
