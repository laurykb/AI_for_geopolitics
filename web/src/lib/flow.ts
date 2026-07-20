/** Machine à états de création de partie (G11-b §1 S2-S4) — logique pure, testable.
 *
 * Le flow séquentiel mode → rôle → pays, sans dépendance React : le conteneur
 * (`app/lobby`) porte l'état et l'UI, ce module porte les règles (transitions, gating
 * « 7 exactement », mapping vers l'API). RG-2 : deux modes seulement (Classique,
 * Campagne) ; le Brouillard et le Réel/escalade sont des réglages cochables, plus des
 * modes ; la Dérive est transversale (RG-3 la rendra toujours active en Classique).
 * L'architecte est fondu dans le Game Master. */

import type { TableSetting } from "./temperament";
import type { CreateGameBody, Difficulty, GameMode, GameRole, ResearchModel } from "./types";

// --- casting des pays (la pensée native est la denrée que
// le jeu évalue) -----------------------------------------------------------------

/** Tag de référence proposé par défaut pour les pays quand le casting est désactivé
 * (un seul modèle) — voir `simulation/model_registry.REASONING_ROLE` côté backend, qui
 * REFUSE tout modèle non-reasoning affecté à un pays quel que soit le choix ici fait. */
export const DEFAULT_COUNTRY_MODEL_TAG = "deepseek-r1:7b";

/** Modèles installés proposables pour incarner un PAYS : uniquement le rôle
 * `reasoning` du panel — les généralistes (`retired`) et la voie lente du laboratoire
 * (`slow_robustness_only`) en sont exclus (le Game Master/juge restent sur un pool plus
 * large, non filtré ici — cf. réserve du rapport de casting). */
export function reasoningCountryModels(models: ResearchModel[]): ResearchModel[] {
  return models.filter((model) => model.installed && model.role === "reasoning");
}

/** Sélection par défaut du casting pays : deepseek-r1:7b s'il est installé, sinon le
 * premier modèle de raisonnement disponible, sinon aucun (multi-modèle indisponible). */
export function defaultCountryCastModels(eligible: ResearchModel[]): string[] {
  const preferred = eligible.find((model) => model.tag === DEFAULT_COUNTRY_MODEL_TAG);
  const fallback = preferred ? [preferred] : eligible.slice(0, 1);
  return fallback.map((model) => model.tag);
}

// --- écrans ---------------------------------------------------------------------

export type FlowStep = "mode" | "role" | "pays";
export const FLOW_STEPS: readonly FlowStep[] = ["mode", "role", "pays"] as const;

/** Étape précédente (retour arrière sans perte) — null si on est au début. */
export function prevStep(step: FlowStep): FlowStep | null {
  const i = FLOW_STEPS.indexOf(step);
  return i > 0 ? FLOW_STEPS[i - 1] : null;
}

/** Étape suivante — null si on est au bout (→ lancer la partie). */
export function nextStep(step: FlowStep): FlowStep | null {
  const i = FLOW_STEPS.indexOf(step);
  return i < FLOW_STEPS.length - 1 ? FLOW_STEPS[i + 1] : null;
}

// --- trois portes : jeu libre, histoire et recherche -----------------------------

/** Les 3 cartes de mode. `value` = mode envoyé à l'API ou destination autonome (clé i18n :
 * `lobby.mode.<value>.titre/blurb/apprend`) ; `campaign` = ce mode remplace S4 par la
 * sélection de chapitre (pays imposés par la fiche). Le Brouillard et le Réel/escalade
 * ne sont plus des cartes : ce sont des interrupteurs (voir FlowSettings). Les libellés
 * vivent dans l'i18n (fr/en) — le composant les traduit via `t`. */
export type FlowMode = {
  value: GameMode | "laboratory";
  destination?: "/campagne" | "/laboratoire";
};

export const FLOW_MODES: readonly FlowMode[] = [
  { value: "classic" },
  { value: "campaign", destination: "/campagne" },
  { value: "laboratory", destination: "/laboratoire" },
] as const;

export type LobbyMode = (typeof FLOW_MODES)[number]["value"];

// --- rôles (S3) -----------------------------------------------------------------

/** Les rôles du flow (§0/S3 + G12 §3). `invent` = « Créer son pays » (forge), `gm` =
 * Game Master (événements + consignes globales), `spectator` = le parieur (parie, ne
 * motionne ni ne prompte). */
export type FlowRole = "player" | "invent" | "gm" | "spectator";

/** Rôle du flow → rôle d'API (l'architecte porte les pouvoirs du Game Master). */
export function backendRole(role: FlowRole): GameRole {
  if (role === "gm") return "architect";
  if (role === "spectator") return "spectator";
  return "player";
}

// --- réglages transversaux (S2) -------------------------------------------------

export type FlowSettings = {
  fog: boolean; // RG-2 — réglage Brouillard (off par défaut)
  escalation: boolean; // RG-2 — réglage Réel/escalade (off par défaut)
  rounds: number; // curseur 3-20 → horizon
  difficulty: Difficulty;
  free: boolean; // partie libre : off par défaut (on = consignes globales + composition de table)
  table?: TableSetting; // G17 — composition de la table (partie LIBRE uniquement)
  // Pensée à découvert : off par défaut (huis clos actuel) — on = pensée native
  // streamée en direct + journaux complets relisibles pendant la partie.
  expose_thinking: boolean;
};

export const ROUNDS_MIN = 3;
export const ROUNDS_MAX = 20;

export const DEFAULT_SETTINGS: FlowSettings = {
  fog: false,
  escalation: false,
  rounds: 5,
  difficulty: "intermediate",
  free: false,
  expose_thinking: false,
};

// --- sélection des pays (S4) ----------------------------------------------------

/** Le sommet compte toujours 7 États (§1 S4). « Créer son pays » en pose 6 sur la
 * carte + 1 forgé ; « Jouer un pays » et « Game Master » en posent 7. */
export const SUMMIT_EXACT = 7;

/** Combien de pays cliquer sur la carte selon le rôle (le pays inventé complète). */
export function mapCapacity(role: FlowRole): number {
  return role === "invent" ? SUMMIT_EXACT - 1 : SUMMIT_EXACT;
}

/** Rabote une sélection à la capacité d'un rôle (au changement de rôle : « Créer son
 * pays » ne garde que 6 États sur la carte, le pays forgé complétant le sommet). */
export function trimForRole(selected: string[], role: FlowRole): string[] {
  return selected.slice(0, mapCapacity(role));
}

/** Bascule blanc↔jaune : retire si présent, ajoute si sous la capacité, sinon ignore
 * (le sommet ne dépasse jamais sa taille — le bouton reste grisé jusqu'au compte pile). */
export function toggleCountry(selected: string[], id: string, capacity: number): string[] {
  if (selected.includes(id)) return selected.filter((c) => c !== id);
  if (selected.length >= capacity) return selected; // plein : clic ignoré
  return [...selected, id];
}

/** La carte est-elle complète pour ce rôle (7 pile, ou 6 pile pour l'invention) ? */
export function mapComplete(role: FlowRole, selected: string[]): boolean {
  return selected.length === mapCapacity(role);
}

/** Peut-on lancer la partie ? Gating final selon le rôle (drapeau / nom du pays inventé). */
export function canLaunch(
  role: FlowRole,
  selected: string[],
  opts: { flag?: string | null; inventName?: string } = {},
): boolean {
  if (!mapComplete(role, selected)) return false;
  if (role === "player") return !!opts.flag && selected.includes(opts.flag);
  if (role === "invent") return (opts.inventName?.trim().length ?? 0) >= 2;
  return true; // gm : 7 pays suffisent
}

// --- résolution vers l'API ------------------------------------------------------

/** Assemble le corps `POST /api/games` à partir de l'état du flow. RG-2 : le mode part
 * tel quel (classic — la Campagne passe par la sélection de chapitre, pas par ici) ; le
 * Brouillard et le Réel/escalade sont des drapeaux cochables. La Dérive n'est plus un
 * choix de lobby (RG-3 la formalisera « toujours active en Classique »). */
export function buildCreateBody(args: {
  scenario: string;
  baseMode: GameMode;
  settings: FlowSettings;
  role: FlowRole;
  selected: string[];
  flag?: string | null;
  ownerId?: string;
  invent?: CreateGameBody["invent"];
  language?: "fr" | "en"; // G14 — réglage utilisateur, lu par le backend dès CC-3
  modelCast?: CreateGameBody["model_cast"];
}): CreateGameBody {
  const {
    scenario,
    baseMode,
    settings,
    role,
    selected,
    flag,
    ownerId,
    invent,
    language,
    modelCast,
  } = args;
  return {
    scenario,
    countries: selected,
    horizon: settings.rounds,
    mode: baseMode,
    fog: settings.fog,
    escalation: settings.escalation,
    role: backendRole(role),
    difficulty: settings.difficulty,
    free: settings.free,
    expose_thinking: settings.expose_thinking,
    language,
    // G17 — la composition de table ne part qu'en partie libre (sinon table équilibrée).
    table: settings.free ? (settings.table ?? "equilibree") : undefined,
    owner_id: ownerId,
    play_as: role === "player" ? (flag ?? undefined) : role === "invent" ? invent?.name : undefined,
    invent: role === "invent" ? invent : undefined,
    model_cast: modelCast,
  };
}
