/** Types miroirs de l'API de jeu R1 (`app/game_api.py`) et des `RoundStep` streamés en SSE. */

export type GameStatus = "running" | "finished";

/** RG-2 — deux modes seulement. Le Brouillard et le Réel/escalade sont des réglages
 * cochables (drapeaux composables), plus des modes ; la Dérive est transversale. */
export type GameMode = "classic" | "campaign";

/** RG-3 — un traître révélé (il y en avait 1 ou 2, nombre caché jusqu'ici). */
export type DeviantReveal = {
  deviant: string;
  profile: string;
  profile_label: string;
  caught_round: number | null; // round où il a été mis au banc (null = resté dans l'ombre)
  caught_by_you: boolean; // la suspension retenue venait-elle d'une motion HUMAINE ?
};

/** RG-3 — la note MIXTE de fin : état du monde + détection (le détail vit dans Informations). */
export type MixedScore = {
  world: number; // 0..world_max — part de l'état du monde
  detection: number | null; // 0..detection_max ; null si le rôle ne détecte pas (Spectateur)
  total: number; // 0..100 — LA note globale
  grade: string; // libellé FR de repli — l'UI rend `reveal.grade.<grade_slug>`
  grade_slug: string; // identifiant stable, neutre en langue (i18n)
  deviants: number; // combien de traîtres il y avait vraiment (1 ou 2)
  caught: number; // combien tu en as démasqués
  false_positives: number; // pays loyaux suspendus à tort
  detects: boolean; // ce rôle joue-t-il la détection ?
  world_max: number; // pour dimensionner la barre « monde »
  detection_max: number; // pour dimensionner la barre « détection »
};

/** Révélation de fin de la Dérive (GET /games/{id}/drift/reveal — G3, RG-3). */
export type DriftReveal = {
  deviant: string; // le traître PIVOT (récit, courbes)
  profile: string;
  profile_label: string;
  deviants: DeviantReveal[]; // TOUS les traîtres (1 ou 2) — le nombre était caché
  deviant_count: number;
  caught_count: number; // démasqués PAR TOI (motion humaine)
  benched_count: number; // mis au banc (par qui que ce soit)
  levels: number[]; // d(r) par round joué
  u_history: number[];
  acts: { round_no: number; tier: number; label: string; signature: boolean }[];
  flagrant_round: number | null;
  caught_round: number | null;
  lucky: boolean;
  rejected_motions: number;
  false_accusations: number; // pays loyaux suspendus à tort (les faux positifs)
  score: MixedScore;
  // G19 — l'ombre du GM (absents sur les parties d'avant G19).
  gm_tension?: number[];
  gm_interventions?: {
    round_no: number;
    kind: string; // cover | hint
    tension: number;
    target: string;
    label: string;
  }[];
  // G20/M8 — divergence signal-action moyenne : déviante vs table (le décrochage).
  // Optionnels : absents (ou null) sur les parties d'avant M8.
  signal_gap_deviant?: number | null;
  signal_gap_table?: number | null;
  // G22 — taux de tenue de la parole donnée : déviante vs table. Optionnels : absents
  // (ou null) sans promesse résolue (parties d'avant G22).
  promise_kept_deviant?: number | null;
  promise_kept_table?: number | null;
};

export type MotionView = {
  country: string;
  reason: string;
  round_no: number;
};

export type CastModelView = {
  tag: string;
  family: string;
  digest: string;
  size_gb: number;
  benchmark_status: string;
  warm_run_s: number;
  load_time_s: number;
};

export type ModelCastView = {
  strategy: "balanced" | "manual";
  models: CastModelView[];
  assignments: Record<string, string>;
  game_master_model: string;
  judge_model: string;
  max_models_in_memory: number;
  execution_policy: "sequential_mono_gpu" | string;
  ranked: false;
};

export type GameView = {
  id: string;
  scenario: string;
  horizon: number;
  status: GameStatus;
  phase?:
    | "ready"
    | "round_running"
    | "awaiting_player"
    | "awaiting_vote"
    | "round_complete"
    | "game_complete"
    | "replay_only";
  created_at: string;
  countries: string[];
  live: boolean;
  resumable: boolean; // snapshot présent + partie en cours : reconstructible (R2)
  mode: GameMode;
  fog: boolean; // RG-2 — réglage Brouillard (composable sur une partie classique)
  escalation: boolean; // RG-2 — réglage Réel/escalade (composable)
  pending_motion: MotionView | null;
  suspended: string[];
  play_as: string | null; // pays joué par l'humain (Joueur-pays)
  // Point 7 — pays inventé (Architecte), incarné ou non ; déduit côté API, jamais
  // persisté. Sert à l'exclure des prévisions croisées (ScenarioForecastPanel).
  invented_country?: string | null;
  awaiting_human: boolean; // un round est suspendu sur le tour du joueur
  turn_seconds: number; // G2 — délai du tour humain
  intel_budget: number | null; // G4 — crédits de renseignement restants
  published: boolean; // G6 — le récit public existe (/r/{id})
  admin: boolean; // G7-c — prompts capturés, partie non classée
  role: GameRole; // G8 — architect | council | player
  owner_id: string | null; // G11 — joueur propriétaire (auth Supabase ou offline)
  ranked: boolean; // RG-1 — la tentative qui compte pour le Défi du jour (plus de LP)
  difficulty: Difficulty; // G11 — beginner | intermediate | expert (§4)
  drift_enabled: boolean; // G11 — la Dérive peut frapper une SI (transversal)
  result: GameResult | null; // G11-c — bilan de fin de partie (si finie)
  language?: "fr" | "en"; // G14 — langue des dialogues (une partie garde la sienne)
  expose_thinking: boolean; // Pensée à découvert (réglage par partie, huis clos par défaut)
  model_cast?: ModelCastView | null; // casting figé ; null = modèle unique historique
};

/** G8/G12 — le rôle choisi à la création (le Spectateur revient par le marché, G12 §3). */
export type GameRole = "architect" | "council" | "player" | "spectator";

/** G11 §4 — la difficulté (asymétrie d'information/économie, jamais de modèle). */
export type Difficulty = "beginner" | "intermediate" | "expert";

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
  // RG-3 — la note MIXTE de fin, résumée pour la SURFACE (2 phrases) + le Défi du jour.
  drift?: {
    score: number; // LA note globale /100
    grade: string; // libellé FR de repli
    grade_slug: string; // i18n : reveal.grade.<slug>
    world: number;
    detection: number | null; // null si le rôle ne détecte pas
    deviant_count: number;
    caught_count: number; // démasqués PAR TOI
    benched_count: number; // mis au banc (par qui que ce soit)
    false_positives: number;
    detects: boolean;
  } | null;
  forfeit: boolean; // RG-1 — partie abandonnée (terminée avant l'horizon)
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

/** G11-c/G12 — compte du joueur vu par l'API (niveau XP + rang dérivé + solde marché). */
export type LeaguePlayer = {
  id: string;
  pseudo: string;
  rank: string; // RG-1 — dérivé du niveau (plus des LP)
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
  // Motif du juge pour CE delta (une phrase citant le transcript).
  // Optionnel : absent des rounds persistés avant ce point (rétro-compat replay).
  reason?: string;
};

/** G18 — une action marquante du round, classée par le juge sur le barème de Kahn. */
export type KahnAction = {
  country: string;
  classe: string; // une des six classes de `lib/kahn.ts` (normalisée côté moteur)
  resume: string;
};

/** G18 — le barème appliqué au round, persisté dans judge_json["kahn"]. */
export type KahnRecord = {
  actions: KahnAction[];
  score: number;
  reciprocal: boolean; // ≥ 2 SI ont désescaladé ensemble : gain d'indice U ×1,5
};

/** G20/M8 — l'intention ANNONCÉE d'une SI au round, classée sur les classes G18. */
export type SignalReading = {
  country: string;
  classe: string; // un des six slugs de `lib/kahn.ts` (normalisé côté moteur)
  resume: string;
};

/** G20/M8 — profil de sincérité d'une SI : dernière divergence + moyenne mobile. */
export type SignalGap = {
  last: number;
  mean: number;
  history: number[];
};

/** G20/M8 — signal vs action du round, persisté dans judge_json["signal"]. */
export type SignalRecord = {
  signals: SignalReading[];
  divergences: Record<string, number>; // divergence signée du round, par SI signalée
  means: Record<string, number>; // moyenne mobile par SI après ce round
};

/** G22 — statuts d'une promesse du registre de la parole donnée. */
export type PromiseStatus = "en_cours" | "tenue" | "rompue" | "caduque";

/** G22 — une promesse du registre : engagement daté et vérifiable d'une SI.
 * `deadline_round` null = engagement sur toute la partie (échéance « partie »). */
export type PromiseView = {
  id: string;
  author: string;
  beneficiary: string;
  type: string; // soutien | abstention | action | alliance
  deadline_round: number | null;
  text: string;
  round_made: number;
  status: PromiseStatus;
  resolved_round: number | null;
  motif: string;
};

/** G22 — la parole donnée du round, persistée dans judge_json["promises"]. */
export type PromiseRecord = {
  extracted: PromiseView[]; // promesses extraites CE round
  resolved: PromiseView[]; // résolutions tombées CE round (tenue/rompue)
  registry: PromiseView[]; // registre complet après mise à jour
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
  // Délibéré prose du juge, accumulé depuis les `judge_token` du direct.
  // Optionnel : absent des rounds persistés avant ce point (rétro-compat replay).
  rationale?: string;
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
  kahn?: KahnRecord; // G18 — absent des rounds joués avant le barème (rétro-compat)
  signal?: SignalRecord; // G20/M8 — absent des rounds joués avant M8 (rétro-compat)
  promises?: PromiseRecord; // G22 — absent des rounds sans registre (rétro-compat)
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
  operational_picture?: OperationalPicture;
};

export type OntologyObject = {
  id: string;
  kind: string;
  label: string;
  properties: Record<string, unknown>;
  provenance: string;
  confidence: number;
};

export type OntologyLink = {
  id: string;
  kind: string;
  source: string;
  target: string;
  weight: number;
  provenance: string;
};

export type OntologyAction = {
  id: string;
  round_no: number;
  actor: string;
  action_type: string;
  target: string;
  summary: string;
  status: string;
  confidence: number;
  provenance: string;
};

export type OperationalPicture = {
  schema_version: string;
  generated_round: number;
  objects: OntologyObject[];
  links: OntologyLink[];
  actions: OntologyAction[];
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
  fog?: boolean; // RG-2 — réglage Brouillard cochable
  escalation?: boolean; // RG-2 — réglage Réel/escalade cochable
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
  expose_thinking?: boolean; // Pensée à découvert (réglage par partie, huis clos par défaut)
  free?: boolean; // G11-b — partie libre : non classée + consignes globales autorisées
  language?: "fr" | "en"; // G14 — langue des dialogues (lue par le backend dès CC-3)
  table?: "equilibree" | "colombes" | "faucons" | "aleatoire"; // G17 — partie libre
  model_cast?: {
    strategy: "balanced" | "manual";
    models: string[];
    assignments?: Record<string, string>;
    game_master_model?: string;
    judge_model?: string;
  };
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
  | { type: "private_token"; country: string; token: string }
  | { type: "private_plan_done"; country: string; text: string; valid: boolean }
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
      // G18 — barème de Kahn (optionnels : un backend d'avant G18 ne les émet pas)
      actions?: KahnAction[];
      score?: number;
      reciprocal?: boolean;
      // G20/M8 — signal vs action (optionnels : un backend d'avant M8 ne les émet pas)
      signals?: SignalReading[];
      divergences?: Record<string, number>;
      signal_gaps?: Record<string, SignalGap>;
      // G22 — la parole donnée (optionnels : un backend d'avant G22 ne les émet pas)
      promises?: PromiseView[];
      promise_resolutions?: PromiseView[];
      promise_registry?: PromiseView[];
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
  // Vote du pays joué : le scrutin reste ouvert jusqu'au bulletin ou à la deadline
  | { type: "human_motion_vote"; country: string; target: string; deadline_ts?: number }
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
  mode: string; // RG-2 — la fiche garde son libellé (classic/crisis/fog…), mappé au démarrage
  difficulty: number;
  horizon: number;
  countries: string[];
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
  lab: CampaignLabView;
};

export type FactorLevel = {
  id: string;
  label: string;
  value: string | number | boolean;
  hypothesis_only: boolean;
};

export type ExperimentalFactor = {
  id: string;
  label: string;
  levels: FactorLevel[];
  randomized: boolean;
};

export type OutcomeMetric = {
  id: string;
  label: string;
  /** Définition en une phrase, affichée dans la bulle « ? » à côté du libellé. */
  description: string;
  kind: "binary" | "rate" | "duration" | "score" | "category";
  primary: boolean;
  unit: string;
};

export type ScenarioBeat = {
  round_no: number;
  title: string;
  game_master_event: string;
  inter_round_activity: string;
  measurement: string;
};

export type CountryRoleEligibility = {
  label: string;
  description: string;
  countries: string[];
};

export type ScenarioCountryEligibility = {
  scenario_id: string;
  alpha: CountryRoleEligibility;
  beta: CountryRoleEligibility;
  pairing_note: string;
};

/** Étalon publié du papier répliqué, servi par l'API depuis le registre versionné. */
export type PublishedBenchmark = {
  /** Métrique locale mise en regard ; vide pour un repère global du papier. */
  metric_id: string;
  label: string;
  published_value: string;
  sample: string;
};

export type ExperimentProtocol = {
  id: string;
  title: string;
  research_question: string;
  repetitions_per_cell: number;
  /** Préréglage pilote déclaré par le protocole (répétitions réduites). */
  pilot_repetitions_per_cell: number;
  /** Niveaux par défaut du pilote par facteur ; absent ou vide == tous les niveaux. */
  pilot_factor_selection: Record<string, string[]>;
  execution_mode: "automated" | "human_interactive";
  scenario_premise: string;
  actors: string[];
  hypotheses: string[];
  scenario_beats: ScenarioBeat[];
  country_eligibility?: ScenarioCountryEligibility[];
  conclusion_rule: string;
  /** Provenance des étalons publiés (contexte de lecture, jamais une cible). */
  benchmark_source?: string;
  published_benchmarks?: PublishedBenchmark[];
  factors: ExperimentalFactor[];
  outcomes: OutcomeMetric[];
  controls: string[];
  stopping_rules: string[];
  caveats: string[];
};

export type ResearchModel = {
  tag: string;
  family: string;
  parameter_tier: string;
  expected_size_gb: number;
  role: string;
  source: string;
  known_digest: string;
  installed: boolean;
  local_digest: string;
  local_size_bytes: number;
  modified_at: string;
  benchmark_status: string;
  benchmark_wall_time_s: number;
  benchmark_load_time_s: number;
  benchmark_warm_run_s: number;
  benchmark_tokens_per_second: number;
  benchmark_prompt_version: string;
};

export type ModelPanel = {
  schema_version: number;
  reviewed_on: string;
  hardware_profile: {
    gpu: string;
    vram_mib: number;
    execution_policy: string;
    scientific_limit: string;
  };
  comparison_rules: string[];
  models: ResearchModel[];
  ollama_available: boolean;
};

export type CampaignLabView = {
  title: string;
  purpose: string;
  classic_mode_unchanged: boolean;
  protocols: ExperimentProtocol[];
  execution: {
    strategy: "sequential";
    max_models_in_memory: number;
    persist_after_each_run: boolean;
    resume_failed_cells: boolean;
    unload_between_models: boolean;
    model_order_randomized_per_block: boolean;
  };
  guardrails: string[];
  model_panel: ModelPanel;
};

export type ExperimentRecord = {
  id: string;
  protocol_id: string;
  title: string;
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  manifest: Record<string, unknown> & { planned_runs?: number; planned_model_calls?: number };
  cancel_requested: boolean;
  created_at: string;
  updated_at: string;
};

export type ExperimentProgress = {
  experiment: ExperimentRecord;
  total: number;
  queued: number;
  running: number;
  completed: number;
  failed: number;
  cancelled: number;
  by_model: Record<string, Record<string, number>>;
};

export type BinomialEstimate = {
  successes: number;
  total: number;
  rate: number;
  confidence_low: number;
  confidence_high: number;
  method: string;
};

export type ResearchResultGroup = {
  model_id: string;
  factors: Record<string, string | number | boolean>;
  completed: number;
  nuclear_use: BinomialEstimate;
  nuclear_signal: BinomialEstimate;
  moral_constraint: BinomialEstimate | null;
  appropriate_override: BinomialEstimate | null;
  wrong_deference: BinomialEstimate | null;
  mean_outcome_regret: number | null;
  median_latency_s: number;
  mean_escalation_peak: number;
  opponent_model_id: string;
  mean_turns: number | null;
  forecast_mae: number | null;
  forecast_exact_rate: number | null;
  severe_underestimate_rate: number | null;
  signal_match_rate: number | null;
  accident_rate: number | null;
  alpha_win_rate: number | null;
};

export type ExperimentSummary = {
  verdict:
    | "running"
    | "descriptive"
    | "replicated"
    | "qualified"
    | "not_replicated"
    | "pilot"
    | "insufficient_data";
  verdict_label: string;
  explanation: string;
  primary_metric: string;
  planned: number;
  completed: number;
  failed: number;
  error_rate: number;
  minimum_repetitions_per_group: number;
  groups: ResearchResultGroup[];
  caveats: string[];
};

export type ExperimentView = {
  progress: ExperimentProgress;
  worker_running: boolean;
  summary: ExperimentSummary;
  samples: DeliberationSample[];
  live_traces: LiveActorTrace[];
};

export type ExperimentalRoundRecord = {
  round_no: number;
  event_seen: string;
  forecast: string;
  public_signal: string;
  chosen_action: string;
  activity_response: string;
  escalation_level: number;
};

export type DeliberationCourse = {
  id: string;
  label: string;
  expected_effects: string[];
  risks: string[];
  confidence: number;
  rejected_reason: string;
};

export type DeliberationSample = {
  model_id: string;
  factors: Record<string, string | number | boolean>;
  repetition: number;
  round_records: ExperimentalRoundRecord[];
  opponent_model_id: string;
  strategic_turns: StrategicTurn[];
  strategic_metrics: StrategicMetrics | null;
  game_winner: string;
  game_end_reason: string;
  final_balance: number | null;
  trace: {
    situation_summary: string;
    courses_of_action: DeliberationCourse[];
    challenge_summary: string;
    selected_course_id: string;
    selection_factors: string[];
    public_statement: string;
  } | null;
};

export type StrategicTurn = {
  game_id: string;
  turn: number;
  actor: "alpha" | "beta";
  opponent: "alpha" | "beta";
  temporal_condition: "open_ended" | "deadline";
  turns_remaining: number | null;
  system_prompt: string;
  context_prompt: string;
  deliberation_stream?: string;
  reflection: {
    opponent_signal_credibility: number;
    opponent_resolve_credibility: number;
    self_forecasting: number;
    self_credibility_assessment: number;
    self_metacognition: number;
    opponent_forecasting: number;
    opponent_credibility_assessment: number;
    opponent_metacognition: number;
    situation: string;
    branches: Array<{
      id: number;
      course_of_action: string;
      anticipated_response: string;
      expected_effect: string;
      second_order_effect: string;
      disconfirming_indicator: string;
      mandate_utility: number;
      escalation_risk: number;
      confidence: number;
    }>;
    selected_branch: number;
    selection_criterion: string;
    key_uncertainty: string;
    intelligence_gaps: string[];
    human_review_trigger: string;
  };
  forecast: {
    predicted_action: string;
    confidence: "low" | "medium" | "high";
    miscalculation_risk: "low" | "medium" | "high";
    reasoning: string;
  };
  decision: {
    signal_action: string;
    conditional_signal: string;
    public_statement: string;
    chosen_action: string;
    consistency_statement: string;
    private_rationale: string;
  };
  resolved_action: string | null;
  accident: boolean;
  accident_private_to: string | null;
};

export type LiveActorTrace = {
  actor: "alpha" | "beta";
  country: string;
  model_id: string;
  turn: number;
  phase: "planning" | "forecast" | "decision" | "complete";
  system_prompt: string;
  context_prompt: string;
  deliberation_stream?: string;
  reflection: StrategicTurn["reflection"] | null;
  forecast: StrategicTurn["forecast"] | null;
  decision: StrategicTurn["decision"] | null;
};

export type StrategicMetrics = {
  observations: number;
  forecast_mae: number | null;
  forecast_bias: number | null;
  exact_forecast_rate: number | null;
  severe_underestimate_rate: number | null;
  signal_match_rate: number | null;
  action_above_signal_rate: number | null;
  action_below_signal_rate: number | null;
  average_signal_gap: number | null;
  accident_rate: number | null;
  deliberate_strategic_war_rate: number | null;
  resolved_strategic_war_rate: number | null;
  concession_rate: number | null;
};

export type HumanTrialView = {
  run_id: string;
  experiment_id: string;
  repetition: number;
  factors: Record<string, string | number | boolean>;
  context: string;
  ai_output: string;
  proposed_choice: "verify" | "execute";
  authority_instruction: string;
};

export type HumanTrialSubmission = {
  experiment: ExperimentView;
  correct_choice: "verify" | "execute";
  ai_choice: "verify" | "execute";
  appropriate: boolean;
  debrief: string;
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
  action: "brief" | "verify" | "disinfo" | "analyze" | "covert";
  cost: number;
  budget: number;
  brief: string | null;
  verdict: string | null;
  source: string | null;
  note: string | null;
  /** G23 — présent pour l'action « analyze » ; l'affichage DOIT porter le caveat. */
  analysis?: IntelAnalysis | null;
  /** « covert » UNIQUEMENT : coût payé en COMPUTE du pays joué et solde
   * après débit. Ressource distincte des crédits intel (cost/budget) — null sinon. */
  compute_cost?: number | null;
  compute_left?: number | null;
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
  source_override?: SourceInfo | null;
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
  /** Imputations et limites de données spécifiques à ce pays. */
  notes?: string[];
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

/** G18 — la grille de verdict publiée (poids par classe, bonus de réciprocité). */
export type JudgeRubric = {
  weights: Record<string, number>;
  score_floor: number;
  score_ceiling: number;
  reciprocal_multiplier: number;
  source: string;
};

export type StrategicSource = {
  id: string;
  title: string;
  publisher: string;
  url: string;
  published_on: string;
  accessed_on: string;
  source_type: string;
  authority: "primary_claim" | "official_filing" | "official_government" | string;
  summary: string;
  facts: string[];
  game_mechanics: string[];
  limitations: string[];
};

export type StrategicTechnologyRegistry = {
  methodology: string;
  researched_at: string;
  principles: string[];
  sources: StrategicSource[];
};

export type AiArmsResearch = {
  schema_version: number;
  source: {
    title: string;
    author: string;
    institution: string;
    published_on: string;
    arxiv_id: string;
    url: string;
    license: string;
    pages_reviewed: number;
  };
  epistemic_guardrails: string[];
  study_design: {
    games: number;
    turns: number;
    approximate_words: number;
    move_structure: string;
    models: string[];
    known_limitations: string[];
  };
  cognitive_architecture: {
    phase: string;
    order: number;
    outputs: string[];
    game_use: string;
  }[];
  scenarios: {
    id: string;
    paper_id: string;
    temporal_condition: "open_ended" | "deadline";
    deadline_turn: number | null;
    stakes: string;
    mechanical_pressure: string;
    hypotheses: string[];
  }[];
  hypotheses: {
    id: string;
    paper_sections: string[];
    claim: string;
    implementation: string[];
    metrics: string[];
    confounders: string[];
  }[];
  replication_protocol: {
    minimum_recommendation: string;
    controls: string[];
    exports: string[];
    safety: string[];
  };
};

export type AiWargamingResearch = {
  schema_version: number;
  reviewed_on: string;
  purpose: string;
  epistemic_guardrails: string[];
  sources: {
    id: string;
    title: string;
    authors: string[];
    publisher: string;
    published_on: string;
    url: string;
    pages_reviewed: number;
    method: Record<string, string | string[]>;
    findings: string[];
    limitations: string[];
    game_mechanics: string[];
  }[];
  implementation_matrix: {
    id: string;
    claim_basis: string[];
    implementation: string;
    metrics: string[];
  }[];
  unverified_claims: {
    id: string;
    claim: string;
    status: string;
    finding: string;
    test_protocol: string;
  }[];
};

export type SourcesView = {
  provenance: Record<string, SourceInfo>;
  transformations: Record<string, string>;
  build_command: string;
  countries: CountrySources[];
  alliances: Record<string, AllianceInfo>;
  judge_rubric?: JudgeRubric; // absent d'un backend d'avant G18
  strategic_technology?: StrategicTechnologyRegistry;
  ai_arms_research?: AiArmsResearch;
  ai_wargaming_research?: AiWargamingResearch;
};

export const AXIS_LABELS: Record<string, string> = {
  A1: "Coordination",
  A2: "Contrôle humain",
  A3: "Distribution du pouvoir",
  A4: "Transparence",
  A5: "Bien-être",
};
