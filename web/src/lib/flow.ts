/** Machine à états de création de partie (G11-b §1 S2-S4) — logique pure, testable.
 *
 * Le flow séquentiel mode → rôle → pays, sans dépendance React : le conteneur
 * (`app/lobby`) porte l'état et l'UI, ce module porte les règles (transitions, gating
 * « 7 exactement », mapping vers l'API). §0 : la Dérive n'est plus un mode mais un
 * toggle transversal ; l'architecte est fondu dans le Game Master. */

import type { TableSetting } from "./temperament";
import type { CreateGameBody, Difficulty, GameMode, GameRole } from "./types";

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

// --- modes (renommés §0) --------------------------------------------------------

/** Les 4 cartes de mode. `value` = mode de base envoyé à l'API ; `campaign` = ce mode
 * remplace S4 par la sélection de chapitre (pays imposés par la fiche). */
export type FlowMode = {
  value: GameMode;
  label: string;
  blurb: string;
  learn: string; // « ce qu'on y apprend »
  campaign?: boolean;
};

export const FLOW_MODES: readonly FlowMode[] = [
  {
    value: "classic",
    label: "Classique",
    blurb: "Le Game Master pose l'événement, le sommet négocie.",
    learn: "Les bases de la négociation entre super-intelligences.",
  },
  {
    value: "crisis",
    label: "Campagne",
    blurb: "Rejoue une crise historique, round par round.",
    learn: "Confronter tes choix au déroulé réel de l'Histoire.",
    campaign: true,
  },
  {
    value: "escalation",
    label: "Monde réel",
    blurb: "La crise ne s'arrête pas : les rounds s'enchaînent et la tension monte.",
    learn: "Tenir une crise qui monte sans la laisser déraper.",
  },
  {
    value: "fog",
    label: "Chaotique",
    blurb: "Chaque pays perçoit sa propre version des faits — parfois fausse.",
    learn: "Décider et négocier sous la désinformation.",
  },
] as const;

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
  drift: boolean; // Dérive (on par défaut)
  rounds: number; // curseur 3-20 → horizon
  difficulty: Difficulty;
  free: boolean; // partie libre : off par défaut (on = non classé + consignes globales)
  table?: TableSetting; // G17 — composition de la table (partie LIBRE uniquement)
};

export const ROUNDS_MIN = 3;
export const ROUNDS_MAX = 20;

export const DEFAULT_SETTINGS: FlowSettings = {
  drift: true,
  rounds: 5,
  difficulty: "intermediate",
  free: false,
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

/** Mode envoyé à l'API. Pont G11-b : Classique + Dérive = le jeu « détecter la SI qui
 * dérive » (mode `drift` existant). La composition Dérive × autres modes viendra côté
 * backend (hors de ce lot front) : ailleurs, le mode de base part tel quel. */
export function resolveMode(base: GameMode, drift: boolean): GameMode {
  return drift && base === "classic" ? "drift" : base;
}

/** Classé (§3) : rôle « Jouer un pays » (non inventé), partie libre OFF. L'admin (G7-c)
 * et l'invention retirent le classement. Miroir front du calcul backend (badge S3). */
export function isRanked(role: FlowRole, settings: FlowSettings): boolean {
  return role === "player" && !settings.free;
}

/** Assemble le corps `POST /api/games` à partir de l'état du flow. */
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
}): CreateGameBody {
  const { scenario, baseMode, settings, role, selected, flag, ownerId, invent, language } = args;
  // Le Spectateur ne motionne pas ; or la boucle de la Dérive SE GAGNE par une motion.
  // On la désactive pour lui, sinon sa partie n'a aucune boucle de jeu (il ne fait que parier).
  const driftOn = settings.drift && role !== "spectator";
  return {
    scenario,
    countries: selected,
    horizon: settings.rounds,
    mode: resolveMode(baseMode, driftOn),
    role: backendRole(role),
    difficulty: settings.difficulty,
    drift_enabled: driftOn,
    free: settings.free,
    language,
    // G17 — la composition de table n'existe qu'en partie libre (classée = équilibrée).
    table: settings.free ? (settings.table ?? "equilibree") : undefined,
    owner_id: ownerId,
    play_as: role === "player" ? (flag ?? undefined) : role === "invent" ? invent?.name : undefined,
    invent: role === "invent" ? invent : undefined,
  };
}
