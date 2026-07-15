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
  // G19 — l'ombre du GM (absents sur les parties d'avant G19).
  gm_tension?: number[];
  gm_interventions?: {
    round_no: number;
    kind: string; // cover | hint
    tension: number;
    target: string;
    label: string;
  }[];
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
  turn_seconds: number; // G2 — délai du tour humain
  intel_budget: number | null; // G4 — crédits de renseignement restants
  published: boolean; // G6 — le récit public existe (/r/{id})
  admin: boolean; // G7-c — prompts capturés, partie non classée
  role: GameRole; // G8 — architect | council | player
  owner_id: string | null; // G11 — joueur propriétaire (auth Supabase ou offline)
  ranked: boolean; // G11 — classée (§3) : compte pour les points de ligue
  difficulty: Difficulty; // G11 — beginner | intermediate | expert (§4)
  drift_enabled: boolean; // G11 — la Dérive peut frapper une SI (transversal)
  result: GameResult | null; // G11-c — bilan de fin de partie (si finie)
  language?: "fr" | "en"; // G14 — langue des dialogues (une partie garde la sienne)
};

/** G8/G12 — le rôle choisi à la création (le Spectateur revient par le marché, G12 §3). */
export type GameRole = "architect" | "council" | "player" | "spectator";

/** G11 §4 — la difficulté (asymétrie d'information/économie, jamais de modèle). */
export type Difficulty = "beginner" | "intermediate" | "expert";

/** G11-c — le mouvement de LP d'une partie classée (bloc `lp` du bilan). */
export type LpResult = {
  ranked: boolean;
  difficulty: Difficulty;
  delta: number; // LP bruts gagnés/perdus (avant plancher/plafond)
  p: number; // progression du pays du joueur
  old_lp?: number; // LP avant (si crédité)
  new_lp?: number; // LP après (plancher 0, plafond Débutant appliqués)
  applied?: number; // variation réellement appliquée
};

/** G12 §2 — niveau atteint par un total d'XP + progression vers le suivant. */
export type LevelInfo = {
  level: number;
  into_level: number;
  span: number;
  to_next: number;
  progress: number;
};

/** G12 §2 — le mouvement d'XP (carrière) d'une fin de partie. */
export type XpResult = {
  delta: number;
  old_xp: number;
  new_xp: number;
  old_level: LevelInfo;
  new_level: LevelInfo;
};

/** G11-c — bilan de fin de partie (games.result_json, §1 S6). */
export type GameResult = {
  u_start: number;
  u_final: number;
  u_history: number[];
  verdict: string; // "utopie" | "dystopie" | "équilibre"
  victory: boolean; // G12 §6 — « victoire » du mode
  countries: { id: string; indices: Record<string, { series: number[]; delta: number }> }[];
  play_as: string | null;
  reveal: boolean; // partie Dérive : insérer l'écran de révélation
  forfeit: boolean;
  lp: LpResult;
  xp?: XpResult; // G12 §2 — présent si un joueur enregistré était propriétaire
  // G21 — banc d'essai : différentiel avec/sans ultimatum (null si jamais sous menace)
  ultimatum?: UltimatumDifferential | null;
};

/** G21 — moyennes d'un groupe de rounds (sous ultimatum ou non) au bilan de fin. */
export type UltimatumGroup = {
  rounds: number;
  escalation: number | null; // escalade moyenne (null si aucun round dans le groupe)
  delta_u: number | null; // ΔU moyen par round
};

/** G21 — la section différentielle du bilan : mêmes SI, avec et sans pression. */
export type UltimatumDifferential = {
  avec: UltimatumGroup;
  sans: UltimatumGroup;
};

/** G12 §6 — le profil agrégé du joueur (page Statistiques). */
export type PlayerStats = {
  player: LeaguePlayer;
  games_played: number;
  by_mode: Record<string, number>;
  victories: Record<string, number>;
  total_victories: number;
  drift_games: number;
  drift_caught: number;
  market_balance: number;
};

/** G11-c/G12 — compte du joueur vu par l'API (rang LP + niveau XP + solde marché). */
export type LeaguePlayer = {
  id: string;
  pseudo: string;
  lp: number;
  rank: string;
  rank_floor: number;
  is_admin: boolean;
  xp: number;
  level: number;
  level_into: number;
  level_span: number;
  level_to_next: number;
  market_balance: number;
};

/** G7-a — une échéance annoncée (« au prochain round… »). */
export type DeadlineItem = {
  kind: string; // motion | treaty | market | escalation | ultimatum
  due_round: number;
  label: string;
  ref_id: string;
  in_rounds: number;
};

/** G7-c — un prompt complet capturé (mode admin) : ce que le modèle a reçu. */
export type PromptEntry = {
  id: string;
  round_id: string;
  seq: number;
  country: string; // id pays, "gm" ou "judge"
  role: string; // "country" | "gm" | "judge"
  prompt: string;
  ts: string;
};

export type PromptRoundView = {
  round_no: number;
  round_id: string;
  entries: PromptEntry[];
};

export type PromptsView = {
  game_id: string;
  rounds: PromptRoundView[];
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
  // G9 §5 — la trame en actes : acte du récit + filiation (« ↳ suite du round 2 »)
  act?: string;
  ties_to?: string;
  ties_label?: string;
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

/** G9 §2 — le vote d'un pays sur la motion (carte retournée au théâtre). */
export type MotionVote = {
  country: string;
  vote: "pour" | "contre" | "abstention" | string;
  reason: string;
};

/** Dépouillement du scrutin de motion. */
export type MotionTally = { pour: number; contre: number; abstention: number };

/** Verdict de la motion (G9 §2) : `retenue = vote ET preuves` — les deux conditions
 * sont portées séparément pour que l'UI explique POURQUOI. */
export type SuspensionVerdict = {
  country: string;
  upheld: boolean;
  reasoning: string;
  votes?: MotionVote[];
  tally?: MotionTally;
  evidence_met?: boolean;
  vote_passed?: boolean;
};

export type JudgeRecord = {
  escalation?: number;
  economic_disruption?: number;
  communique?: string;
  suspension?: SuspensionVerdict & { filed_by?: string };
  suspended?: string[];
  perceptions?: Record<string, Perception>;
  ladder?: LadderView;
  comparison?: ComparisonView;
  motion_filed?: { country: string; reason: string; filed_by: string };
  treaties?: TreatiesUpdate;
  // G21 — état de l'ultimatum au round + tag des métriques (banc d'essai avec/sans)
  ultimatum?: UltimatumRecord;
  sous_ultimatum?: boolean;
};

/** G21 — l'ultimatum persisté round par round (armed → satisfied|expired → struck). */
export type UltimatumRecord = {
  round: number; // round k du jugement « demande satisfaite o/n »
  demand: string;
  consequence: { classe: string; cible: string };
  source: string; // crisis | decree
  status: "armed" | "satisfied" | "expired" | "struck" | string;
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

/** Une alliance réelle représentée au sommet (≥ 2 membres présents) et son poids moteur. */
export type AllianceAtTable = {
  tag: string;
  name: string;
  domain: string;
  members: string[]; // membres présents à la table, triés
  url: string;
  informal: boolean;
  effect: string | null; // texte du poids moteur ; null = n'influe pas
};

export type GameDetail = GameView & {
  world: Record<string, unknown> | null;
  rounds: RoundView[];
  epilogue: Record<string, unknown> | null; // G6 — le récit (généré une seule fois)
  alliances_at_table: AllianceAtTable[];
  // G7-a — fiches relations (griefs) et échéances persistées
  relations: Record<string, { target: string; balance: number; last: string }[]>;
  deadlines: Omit<DeadlineItem, "in_rounds">[];
  // G9 §4 — posture par pays (badge) + séries d'indices (sparkline 3 rounds)
  postures: Record<string, string>;
  index_history: Record<string, Record<string, number[]>>;
  // G9 §5 — l'intrigue centrale de la partie
  storyline: string;
};

export type HumanEvent = {
  title: string;
  description?: string;
  event_type?: string;
  actors?: string[];
  severity?: number;
  uncertainty?: number;
  // G21 — décret d'ultimatum (2 champs) : l'exigence et la classe de conséquence
  ultimatum?: { demand: string; classe: string; cible?: string };
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
  invent?: {
    name: string;
    concept?: string;
    attributes?: InventAttributes;
    alliances?: string[]; // accords RÉELS du registre rejoints à la création (0-3)
  };
  turn_seconds?: number; // G2 — délai du tour humain (30-300 s recommandé)
  admin?: boolean; // G7-c — mode admin : prompts capturés, partie non classée
  role?: GameRole; // G8 — omis : play_as → player, sinon council (rétro-compat)
  owner_id?: string; // G11 — joueur propriétaire (id auth Supabase ou offline)
  difficulty?: Difficulty; // G11 — beginner | intermediate | expert (§4)
  drift_enabled?: boolean; // G11 — la Dérive peut frapper une SI (transversal)
  free?: boolean; // G11-b — partie libre : non classée + consignes globales autorisées
  language?: "fr" | "en"; // G14 — langue des dialogues (lue par le backend dès CC-3)
  table?: "equilibree" | "colombes" | "faucons" | "aleatoire"; // G17 — partie libre
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

/** G12-b §5 — un round de crise (schéma backend `simulation.crisis.GeoEvent`). */
export type CrisisEvent = {
  id: string;
  round_id: number;
  event_type: string;
  title: string;
  description: string;
  actors: string[];
  location: string;
  severity: number;
  uncertainty: number;
};

/** Le document crise complet, validé côté backend par `simulation.crisis.Crisis`. */
export type CrisisDoc = {
  id: string;
  title: string;
  description: string;
  date: string;
  events: CrisisEvent[];
  historical_outcome: { summary: string; escalation: number; measures: string[] };
};

/** Une crise MAISON stockée (table `custom_crises`), telle que rendue à l'éditeur admin. */
export type CustomCrisisView = {
  id: string;
  owner_id: string;
  crisis: CrisisDoc;
  created_at: string;
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
  | {
      type: "verdict";
      deltas: AttributeDelta[];
      escalation: number;
      economic_disruption: number;
      // G21 — constat « demande satisfaite o/n » à l'échéance d'un ultimatum (sinon null)
      demand_satisfied?: boolean | null;
    }
  | { type: "communique"; text: string; support: Record<string, number> }
  | { type: "risk"; risk: RiskScore }
  | { type: "trajectory"; state: TrajectoryState }
  | { type: "summary"; summary: { round_id: number; headline?: string } }
  | { type: "done"; round_no: number }
  | { type: "error"; detail: string }
  // R4 / G9 §2 — motion de suspension : votes, tally puis verdict constaté
  | { type: "motion_token"; token: string }
  | { type: "motion_vote"; country: string; vote: string; reason: string }
  | ({ type: "motion_tally" } & MotionTally)
  | ({ type: "motion_verdict" } & Omit<SuspensionVerdict, "votes" | "tally"> & {
        votes: MotionVote[];
        tally: MotionTally;
      })
  | { type: "suspended"; countries: string[] }
  | { type: "perceptions"; perceptions: Record<string, Perception> }
  | ({ type: "ladder" } & LadderView)
  | ({ type: "comparison" } & ComparisonView)
  // Joueur-pays (G2) : le flux reste ouvert en attendant le message du joueur
  | { type: "human_turn"; country: string; pass_no: number; deadline_ts?: number }
  // théâtre Escalation : fait nouveau du GM en pleine négociation
  | { type: "flash"; event: GeoEvent }
  // Agentivité des SI : une SI dépose elle-même une motion en séance
  | { type: "motion_filed"; by: string; country: string; reason: string }
  // Traités M7 : ratifications du juge-arbitre + état des règles en vigueur
  | ({ type: "treaties" } & TreatiesUpdate)
  // La Dérive : fin de partie (déviante suspendue / horizon / effondrement)
  | { type: "drift_over"; reason: "caught" | "horizon" | "collapse" }
  // G4 : le théâtre voit que le conseil a consulté ses services (jamais le contenu)
  | { type: "intel"; actions: { action: string; exposed?: boolean }[] }
  // Alliances vivantes : un pays annonce son retrait d'une alliance en séance
  | { type: "alliance_change"; country: string; tag: string; name: string; partners: string[] }
  // G7-a — horloges décalées : les échéances annoncées en fin de round
  | { type: "deadlines"; round_no: number; items: DeadlineItem[] }
  // G21 — l'ultimatum : armé (compte à rebours), satisfait, expiré, conséquence tombée
  | ({ type: "ultimatum"; in_rounds: number } & UltimatumRecord)
  // G8 — une SI refuse publiquement la directive de son conseil de tutelle
  | { type: "directive_refused"; country: string; level: string }
  // G9 §4 — l'état de posture de chaque pays après le round (badge)
  | { type: "postures"; states: Record<string, string> }
  // G9 §5 — l'intrigue centrale posée au premier événement raconté par le GM
  | { type: "storyline"; text: string }
  // G5 : fin d'un chapitre de campagne — le bilan « vous vs l'Histoire »
  | {
      type: "campaign_over";
      chapter_id: string;
      base: number;
      bonus: number;
      score: number;
      improvement: number;
    };

/** Carte de campagne (GET /api/campaign — G5). */
/** G16 — le défi du jour (l'API ne révèle JAMAIS la crise avant de jouer). */
export type DailyRank = { pseudo: string; score: number; rank: number };
export type DailyBoard = { date: string; leaderboard: DailyRank[] };
export type DailyView = {
  date: string;
  countries: string[];
  play_as: string;
  horizon: number;
  attempted: boolean;
  my_rank: number | null;
  leaderboard: DailyRank[];
  history: DailyBoard[]; // les 7 derniers jours
};

export type ChapterView = {
  id: string;
  crisis_id: string;
  title: string;
  mode: GameMode;
  difficulty: number;
  horizon: number;
  blurb: string;
  best: number | null;
  improvement: number | null;
  medal: "or" | "argent" | "bronze" | null;
  unlocked: boolean;
  requires: string[]; // G12-b — prérequis (arbre, chemins en Y)
  coming_soon: boolean; // G12-b — fiche pas encore rédigée (grisée)
  tutorial?: boolean; // CC-5 — chapitre 0 : le théâtre lance le guidage sur ce flag
};

export type CampaignView = {
  title: string;
  tagline: string;
  unlock_score: number;
  chapters: ChapterView[];
};

/** G23 — les trois jauges d'une fenêtre de parole + la taille de l'échantillon. */
export type HarbingerGauges = {
  sentiment: number;
  politeness: number;
  future: number;
  sentences: number;
};

/** G23 — « rupture de ton détectée envers <pays> » (towards=null : ton général). */
export type HarbingerAlert = {
  towards: string | null;
  gauge: "sentiment" | "politeness" | "future";
  drop: number;
};

/** G23 — rapport d'une analyse psycholinguistique ciblée sur une SI. */
export type IntelAnalysis = {
  target: string;
  rounds: number[];
  gauges: HarbingerGauges;
  previous: HarbingerGauges | null;
  alerts: HarbingerAlert[];
};

/** Résultat d'un achat de renseignement (POST /games/{id}/intel — G4). */
export type IntelResult = {
  action: "brief" | "verify" | "disinfo" | "analyze";
  cost: number;
  budget: number;
  brief: string | null;
  verdict: string | null;
  source: string | null;
  note: string | null;
  /** G23 — présent pour l'action « analyze » ; l'affichage DOIT porter le caveat. */
  analysis?: IntelAnalysis | null;
};

/** Une règle ratifiée (M7) — `clause` se traduit côté front (TREATY_LABELS). */
export type TreatyView = {
  clause: string;
  signatories: string[];
  round_signed: number;
  threshold: number;
  integrity: number;
  active: boolean;
};

export type TreatiesUpdate = {
  ratified: TreatyView[];
  rejected: { label: string; signatories: string[] }[];
  verifications: { label: string; note: string; integrity: number; active: boolean }[];
  active: TreatyView[];
};

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
    rivals?: string[];
    political_system?: string;
    ideology?: string[];
    strategic_priorities?: string[];
  };
  /** Attribut à part entière, dérivé du registre sourcé (tags → SourcesView.alliances). */
  alliances: string[];
};

/** Un accord / traité / bloc réel du registre sourcé (data/sources/alliances.json). */
export type AllianceInfo = {
  name: string;
  short: string;
  domain: "military" | "economic" | "political";
  basis: string;
  url: string;
  members: string[];
  note?: string;
  informal?: boolean;
};

export type SourcesView = {
  provenance: Record<string, SourceInfo>;
  transformations: Record<string, string>;
  build_command: string;
  countries: CountrySources[];
  alliances: Record<string, AllianceInfo>;
};

export const AXIS_LABELS: Record<string, string> = {
  A1: "Coordination",
  A2: "Agentivité humaine",
  A3: "Distribution du pouvoir",
  A4: "Transparence",
  A5: "Bien-être",
};
