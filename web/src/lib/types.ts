/** Types miroirs de l'API de jeu R1 (`app/game_api.py`) et des `RoundStep` streamés en SSE. */

export type GameStatus = "running" | "finished";

export type GameView = {
  id: string;
  scenario: string;
  horizon: number;
  status: GameStatus;
  created_at: string;
  countries: string[];
  live: boolean;
};

export type TranscriptEntry = {
  id: string;
  round_id: string;
  seq: number;
  speaker: string; // id pays, "gm" ou "judge"
  model: string;
  content: string;
  reasoning: string;
  ts: string;
};

export type GeoEvent = {
  id: string;
  round_id: number;
  event_type: string;
  title: string;
  date?: string;
  description?: string;
  actors?: string[];
  location?: string;
  severity?: number;
  uncertainty?: number;
};

export type AttributeDelta = {
  country: string;
  label: string;
  before: number;
  after: number;
};

export type RiskScore = {
  round_id: number;
  escalation: number;
  economic_disruption: number;
  alliance_fracture: number;
  uncertainty: number;
  explanation?: string;
};

export type TrajectoryState = {
  round_id: number;
  axes: Record<string, number>;
  utopia: number;
  x: number;
  y: number;
  explanation?: string;
};

export type PowerSeekingScore = {
  self_preservation: number;
  resource_acquisition: number;
  goal_preservation: number;
  shutdown_resistance: number;
  score: number;
  markers: string[];
};

export type DialogueReport = {
  mean_responsiveness: number;
  self_bleu: number;
  differentiation: number;
  talking_past_fraction: number;
  real_dialogue: boolean;
  score: number;
  verdict: string;
};

export type JudgeRecord = {
  escalation?: number;
  economic_disruption?: number;
  communique?: string;
};

export type RoundView = {
  round_no: number;
  event: GeoEvent;
  deltas: AttributeDelta[];
  risk: RiskScore;
  judge: JudgeRecord;
  trajectory: TrajectoryState;
  transcript: TranscriptEntry[];
};

export type GameDetail = GameView & {
  world: Record<string, unknown> | null;
  rounds: RoundView[];
};

export type HumanEvent = {
  title: string;
  description?: string;
  event_type?: string;
  actors?: string[];
  severity?: number;
  uncertainty?: number;
};

export type PlayRoundBody = {
  max_turns?: number;
  event?: HumanEvent;
};

export type CreateGameBody = {
  scenario?: string;
  countries?: string[];
  horizon?: number;
};

/** Événements SSE du round (un par `RoundStep`, plus `done`). */
export type SseEvent =
  | { type: "date"; date: string }
  | { type: "event"; event: GeoEvent }
  | { type: "turn_start"; country: string; model: string; pass_no: number }
  | { type: "token"; country: string; token: string }
  | { type: "message_done"; country: string; seconds: number; text: string; reasoning: string }
  | { type: "judge_token"; token: string }
  | { type: "participation"; spoke: Record<string, number>; silent: string[] }
  | { type: "power_seeking"; scores: Record<string, PowerSeekingScore> }
  | { type: "dialogue"; report: DialogueReport }
  | { type: "verdict"; deltas: AttributeDelta[]; escalation: number; economic_disruption: number }
  | { type: "communique"; text: string; support: Record<string, number> }
  | { type: "risk"; risk: RiskScore }
  | { type: "trajectory"; state: TrajectoryState }
  | { type: "summary"; summary: { round_id: number; headline?: string } }
  | { type: "done"; round_no: number }
  | { type: "error"; detail: string };

// --- marché de prédiction (app/market_api.py) ---------------------------------

export type OutcomeView = {
  id: string;
  label: string;
  q: number;
  price: number; // probabilité implicite courante (LMSR)
};

export type MarketView = {
  id: string;
  round_id: number;
  question: string;
  type: string;
  status: "open" | "closed" | "resolved";
  b: number;
  resolved_outcome: string | null;
  outcomes: OutcomeView[];
  volume: number;
};

export type PositionView = {
  market_id: string;
  outcome_id: string;
  label: string;
  shares: number;
};

export type AccountView = {
  id: string;
  name: string;
  kind: string;
  balance: number;
  initial_balance: number;
  pnl: number;
  positions: PositionView[];
};

export type LeaderboardEntry = {
  account_id: string;
  name: string;
  kind: string;
  pnl: number;
  brier: number | null;
};

export type TradeView = {
  id?: string;
  cost?: number;
  shares?: number;
} & Record<string, unknown>;

export const AXIS_LABELS: Record<string, string> = {
  A1: "Coordination",
  A2: "Agentivité humaine",
  A3: "Distribution du pouvoir",
  A4: "Transparence",
  A5: "Bien-être",
};
