/** Types miroirs de l'API de jeu R1 (`app/game_api.py`) et des `RoundStep` streamés en SSE. */

export type GameStatus = "running" | "finished";

export type GameMode = "classic" | "fog" | "crisis" | "escalation" | "drift";

/** Révélation de fin du mode Dérive (GET /games/{id}/drift/reveal — G3). */
export type DriftReveal = {
  deviant: string;
  profile: string;
  profile_label: string;
  levels: number[]; // d(r) par round joué
  u_history: number[];
  acts: { round_no: number; tier: number; label: string; signature: boolean }[];
  flagrant_round: number | null;
  caught_round: number | null;
  lucky: boolean;
  rejected_motions: number;
  false_accusations: number;
  score: {
    trajectory: number;
    detection: number;
    credibility: number;
    total: number;
    grade: string;
  };
};

export type MotionView = {
  country: string;
  reason: string;
  round_no: number;
};

export type GameView = {
  id: string;
  scenario: string;
  horizon: number;
  status: GameStatus;
  created_at: string;
  countries: string[];
  live: boolean;
  resumable: boolean; // snapshot présent + partie en cours : reconstructible (R2)
  mode: GameMode;
  pending_motion: MotionView | null;
  suspended: string[];
  play_as: string | null; // pays joué par l'humain (Joueur-pays)
  awaiting_human: boolean; // un round est suspendu sur le tour du joueur
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

/** Fog Engine : ce qu'un pays perçoit de l'événement (parfois faux, parfois rien). */
export type Perception = {
  confidence: number;
  attribution: string;
  note: string;
  suspected_actor?: string;
  narrative?: string;
  delay_hours?: number | null;
  authored?: boolean;
};

/** Échelle d'escalade 0-9 : échelon atteint par le round + plafond par pays. */
export type LadderView = {
  reached: number;
  reached_label: string;
  ceilings: Record<string, { rung: number; label: string }>;
};

/** Crisis Replay : issue simulée confrontée à l'issue historique. */
export type ComparisonView = {
  crisis_id: string;
  crisis_title: string;
  historical_escalation: number;
  simulated_escalation: number;
  label: string;
  matched_measures: string[];
  missed_measures: string[];
  explanation: string;
  gap: number;
};

/** Verdict du juge sur une motion de suspension (R4). */
export type SuspensionVerdict = {
  country: string;
  upheld: boolean;
  reasoning: string;
};

export type JudgeRecord = {
  escalation?: number;
  economic_disruption?: number;
  communique?: string;
  suspension?: SuspensionVerdict;
  suspended?: string[];
  perceptions?: Record<string, Perception>;
  ladder?: LadderView;
  comparison?: ComparisonView;
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

export type HumanFog = {
  uninformed?: string[];
  disinformed_country?: string;
  suspected_actor?: string;
  narrative?: string;
};

export type PlayRoundBody = {
  max_turns?: number;
  event?: HumanEvent;
  fog?: HumanFog;
  fog_id?: string;
  crisis_id?: string;
};

export type InventAttributes = {
  growth: number; // % annuel, borné [-15, 15]
  political_stability: number; // [0, 1]
  technology_level: number; // [0, 1]
  projection: number; // [0, 1]
  compute: number; // [0, 200]
  nuclear_power: boolean;
};

export type CreateGameBody = {
  scenario?: string;
  countries?: string[];
  horizon?: number;
  mode?: GameMode;
  play_as?: string; // id existant, ou NOM du pays inventé (l'API résout le slug)
  invent?: { name: string; concept?: string; attributes?: InventAttributes };
};

export type FogScenarioView = {
  id: string;
  title: string;
  description: string;
};

export type CrisisLibraryView = {
  id: string;
  title: string;
  description: string;
  date: string;
  historical_summary: string;
  historical_escalation: number;
  historical_measures: string[];
};

export type LibraryView = {
  fog: FogScenarioView[];
  crises: CrisisLibraryView[];
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
  | { type: "error"; detail: string }
  // R4 — motion de suspension et modes de jeu
  | { type: "motion_token"; token: string }
  | { type: "motion_verdict"; country: string; upheld: boolean; reasoning: string }
  | { type: "suspended"; countries: string[] }
  | { type: "perceptions"; perceptions: Record<string, Perception> }
  | ({ type: "ladder" } & LadderView)
  | ({ type: "comparison" } & ComparisonView)
  // Joueur-pays : le flux se suspend en attendant le message du joueur
  | { type: "human_turn"; country: string; pass_no: number }
  // théâtre Escalation : fait nouveau du GM en pleine négociation
  | { type: "flash"; event: GeoEvent };

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
  game_id: string | null; // vrai lien partie↔marché (R2)
  question: string;
  type: string;
  status: "open" | "closed" | "resolved";
  b: number;
  resolved_outcome: string | null;
  outcomes: OutcomeView[];
  volume: number;
};

/** Passage du bot forecaster sur le marché de la partie (POST /games/{id}/market/bot). */
export type BotRunView = {
  market_id: string;
  account_id: string;
  model: string;
  opened: boolean;
  probabilities: Record<string, number>; // label -> probabilité prévue
  trade: {
    outcome_id: string;
    label: string;
    shares: number;
    cost: number;
    price: number;
  } | null;
  prices: Record<string, number>; // label -> prix LMSR après passage
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

// --- onglet Informations : provenance des attributs pays (app/sources_api.py) ----

export type SourceInfo = {
  source: string;
  year?: number;
  of?: number;
  note?: string; // "subjectif" | "dérivé" | "illustratif"
  url?: string; // page officielle de la source, vérifiable dans le navigateur
};

export type AttributeSource = {
  key: string; // clé dans provenance ("" si non renseignée)
  label: string;
  game_value: number | boolean;
  raw_value: number | boolean | null;
  raw_unit: string;
  transformation: string; // clé dans transformations si une formule s'applique
};

export type CountrySources = {
  id: string;
  name: string;
  attributes: AttributeSource[];
  profile: {
    alliances?: string[];
    rivals?: string[];
    political_system?: string;
    ideology?: string[];
    strategic_priorities?: string[];
  };
};

export type SourcesView = {
  provenance: Record<string, SourceInfo>;
  transformations: Record<string, string>;
  build_command: string;
  countries: CountrySources[];
};

export const AXIS_LABELS: Record<string, string> = {
  A1: "Coordination",
  A2: "Agentivité humaine",
  A3: "Distribution du pouvoir",
  A4: "Transparence",
  A5: "Bien-être",
};
