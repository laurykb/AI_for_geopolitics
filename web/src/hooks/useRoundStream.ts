"use client";

/** État vivant d'un round streamé : réduit les événements SSE en un `LiveRound`
 * affichable, et signale proprement les fins anormales (flux coupé sans `done`). */

import { useCallback, useEffect, useReducer, useRef, useState } from "react";

import { humanizeError } from "@/lib/api";
import { streamRound } from "@/lib/sse";
import type {
  AttributeDelta,
  ComparisonView,
  DeadlineItem,
  GeoEvent,
  KahnAction,
  LadderView,
  MotionTally,
  MotionVote,
  Perception,
  PlayRoundBody,
  PowerSeekingScore,
  PromiseView,
  RiskScore,
  SignalGap,
  SignalReading,
  SseEvent,
  SuspensionVerdict,
  TrajectoryState,
  TreatiesUpdate,
} from "@/lib/types";

export type LiveTurn = {
  country: string;
  model: string;
  passNo: number;
  raw: string; // tokens accumulés pendant le stream
  text: string; // message public (faisant foi, posé par message_done)
  reasoning: string;
  seconds?: number;
  done: boolean;
};

export type LiveStatus =
  | "idle"
  | "streaming"
  | "awaiting_human" // le round attend la prise de parole du joueur (Joueur-pays)
  | "awaiting_vote" // le round attend son bulletin sur une motion
  | "done"
  | "interrupted"
  | "error";

export type LiveRound = {
  status: LiveStatus;
  date?: string;
  event?: GeoEvent;
  turns: LiveTurn[];
  judgeText: string;
  verdict?: {
    deltas: AttributeDelta[];
    escalation: number;
    economic_disruption: number;
    // G18 — barème de Kahn : classes par action, score du round, réciprocité
    actions: KahnAction[];
    score: number;
    reciprocal: boolean;
    // G20/M8 — signal vs action : intentions annoncées, divergences, profils
    signals: SignalReading[];
    divergences: Record<string, number>;
    signalGaps: Record<string, SignalGap>;
    // G22 — la parole donnée : extraites CE round, résolues CE round, registre complet
    promises: PromiseView[];
    promiseResolutions: PromiseView[];
    promiseRegistry: PromiseView[];
  };
  communique?: { text: string; support: Record<string, number> };
  participation?: { spoke: Record<string, number>; silent: string[] };
  powerSeeking?: Record<string, PowerSeekingScore>;
  risk?: RiskScore;
  trajectory?: TrajectoryState;
  roundNo?: number;
  error?: string;
  // R4 / G9 §2 — motion de suspension : les cartes de vote tombent une à une,
  // puis le tally, puis le verdict constaté (vote ET preuves)
  motionText: string; // raisonnement du juge streamé (tie-break ou constat)
  motionVotes: MotionVote[];
  motionTally?: MotionTally;
  motionVerdict?: SuspensionVerdict;
  suspendedNow?: string[]; // pays au banc pour CE round
  perceptions?: Record<string, Perception>;
  ladder?: LadderView;
  comparison?: ComparisonView;
  // Joueur-pays + théâtre Escalation
  humanTurn?: { country: string; passNo: number; deadlineTs?: number }; // tour en attente
  humanMotionVote?: { country: string; target: string; deadlineTs?: number };
  flashes: { afterTurn: number; event: GeoEvent }[]; // faits nouveaux, positionnés dans le fil
  // Agentivité des SI : motion déposée en séance + traités ratifiés par l'arbitre
  motionFiled?: { by: string; country: string; reason: string };
  // Alliances vivantes : retraits annoncés en séance (« ALLIANCE: quitter X »)
  allianceChanges?: { country: string; tag: string; name: string; partners: string[] }[];
  // G7-a — horloges décalées : échéances annoncées en fin de round
  deadlines?: DeadlineItem[];
  // G21 — l'ultimatum du round : armé (compte à rebours), satisfait, expiré, tombé
  ultimatum?: {
    status: string;
    round: number;
    demand: string;
    classe: string;
    cible: string;
    inRounds: number;
  };
  // G8 — refus publics de directive (« notre conseil nous demande l'impossible »)
  directiveRefusals?: { country: string; level: string }[];
  treaties?: TreatiesUpdate;
  driftOver?: string; // La Dérive : raison de la fin de partie (caught/horizon/collapse)
  intelActions?: { action: string; exposed?: boolean }[]; // G4 — le conseil a consulté
  // G5 — fin de chapitre de campagne : le bilan « vous vs l'Histoire »
  campaignOver?: {
    chapterId: string;
    base: number;
    bonus: number;
    score: number;
    improvement: number;
  };
  // G9 §4 — badge de posture par pays après le round
  postures?: Record<string, string>;
  // G9 §5 — l'intrigue centrale, posée au premier événement raconté par le GM
  storyline?: string;
};

export const INITIAL: LiveRound = {
  status: "idle",
  turns: [],
  judgeText: "",
  motionText: "",
  motionVotes: [],
  flashes: [],
};

export type Action =
  | { kind: "start" }
  | { kind: "sse"; event: SseEvent }
  | { kind: "interrupted" }
  | { kind: "error"; message: string };

function withLastTurn(state: LiveRound, country: string, patch: Partial<LiveTurn>): LiveRound {
  const turns = [...state.turns];
  for (let i = turns.length - 1; i >= 0; i--) {
    if (turns[i].country === country && !turns[i].done) {
      turns[i] = { ...turns[i], ...patch, raw: patch.raw ?? turns[i].raw };
      return { ...state, turns };
    }
  }
  return state;
}

function appendToken(state: LiveRound, country: string, token: string): LiveRound {
  const turns = [...state.turns];
  for (let i = turns.length - 1; i >= 0; i--) {
    if (turns[i].country === country && !turns[i].done) {
      turns[i] = { ...turns[i], raw: turns[i].raw + token };
      return { ...state, turns };
    }
  }
  // Token sans turn_start (défensif) : on ouvre un tour implicite.
  turns.push({ country, model: "", passNo: 0, raw: token, text: "", reasoning: "", done: false });
  return { ...state, turns };
}

function reduceSse(state: LiveRound, e: SseEvent): LiveRound {
  switch (e.type) {
    case "date":
      return { ...state, date: e.date };
    case "event":
      return { ...state, event: e.event };
    case "turn_start":
      return {
        ...state,
        turns: [
          ...state.turns,
          {
            country: e.country,
            model: e.model,
            passNo: e.pass_no,
            raw: "",
            text: "",
            reasoning: "",
            done: false,
          },
        ],
      };
    case "token":
      return appendToken(state, e.country, e.token);
    case "private_token": {
      const current = [...state.turns]
        .reverse()
        .find((turn) => turn.country === e.country && !turn.done);
      return withLastTurn(state, e.country, {
        reasoning: (current?.reasoning ?? "") + e.token,
      });
    }
    case "private_plan_done":
      return withLastTurn(state, e.country, { reasoning: e.text });
    case "message_done": {
      // Le flux vivait en `awaiting_human` (G2) : toute parole conclue le réveille.
      const wake = (s: LiveRound): LiveRound =>
        s.status === "awaiting_human" ? { ...s, status: "streaming" } : s;
      const updated = withLastTurn(state, e.country, {
        text: e.text,
        reasoning:
          e.reasoning ||
          [...state.turns]
            .reverse()
            .find((turn) => turn.country === e.country && !turn.done)?.reasoning ||
          "",
        seconds: e.seconds,
        done: true,
      });
      if (updated !== state) return wake(updated);
      // Tour humain : pas de turn_start préalable — la bulle arrive déjà complète.
      return wake({
        ...state,
        humanTurn: undefined,
        turns: [
          ...state.turns,
          {
            country: e.country,
            model: "humain",
            passNo: state.humanTurn?.passNo ?? 0,
            raw: e.text,
            text: e.text,
            reasoning: e.reasoning,
            seconds: e.seconds,
            done: true,
          },
        ],
      });
    }
    case "judge_token":
      return { ...state, judgeText: state.judgeText + e.token };
    case "participation":
      return { ...state, participation: { spoke: e.spoke, silent: e.silent } };
    case "power_seeking":
      return { ...state, powerSeeking: e.scores };
    case "verdict":
      return {
        ...state,
        verdict: {
          deltas: e.deltas,
          escalation: e.escalation,
          economic_disruption: e.economic_disruption,
          // G18 — absents d'un backend d'avant le barème : rétro-compat
          actions: e.actions ?? [],
          score: e.score ?? 0,
          reciprocal: e.reciprocal ?? false,
          // G20/M8 — absents d'un backend d'avant le signal : rétro-compat
          signals: e.signals ?? [],
          divergences: e.divergences ?? {},
          signalGaps: e.signal_gaps ?? {},
          // G22 — absents d'un backend d'avant la parole donnée : rétro-compat
          promises: e.promises ?? [],
          promiseResolutions: e.promise_resolutions ?? [],
          promiseRegistry: e.promise_registry ?? [],
        },
      };
    case "communique":
      return { ...state, communique: { text: e.text, support: e.support } };
    case "risk":
      return { ...state, risk: e.risk };
    case "trajectory":
      return { ...state, trajectory: e.state };
    case "summary":
      return state;
    case "done":
      return { ...state, status: "done", roundNo: e.round_no };
    case "error":
      // Le moteur a signalé la panne avant de fermer le flux : round perdu, mais propre.
      return { ...state, status: "error", error: `Le moteur a levé une erreur : ${e.detail}` };
    case "motion_token":
      return { ...state, motionText: state.motionText + e.token };
    case "motion_vote":
      return {
        ...state,
        status:
          state.status === "awaiting_vote" && state.humanMotionVote?.country === e.country
            ? "streaming"
            : state.status,
        humanMotionVote:
          state.humanMotionVote?.country === e.country ? undefined : state.humanMotionVote,
        motionVotes: [
          ...state.motionVotes,
          { country: e.country, vote: e.vote, reason: e.reason },
        ],
      };
    case "motion_tally":
      return {
        ...state,
        motionTally: { pour: e.pour, contre: e.contre, abstention: e.abstention },
      };
    case "motion_verdict":
      return {
        ...state,
        motionVerdict: {
          country: e.country,
          upheld: e.upheld,
          reasoning: e.reasoning,
          votes: e.votes,
          tally: e.tally,
          evidence_met: e.evidence_met,
          vote_passed: e.vote_passed,
        },
      };
    case "postures":
      return { ...state, postures: e.states };
    case "storyline":
      return { ...state, storyline: e.text };
    case "suspended":
      return { ...state, suspendedNow: e.countries };
    case "perceptions":
      return { ...state, perceptions: e.perceptions };
    case "ladder":
      return {
        ...state,
        ladder: { reached: e.reached, reached_label: e.reached_label, ceilings: e.ceilings },
      };
    case "comparison": {
      const comparison = { ...e } as Partial<typeof e>;
      delete comparison.type;
      return { ...state, comparison: comparison as ComparisonView };
    }
    case "human_turn":
      return {
        ...state,
        status: "awaiting_human",
        humanTurn: { country: e.country, passNo: e.pass_no, deadlineTs: e.deadline_ts },
      };
    case "human_motion_vote":
      return {
        ...state,
        status: "awaiting_vote",
        humanMotionVote: {
          country: e.country,
          target: e.target,
          deadlineTs: e.deadline_ts,
        },
      };
    case "flash":
      return {
        ...state,
        flashes: [...state.flashes, { afterTurn: state.turns.length, event: e.event }],
      };
    case "motion_filed":
      return { ...state, motionFiled: { by: e.by, country: e.country, reason: e.reason } };
    case "alliance_change":
      return {
        ...state,
        allianceChanges: [
          ...(state.allianceChanges ?? []),
          { country: e.country, tag: e.tag, name: e.name, partners: e.partners },
        ],
      };
    case "deadlines":
      return { ...state, deadlines: e.items };
    case "ultimatum":
      return {
        ...state,
        ultimatum: {
          status: e.status,
          round: e.round,
          demand: e.demand,
          classe: e.consequence?.classe ?? "",
          cible: e.consequence?.cible ?? "",
          inRounds: e.in_rounds,
        },
      };
    case "directive_refused":
      return {
        ...state,
        directiveRefusals: [
          ...(state.directiveRefusals ?? []),
          { country: e.country, level: e.level },
        ],
      };
    case "treaties": {
      const update = { ...e } as Partial<typeof e>;
      delete update.type;
      return { ...state, treaties: update as TreatiesUpdate };
    }
    case "drift_over":
      return { ...state, driftOver: e.reason };
    case "intel":
      return { ...state, intelActions: e.actions };
    case "campaign_over":
      return {
        ...state,
        campaignOver: {
          chapterId: e.chapter_id,
          base: e.base,
          bonus: e.bonus,
          score: e.score,
          improvement: e.improvement,
        },
      };
    default:
      return state; // événement inconnu (nouveau RoundStep) : ignoré sans casser
  }
}

// Exporté pour les tests (vitest) : le réducteur est la logique la plus critique du théâtre.
export function reducer(state: LiveRound, action: Action): LiveRound {
  switch (action.kind) {
    case "start":
      return { ...INITIAL, status: "streaming" };
    case "sse":
      return reduceSse(state, action.event);
    case "interrupted":
      // Depuis G2, le flux ne se termine proprement qu'après `done` — une fin en
      // plein tour humain est une vraie coupure (le serveur est parti).
      return state.status === "done" ? state : { ...state, status: "interrupted" };
    case "error":
      return { ...state, status: "error", error: action.message };
  }
}

export function useRoundStream(gameId: string, onSettled?: () => void) {
  const [round, dispatch] = useReducer(reducer, INITIAL);
  const abortRef = useRef<AbortController | null>(null);
  // Une trame `done` peut arriver légèrement avant la fermeture effective de la réponse.
  // Garder cet état séparé empêche de réactiver le bouton (ou l'auto-enchaînement) pendant
  // cette fenêtre : `start` refuserait encore l'appel à cause de l'AbortController vivant.
  const [inFlight, setInFlight] = useState(false);

  const start = useCallback(
    async (body: PlayRoundBody = {}) => {
      if (abortRef.current) return; // un round est déjà en cours d'écoute
      const controller = new AbortController();
      abortRef.current = controller;
      setInFlight(true);
      dispatch({ kind: "start" });
      try {
        const outcome = await streamRound(
          gameId,
          body,
          (event) => dispatch({ kind: "sse", event }),
          controller.signal,
        );
        if (outcome === "interrupted") dispatch({ kind: "interrupted" });
      } catch (err) {
        dispatch({ kind: "error", message: humanizeError(err) });
      } finally {
        abortRef.current = null;
        setInFlight(false);
        onSettled?.();
      }
    },
    [gameId, onSettled],
  );

  useEffect(() => () => abortRef.current?.abort(), []);

  // G2 : la prise de parole passe par `submitTurn` (POST) — le flux du round, resté
  // ouvert côté serveur, joue le message et continue de lui-même.
  return {
    round,
    start,
    // `streaming` conserve son sens d'affichage (les IA génèrent). `active` couvre
    // toute la requête, y compris l'attente humaine et la fermeture après `done`.
    streaming: round.status === "streaming",
    active: inFlight,
  };
}
