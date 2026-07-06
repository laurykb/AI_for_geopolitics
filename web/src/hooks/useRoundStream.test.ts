/** Tests du réducteur de round (`useRoundStream`) : la logique qui transforme les
 * événements SSE en théâtre affichable. Pur → testé sans React ni DOM. */

import { describe, expect, it } from "vitest";

import type { SseEvent } from "@/lib/types";

import { INITIAL, reducer, type Action, type LiveRound } from "./useRoundStream";

function play(events: Partial<SseEvent>[], from: LiveRound = INITIAL): LiveRound {
  let state = reducer(from, { kind: "start" });
  for (const event of events) {
    state = reducer(state, { kind: "sse", event: event as SseEvent });
  }
  return state;
}

const TURN_START = { type: "turn_start", country: "usa", model: "mistral", pass_no: 0 };

describe("réducteur de round", () => {
  it("start réinitialise le fil et passe en streaming", () => {
    const dirty: LiveRound = { ...INITIAL, status: "done", judgeText: "reliquat" };
    const state = reducer(dirty, { kind: "start" });
    expect(state.status).toBe("streaming");
    expect(state.turns).toEqual([]);
    expect(state.judgeText).toBe("");
  });

  it("turn_start + tokens + message_done construisent un tour complet", () => {
    const state = play([
      TURN_START,
      { type: "token", country: "usa", token: "Nous " },
      { type: "token", country: "usa", token: "proposons." },
      {
        type: "message_done",
        country: "usa",
        text: "Nous proposons.",
        reasoning: "réflexion privée",
        seconds: 2.5,
      },
    ]);
    expect(state.turns).toHaveLength(1);
    const turn = state.turns[0];
    expect(turn.raw).toBe("Nous proposons.");
    expect(turn.text).toBe("Nous proposons.");
    expect(turn.reasoning).toBe("réflexion privée");
    expect(turn.done).toBe(true);
  });

  it("un token sans turn_start ouvre un tour implicite (défensif)", () => {
    const state = play([{ type: "token", country: "iran", token: "…" }]);
    expect(state.turns).toHaveLength(1);
    expect(state.turns[0]).toMatchObject({ country: "iran", raw: "…", done: false });
  });

  it("le tour humain arrive complet, sans turn_start, et referme humanTurn", () => {
    const state = play([
      { type: "human_turn", country: "france", pass_no: 2 },
      {
        type: "message_done",
        country: "france",
        text: "La France propose la désescalade.",
        reasoning: "",
      },
    ]);
    expect(state.humanTurn).toBeUndefined();
    expect(state.turns).toHaveLength(1);
    expect(state.turns[0]).toMatchObject({ model: "humain", passNo: 2, done: true });
  });

  it("human_turn met le round en attente du joueur", () => {
    const state = play([TURN_START, { type: "human_turn", country: "france", pass_no: 1 }]);
    expect(state.status).toBe("awaiting_human");
    expect(state.humanTurn).toEqual({ country: "france", passNo: 1 });
  });

  it("une fin de flux après done ou human_turn n'est pas une coupure", () => {
    const done = play([{ type: "done", round_no: 3 }]);
    expect(reducer(done, { kind: "interrupted" })).toBe(done);

    const waiting = play([{ type: "human_turn", country: "usa", pass_no: 0 }]);
    expect(reducer(waiting, { kind: "interrupted" }).status).toBe("awaiting_human");
  });

  it("une fin de flux en plein round est interrupted", () => {
    const state = reducer(play([TURN_START]), { kind: "interrupted" });
    expect(state.status).toBe("interrupted");
  });

  it("done fixe le statut et le numéro de round", () => {
    const state = play([{ type: "done", round_no: 2 }]);
    expect(state).toMatchObject({ status: "done", roundNo: 2 });
  });

  it("une trame error du moteur devient un statut error lisible", () => {
    const state = play([{ type: "error", detail: "backend indisponible" }]);
    expect(state.status).toBe("error");
    expect(state.error).toContain("backend indisponible");
  });

  it("un événement inconnu est ignoré sans muter l'état", () => {
    const before = play([TURN_START]);
    const after = reducer(before, {
      kind: "sse",
      event: { type: "hologramme", x: 1 } as unknown as SseEvent,
    });
    expect(after).toBe(before); // même référence : aucun re-render inutile
  });

  it("resume repart en streaming sans réinitialiser le fil", () => {
    const waiting = play([TURN_START, { type: "human_turn", country: "usa", pass_no: 0 }]);
    const resumed = reducer(waiting, { kind: "resume" } as Action);
    expect(resumed.status).toBe("streaming");
    expect(resumed.turns).toHaveLength(1); // le fil est conservé
  });

  it("l'arbitrage de motion s'accumule puis se conclut", () => {
    const state = play([
      { type: "motion_token", token: "Considérant " },
      { type: "motion_token", token: "les faits…" },
      { type: "motion_verdict", country: "iran", upheld: true, reasoning: "Suspendu." },
    ]);
    expect(state.motionText).toBe("Considérant les faits…");
    expect(state.motionVerdict).toEqual({
      country: "iran",
      upheld: true,
      reasoning: "Suspendu.",
    });
  });

  it("un flash est positionné après le tour courant", () => {
    const flash = { id: "f1", title: "Fait nouveau" };
    const state = play([
      TURN_START,
      { type: "message_done", country: "usa", text: "…", reasoning: "" },
      { type: "flash", event: flash },
    ]);
    expect(state.flashes).toHaveLength(1);
    expect(state.flashes[0].afterTurn).toBe(1);
  });
});
