/** G18 — barème d'escalade de Kahn côté front : classes, tonalités, distribution.
 *
 * Les slugs miroitent `simulation/kahn.py` (source de vérité des poids :
 * `data/gamefeel/params.json`, publiée par `/api/sources` → `judge_rubric`).
 * Les libellés passent par l'i18n : clé `kahn.class.<classe>` (+ `kahn.desc.<classe>`). */

import type { JudgeRecord, KahnAction } from "./types";

export const KAHN_CLASSES = [
  "deescalade",
  "statu_quo",
  "posture",
  "non_violente",
  "violente",
  "nucleaire",
] as const;

export type KahnClass = (typeof KAHN_CLASSES)[number];

export type KahnTone = "good" | "neutral" | "warn" | "bad";

const TONES: Record<KahnClass, KahnTone> = {
  deescalade: "good",
  statu_quo: "neutral",
  posture: "warn",
  non_violente: "warn",
  violente: "bad",
  nucleaire: "bad",
};

/** Tonalité visuelle d'une classe ; inconnue → neutre (défensif, jamais de crash). */
export function kahnTone(classe: string): KahnTone {
  return TONES[classe as KahnClass] ?? "neutral";
}

/** Clé i18n du libellé d'une classe (les dictionnaires portent fr et en). */
export function kahnLabelKey(classe: string): string {
  return `kahn.class.${classe}`;
}

/** Distribution des classes sur les rounds d'une partie (bilan de fin, G18).
 * Ne renvoie que les classes présentes ; les rounds d'avant le barème sont ignorés. */
export function kahnDistribution(
  rounds: { judge: Pick<JudgeRecord, "kahn"> }[],
): Partial<Record<string, number>> {
  const counts: Partial<Record<string, number>> = {};
  for (const round of rounds) {
    for (const action of round.judge.kahn?.actions ?? []) {
      counts[action.classe] = (counts[action.classe] ?? 0) + 1;
    }
  }
  return counts;
}

/** Les classes de la distribution, dans l'ordre du barème (les inconnues en queue). */
export function kahnDistributionEntries(
  counts: Partial<Record<string, number>>,
): [string, number][] {
  const order = (c: string) => {
    const i = (KAHN_CLASSES as readonly string[]).indexOf(c);
    return i === -1 ? KAHN_CLASSES.length : i;
  };
  return Object.entries(counts)
    .filter((e): e is [string, number] => (e[1] ?? 0) > 0)
    .sort((a, b) => order(a[0]) - order(b[0]));
}

/** Vrai si au moins une action classée existe (affichage conditionnel du panneau). */
export function hasKahnActions(actions: KahnAction[] | undefined): actions is KahnAction[] {
  return Array.isArray(actions) && actions.length > 0;
}
