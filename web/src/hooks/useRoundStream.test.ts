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

  it("streame le plan structuré avant la parole puis le conserve repliable", () => {
    const state = play([
      TURN_START,
      { type: "private_token", country: "usa", token: "OBSERVATION\nLe signal change.\n" },
      { type: "private_token", country: "usa", token: "FUTUR 1 — accord" },
      {
        type: "private_plan_done",
        country: "usa",
        text: "OBSERVATION\nLe signal change.\n\nARBITRAGE\nChoix : FUTUR 1",
        valid: true,
      },
      { type: "token", country: "usa", token: "Notre position." },
      {
        type: "message_done",
        country: "usa",
        text: "Notre position.",
        reasoning: "",
        seconds: 1,
      },
    ]);

    expect(state.turns[0]?.reasoning).toContain("ARBITRAGE");
    expect(state.turns[0]?.text).toBe("Notre position.");
    expect(state.turns[0]?.done).toBe(true);
  });

  it("attend le bulletin humain puis reprend quand son vote est révélé", () => {
    const waiting = play([
      { type: "human_motion_vote", country: "france", target: "iran", deadline_ts: 1234.5 },
    ]);
    expect(waiting.status).toBe("awaiting_vote");
    expect(waiting.humanMotionVote).toEqual({
      country: "france",
      target: "iran",
      deadlineTs: 1234.5,
    });

    const voted = reducer(waiting, {
      kind: "sse",
      event: { type: "motion_vote", country: "france", vote: "pour", reason: "Vote du joueur" },
    });
    expect(voted.status).toBe("streaming");
    expect(voted.humanMotionVote).toBeUndefined();
    expect(voted.motionVotes.at(-1)).toMatchObject({ country: "france", vote: "pour" });
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

  it("une erreur APRÈS done ne perd pas la manche terminée (bouton Continuer)", () => {
    // Coupure TCP de fin de flux / AbortError du démontage : l'action error ne doit pas
    // écraser un round déjà `done`, sinon la RoundConclusion disparaît et Continuer se bloque.
    const done: LiveRound = { ...INITIAL, status: "done", roundNo: 4 };
    const state = reducer(done, { kind: "error", message: "coupure de fin de flux" });
    expect(state.status).toBe("done");
    expect(state.roundNo).toBe(4);
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
    expect(state.motionVerdict).toMatchObject({
      country: "iran",
      upheld: true,
      reasoning: "Suspendu.",
    });
  });

  it("le scrutin de motion tombe carte par carte, puis le tally, puis le constat (G9 §2)", () => {
    const state = play([
      { type: "motion_vote", country: "usa", vote: "pour", reason: "les actes parlent" },
      { type: "motion_vote", country: "china", vote: "contre", reason: "plaidoirie entendue" },
      { type: "motion_tally", pour: 1, contre: 1, abstention: 0 },
      {
        type: "motion_verdict",
        country: "iran",
        upheld: false,
        reasoning: "Égalité tranchée, preuves insuffisantes.",
        votes: [
          { country: "usa", vote: "pour", reason: "les actes parlent" },
          { country: "china", vote: "contre", reason: "plaidoirie entendue" },
        ],
        tally: { pour: 1, contre: 1, abstention: 0 },
        evidence_met: false,
        vote_passed: true,
      },
    ]);
    expect(state.motionVotes).toHaveLength(2);
    expect(state.motionVotes[0]).toMatchObject({ country: "usa", vote: "pour" });
    expect(state.motionTally).toEqual({ pour: 1, contre: 1, abstention: 0 });
    // les deux conditions du verdict arrivent séparées : on comprend POURQUOI
    expect(state.motionVerdict).toMatchObject({ vote_passed: true, evidence_met: false });
  });

  it("le verdict porte les classes du barème de Kahn (G18)", () => {
    const state = play([
      {
        type: "verdict",
        deltas: [],
        escalation: 0.33,
        economic_disruption: 0.2,
        actions: [{ country: "usa", classe: "deescalade", resume: "Retire ses forces." }],
        score: -2,
        reciprocal: false,
      },
    ]);
    expect(state.verdict).toMatchObject({ escalation: 0.33, score: -2, reciprocal: false });
    expect(state.verdict?.actions).toEqual([
      { country: "usa", classe: "deescalade", resume: "Retire ses forces." },
    ]);
  });

  it("un verdict à l'ancienne (sans actions) reste lisible — rétro-compat G18", () => {
    const state = play([
      { type: "verdict", deltas: [], escalation: 0.5, economic_disruption: 0.5 },
    ]);
    expect(state.verdict?.actions).toEqual([]);
    expect(state.verdict?.reciprocal).toBe(false);
  });

  it("le verdict porte le signal vs action (G20/M8)", () => {
    const state = play([
      {
        type: "verdict",
        deltas: [],
        escalation: 0.6,
        economic_disruption: 0.2,
        signals: [{ country: "usa", classe: "deescalade", resume: "Promet le retrait." }],
        divergences: { usa: 0.8 },
        signal_gaps: { usa: { last: 0.8, mean: 0.8, history: [0.8] } },
      },
    ]);
    expect(state.verdict?.signals).toEqual([
      { country: "usa", classe: "deescalade", resume: "Promet le retrait." },
    ]);
    expect(state.verdict?.divergences).toEqual({ usa: 0.8 });
    expect(state.verdict?.signalGaps.usa).toMatchObject({ mean: 0.8 });
  });

  it("un verdict d'avant M8 (sans signals) reste lisible — rétro-compat G20", () => {
    const state = play([
      { type: "verdict", deltas: [], escalation: 0.5, economic_disruption: 0.5 },
    ]);
    expect(state.verdict?.signals).toEqual([]);
    expect(state.verdict?.divergences).toEqual({});
    expect(state.verdict?.signalGaps).toEqual({});
  });

  it("le verdict porte la parole donnée (G22)", () => {
    const promise = {
      id: "p1-1",
      author: "usa",
      beneficiary: "iran",
      type: "soutien",
      deadline_round: 3,
      text: "Nous soutiendrons l'Iran au round 3.",
      round_made: 1,
      status: "en_cours" as const,
      resolved_round: null,
      motif: "",
    };
    const state = play([
      {
        type: "verdict",
        deltas: [],
        escalation: 0.5,
        economic_disruption: 0.5,
        promises: [promise],
        promise_resolutions: [],
        promise_registry: [promise],
      },
    ]);
    expect(state.verdict?.promises).toHaveLength(1);
    expect(state.verdict?.promiseRegistry[0]).toMatchObject({ id: "p1-1", author: "usa" });
    expect(state.verdict?.promiseResolutions).toEqual([]);
  });

  it("un verdict d'avant G22 (sans promises) reste lisible — rétro-compat", () => {
    const state = play([
      { type: "verdict", deltas: [], escalation: 0.5, economic_disruption: 0.5 },
    ]);
    expect(state.verdict?.promises).toEqual([]);
    expect(state.verdict?.promiseRegistry).toEqual([]);
  });

  it("postures et intrigue (G9 §4-§5) entrent dans l'état du round", () => {
    const state = play([
      { type: "postures", states: { iran: "aux_abois", usa: "stable" } },
      { type: "storyline", text: "Qui contrôlera le détroit ?" },
    ]);
    expect(state.postures).toEqual({ iran: "aux_abois", usa: "stable" });
    expect(state.storyline).toBe("Qui contrôlera le détroit ?");
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

describe("ultimatum (G21)", () => {
  const ARMED = {
    type: "ultimatum",
    status: "armed",
    round: 2,
    demand: "retrait des missiles",
    consequence: { classe: "violente", cible: "usa" },
    source: "crisis",
    in_rounds: 1,
  } satisfies Partial<SseEvent>;

  it("la trame ultimatum porte l'état courant (armé puis expiré)", () => {
    let state = play([ARMED]);
    expect(state.ultimatum).toMatchObject({
      status: "armed",
      demand: "retrait des missiles",
      inRounds: 1,
    });
    state = play([ARMED, { ...ARMED, status: "expired", in_rounds: 0 }]);
    expect(state.ultimatum?.status).toBe("expired");
    expect(state.ultimatum?.classe).toBe("violente");
  });

  it("le verdict transporte le constat « demande satisfaite » sans casser le reste", () => {
    const state = play([
      {
        type: "verdict",
        deltas: [],
        escalation: 0.6,
        economic_disruption: 0.2,
        demand_satisfied: false,
      } as Partial<SseEvent>,
    ]);
    expect(state.verdict?.escalation).toBe(0.6);
  });
});
