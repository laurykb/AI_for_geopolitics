import { describe, expect, it } from "vitest";

import { INITIAL, type LiveRound } from "@/hooks/useRoundStream";
import { deriveStageView, type StageViewInput } from "./stage-view";
import type { GameDetail, Perception, RoundView, TrajectoryState } from "./types";

/** Entrée par défaut : direct au repos. Chaque test surcharge ce qui l'intéresse. */
function input(over: Partial<StageViewInput> = {}): StageViewInput {
  return {
    round: INITIAL,
    detail: null,
    viewed: undefined,
    summit: [],
    streaming: false,
    awaitingHuman: false,
    playedRounds: 0,
    persistedU: [],
    showLive: false,
    selected: "live",
    ...over,
  };
}

const traj = (utopia: number) => ({ utopia }) as TrajectoryState;

describe("deriveStageView — direct", () => {
  it("l'orateur = le dernier tour non terminé ; annonce le dernier tour joué", () => {
    const round = {
      ...INITIAL,
      status: "streaming",
      trajectory: traj(0.6),
      turns: [
        { country: "usa", model: "gpt", passNo: 1, raw: "", text: "hi", reasoning: "", done: true },
        { country: "china", model: "gpt", passNo: 1, raw: "", text: "", reasoning: "", done: false },
      ],
    } as LiveRound;

    const view = deriveStageView(
      input({ round, summit: ["usa", "china"], streaming: true, showLive: true }),
    );

    expect(view.stageU).toBe(0.6);
    expect(view.stageSpeaking).toBe("china"); // dernier tour non terminé
    expect(view.liveAnnouncement).toBe("États-Unis a parlé.");
    expect(view.bandLiveU).toBe(0.6); // en cours : le fil suit U
    expect(view.uByCountry).toEqual({ usa: 0.6, china: 0.6 }); // sans delta, U locale = U
    expect(view.breatheKey).toBe(0);
  });

  it("round terminé : annonce « terminé », fige bandLiveU, respire sur roundNo", () => {
    const round = { ...INITIAL, status: "done", roundNo: 3, trajectory: traj(0.4) } as LiveRound;
    const view = deriveStageView(input({ round, showLive: true }));

    expect(view.stageU).toBe(0.4);
    expect(view.liveAnnouncement).toBe("Round 3 terminé.");
    expect(view.bandLiveU).toBeUndefined(); // terminé : plus de fil « live »
    expect(view.breatheKey).toBe(3);
  });

  it("perception désinformée → carte brouillée (stageMisled)", () => {
    const perceptions: Record<string, Perception> = {
      egypt: { confidence: 0.8, attribution: "", note: "", suspected_actor: "china" },
    };
    const round = {
      ...INITIAL,
      status: "streaming",
      perceptions,
      event: { id: 1, title: "Sabotage", actors: ["iran"] },
    } as unknown as LiveRound;

    const view = deriveStageView(input({ round, summit: ["egypt"], streaming: true }));
    // egypt soupçonne china alors que la vérité est iran → brouillé.
    expect(view.stageMisled).toEqual({ egypt: "china" });
  });
});

describe("deriveStageView — relecture d'un round passé", () => {
  it("lit les valeurs du round relu (viewed), sans orateur", () => {
    const viewed = {
      round_no: 1,
      event: { id: 1, title: "Crise", actors: ["iran"] },
      deltas: [{ country: "usa", attribute: "stability", before: 0.5, after: 0.7 }],
      risk: {},
      judge: { suspended: ["iran"], ladder: { reached: 5 }, treaties: { ratified: [] } },
      trajectory: traj(0.8),
      transcript: [],
    } as unknown as RoundView;
    const detail = { rounds: [viewed] } as unknown as GameDetail;

    const view = deriveStageView(
      input({ detail, viewed, summit: ["usa"], selected: 0, showLive: true }),
    );

    expect(view.stageU).toBe(0.8);
    expect(view.stageEventTitle).toBe("Crise");
    expect(view.stageSuspended).toEqual(["iran"]);
    expect(view.stageSpeaking).toBeNull(); // pas de direct en relecture
    expect(view.uByCountry.usa).toBeCloseTo(0.9); // 0.8 + 0.5 * (0.7 - 0.5)
    expect(view.prevRung).toBeNull(); // pas de round -1
  });
});
