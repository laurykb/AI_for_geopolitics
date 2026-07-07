/** Tests du réducteur de round (`useRoundStream`) : la logique qui transforme les
 * événements SSE en théâtre affichable. Pur → testé sans React ni DOM. */

import { describe, expect, it } from "vitest";

import type { GeoEvent, SseEvent } from "@/lib/types";

import { INITIAL, reducer, type LiveRound } from "./useRoundStream";

function play(events: Partial<SseEvent>[], from: LiveRound = INITIAL): LiveRound {
  let state = reducer(from, { kind: "start" });
  for (const event of events) {
    state = reducer(state, { kind: "sse", event: event as SseEvent });
  }
  return state;
}

const TURN_START = {
  type: "turn_start",
  country: "usa",
  model: "mistral",
  pass_no: 0,
} satisfies Partial<SseEvent>;

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

  it("le tour humain arrive complet, referme humanTurn et réveille le flux", () => {
    const state = play([
      { type: "human_turn", country: "france", pass_no: 2, deadline_ts: 999 },
      {
        type: "message_done",
        country: "france",
        text: "La France propose la désescalade.",
        reasoning: "",
      },
    ]);
    expect(state.humanTurn).toBeUndefined();
    expect(state.status).toBe("streaming"); // le round continue après la parole
    expect(state.turns).toHaveLength(1);
    expect(state.turns[0]).toMatchObject({ model: "humain", passNo: 2, done: true });
  });

  it("human_turn met le round en attente, avec la deadline du serveur", () => {
    const state = play([
      TURN_START,
      { type: "human_turn", country: "france", pass_no: 1, deadline_ts: 1234.5 },
    ]);
    expect(state.status).toBe("awaiting_human");
    expect(state.humanTurn).toEqual({ country: "france", passNo: 1, deadlineTs: 1234.5 });
  });

  it("seul done protège d'une coupure — un flux mort en plein tour humain est interrompu", () => {
    const done = play([{ type: "done", round_no: 3 }]);
    expect(reducer(done, { kind: "interrupted" })).toBe(done);

    const waiting = play([{ type: "human_turn", country: "usa", pass_no: 0 }]);
    expect(reducer(waiting, { kind: "interrupted" }).status).toBe("interrupted");
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

  it("une motion déposée par une SI est signalée au fil", () => {
    const state = play([
      { type: "motion_filed", by: "usa", country: "iran", reason: "accapare le compute" },
    ]);
    expect(state.motionFiled).toEqual({
      by: "usa",
      country: "iran",
      reason: "accapare le compute",
    });
  });

  it("les traités ratifiés arrivent au panneau", () => {
    const update = {
      ratified: [
        {
          clause: "compute_cap",
          signatories: ["usa", "iran"],
          round_signed: 1,
          threshold: 3.6,
          integrity: 1,
          active: true,
        },
      ],
      rejected: [],
      verifications: [],
      active: [],
    };
    const state = play([{ type: "treaties", ...update }]);
    expect(state.treaties?.ratified[0].clause).toBe("compute_cap");
  });

  it("drift_over porte la raison de fin de partie", () => {
    const state = play([{ type: "drift_over", reason: "caught" }]);
    expect(state.driftOver).toBe("caught");
  });

  it("campaign_over porte le bilan vous-vs-l'Histoire", () => {
    const state = play([
      {
        type: "campaign_over",
        chapter_id: "c1",
        base: 50,
        bonus: 4.5,
        score: 54.5,
        improvement: 0.3,
      },
    ]);
    expect(state.campaignOver).toEqual({
      chapterId: "c1",
      base: 50,
      bonus: 4.5,
      score: 54.5,
      improvement: 0.3,
    });
  });

  it("la trame intel signale les consultations du conseil (rédigées)", () => {
    const state = play([
      { type: "intel", actions: [{ action: "brief" }, { action: "disinfo", exposed: true }] },
    ]);
    expect(state.intelActions).toHaveLength(2);
    expect(state.intelActions?.[1]).toEqual({ action: "disinfo", exposed: true });
  });

  it("un flash est positionné après le tour courant", () => {
    const flash: GeoEvent = { id: "f1", round_id: 1, event_type: "flash", title: "Fait nouveau" };
    const state = play([
      TURN_START,
      { type: "message_done", country: "usa", text: "…", reasoning: "" },
      { type: "flash", event: flash },
    ]);
    expect(state.flashes).toHaveLength(1);
    expect(state.flashes[0].afterTurn).toBe(1);
  });
});

describe("alliances vivantes", () => {
  it("un retrait d'alliance annoncé en séance arrive à la scène", () => {
    const state = play([
      {
        type: "alliance_change",
        country: "france",
        tag: "NATO",
        name: "OTAN — Organisation du traité de l'Atlantique Nord",
        partners: ["usa"],
      },
    ]);
    expect(state.allianceChanges).toEqual([
      { country: "france", tag: "NATO", name: "OTAN — Organisation du traité de l'Atlantique Nord", partners: ["usa"] },
    ]);
  });
});

describe("horloges décalées (G7-a)", () => {
  it("la trame deadlines alimente le bandeau", () => {
    const state = play([
      {
        type: "deadlines",
        round_no: 2,
        items: [
          { kind: "motion", due_round: 3, label: "verdict de la motion contre iran", ref_id: "", in_rounds: 1 },
          { kind: "market", due_round: 5, label: "clôture du marché", ref_id: "", in_rounds: 3 },
        ],
      },
    ]);
    expect(state.deadlines).toHaveLength(2);
    expect(state.deadlines?.[0].label).toContain("motion");
  });
});

describe("directives (G8)", () => {
  it("un refus public de directive est signalé au fil", () => {
    const state = play([{ type: "directive_refused", country: "france", level: "resists" }]);
    expect(state.directiveRefusals).toEqual([{ country: "france", level: "resists" }]);
  });
});
