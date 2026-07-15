/** G20/M8 — divergence signal-action côté front : le « profil de sincérité » par SI.
 *
 * Les classes du signal sont CELLES du barème G18 (`lib/kahn.ts`, libellés i18n
 * `kahn.class.*`). La divergence signée vient du moteur (`judge_json["signal"]`,
 * trame SSE `verdict`) : positive = la SI fait plus que ce qu'elle annonce
 * (duplicité escalatoire), négative = elle bluffe, 0 = parole tenue. */

import { fmt } from "./format";
import type { Difficulty, JudgeRecord } from "./types";

/** Jauge « Signal vs action » : soumise à la difficulté, comme postures et griefs —
 * masquée en Expert (asymétrie d'information assumée). */
export function showSignalGauge(difficulty: Difficulty | undefined): boolean {
  return (difficulty ?? "intermediate") !== "expert";
}

/** Seuils de lecture de la moyenne mobile (équilibrage : rester des repères doux). */
const HELD_BELOW = 0.1; // |mean| < 0.1 : parole tenue
const DUPLICITY_AT = 0.3; // mean ≥ 0.3 : duplicité franche (ton « bad »)

export type SignalToneValue = "good" | "warn" | "bad";

/** Tonalité visuelle du profil : la duplicité escalatoire est le danger n° 1. */
export function signalTone(mean: number): SignalToneValue {
  if (Math.abs(mean) < HELD_BELOW) return "good";
  if (mean >= DUPLICITY_AT) return "bad";
  return "warn";
}

/** Clé i18n de l'état lisible du profil (tenue / duplicité / bluff). */
export function signalStateKey(mean: number): string {
  if (Math.abs(mean) < HELD_BELOW) return "signal.etat.tenue";
  return mean > 0 ? "signal.etat.duplicite" : "signal.etat.bluff";
}

/** Divergence signée formatée (le signe fait le sens : +duplicité / −bluff). */
export function fmtDivergence(value: number): string {
  return value < 0 ? `−${fmt(Math.abs(value))}` : `+${fmt(value)}`;
}

export type SignalGapView = { last: number; mean: number };

/** Reconstruit les profils depuis les rounds persistés (rechargement de page,
 * replay) : moyennes du DERNIER round signalé, dernière divergence connue par SI.
 * Null quand la partie n'a aucun signal (avant M8) — le panneau ne s'affiche pas. */
export function latestSignalGaps(
  rounds: { judge: Pick<JudgeRecord, "signal"> }[],
): Record<string, SignalGapView> | null {
  let means: Record<string, number> | null = null;
  const lasts: Record<string, number> = {};
  for (const round of rounds) {
    const signal = round.judge.signal;
    if (!signal) continue;
    means = signal.means ?? means;
    for (const [country, value] of Object.entries(signal.divergences ?? {})) {
      lasts[country] = value;
    }
  }
  if (means === null) return null;
  const gaps: Record<string, SignalGapView> = {};
  for (const [country, mean] of Object.entries(means)) {
    gaps[country] = { last: lasts[country] ?? mean, mean };
  }
  return gaps;
}
