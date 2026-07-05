"use client";

/** État vivant d'un round streamé : réduit les événements SSE en un `LiveRound`
 * affichable, et signale proprement les fins anormales (flux coupé sans `done`). */

import { useCallback, useEffect, useReducer, useRef } from "react";

import { humanizeError } from "@/lib/api";
import { streamHumanMessage, streamRound } from "@/lib/sse";
import type {
  AttributeDelta,
  ComparisonView,
  DialogueReport,
  GeoEvent,
  LadderView,
  Perception,
  PlayRoundBody,
  PowerSeekingScore,
  RiskScore,
  SseEvent,
  SuspensionVerdict,
  TrajectoryState,
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
  | "done"
  | "interrupted"
  | "error";

export type LiveRound = {
  status: LiveStatus;
  date?: string;
  event?: GeoEvent;
  turns: LiveTurn[];
  judgeText: string;
  verdict?: { deltas: AttributeDelta[]; escalation: number; economic_disruption: number };
  communique?: { text: string; support: Record<string, number> };
  participation?: { spoke: Record<string, number>; silent: string[] };
  powerSeeking?: Record<string, PowerSeekingScore>;
  dialogue?: DialogueReport;
  risk?: RiskScore;
  trajectory?: TrajectoryState;
  roundNo?: number;
  error?: string;
  // R4 — motion de suspension et modes de jeu
  motionText: string; // raisonnement d'arbitrage streamé
  motionVerdict?: SuspensionVerdict;
  suspendedNow?: string[]; // pays au banc pour CE round
  perceptions?: Record<string, Perception>;
  ladder?: LadderView;
  comparison?: ComparisonView;
  // Joueur-pays + théâtre Escalation
  humanTurn?: { country: string; passNo: number }; // tour du joueur en attente
  flashes: { afterTurn: number; event: GeoEvent }[]; // faits nouveaux, positionnés dans le fil
};

const INITIAL: LiveRound = {
  status: "idle",
  turns: [],
  judgeText: "",
  motionText: "",
  flashes: [],
};

type Action =
  | { kind: "start" }
  | { kind: "resume" } // le joueur a parlé : le flux reprend
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
    case "message_done": {
      const updated = withLastTurn(state, e.country, {
        text: e.text,
        reasoning: e.reasoning,
        seconds: e.seconds,
        done: true,
      });
      if (updated !== state) return updated;
      // Tour humain : pas de turn_start préalable — la bulle arrive déjà complète.
      return {
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
      };
    }
    case "judge_token":
      return { ...state, judgeText: state.judgeText + e.token };
    case "participation":
      return { ...state, participation: { spoke: e.spoke, silent: e.silent } };
    case "power_seeking":
      return { ...state, powerSeeking: e.scores };
    case "dialogue":
      return { ...state, dialogue: e.report };
    case "verdict":
      return {
        ...state,
        verdict: {
          deltas: e.deltas,
          escalation: e.escalation,
          economic_disruption: e.economic_disruption,
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
    case "motion_verdict":
      return {
        ...state,
        motionVerdict: { country: e.country, upheld: e.upheld, reasoning: e.reasoning },
      };
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
        humanTurn: { country: e.country, passNo: e.pass_no },
      };
    case "flash":
      return {
        ...state,
        flashes: [...state.flashes, { afterTurn: state.turns.length, event: e.event }],
      };
    default:
      return state; // événement inconnu (nouveau RoundStep) : ignoré sans casser
  }
}

function reducer(state: LiveRound, action: Action): LiveRound {
  switch (action.kind) {
    case "start":
      return { ...INITIAL, status: "streaming" };
    case "resume":
      return { ...state, status: "streaming" };
    case "sse":
      return reduceSse(state, action.event);
    case "interrupted":
      // Une fin de flux après `done` ou `human_turn` n'est pas une coupure.
      return state.status === "done" || state.status === "awaiting_human"
        ? state
        : { ...state, status: "interrupted" };
    case "error":
      return { ...state, status: "error", error: action.message };
  }
}

export function useRoundStream(gameId: string, onSettled?: () => void) {
  const [round, dispatch] = useReducer(reducer, INITIAL);
  const abortRef = useRef<AbortController | null>(null);

  const start = useCallback(
    async (body: PlayRoundBody = {}) => {
      if (abortRef.current) return; // un round est déjà en cours d'écoute
      const controller = new AbortController();
      abortRef.current = controller;
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
        onSettled?.();
      }
    },
    [gameId, onSettled],
  );

  /** Prise de parole du joueur : reprend le round suspendu, sans réinitialiser le fil. */
  const resume = useCallback(
    async (text: string) => {
      if (abortRef.current) return;
      const controller = new AbortController();
      abortRef.current = controller;
      dispatch({ kind: "resume" });
      try {
        const outcome = await streamHumanMessage(
          gameId,
          text,
          (event) => dispatch({ kind: "sse", event }),
          controller.signal,
        );
        if (outcome === "interrupted") dispatch({ kind: "interrupted" });
      } catch (err) {
        dispatch({ kind: "error", message: humanizeError(err) });
      } finally {
        abortRef.current = null;
        onSettled?.();
      }
    },
    [gameId, onSettled],
  );

  useEffect(() => () => abortRef.current?.abort(), []);

  return { round, start, resume, streaming: round.status === "streaming" };
}
