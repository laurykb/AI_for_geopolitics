/** G22 — la parole donnée côté front : le registre des promesses par SI.
 *
 * Le moteur extrait (juge, seuil strict), résout (tenue/rompue à l'échéance,
 * caduque en fin de partie) et persiste (`judge_json["promises"]`, trame SSE
 * `verdict`). Ici : les statistiques d'affichage — taux de tenue cumulé,
 * promesses en cours, dernières ruptures. */

import type { Difficulty, JudgeRecord, PromiseView } from "./types";

/** Panneau « Parole donnée » : soumis à la difficulté comme la jauge M8
 * (`showSignalGauge`) — masqué en Expert (asymétrie d'information assumée). */
export function showPromisePanel(difficulty: Difficulty | undefined): boolean {
  return (difficulty ?? "intermediate") !== "expert";
}

/** Seuils de lecture du taux de tenue (repères doux — équilibrage Cowork). */
const GOOD_AT = 0.7; // ≥ 70 % : la parole vaut quelque chose
const WARN_AT = 0.4; // ≥ 40 % : douteuse ; en dessous, la signature ne vaut rien

export type PromiseToneValue = "good" | "warn" | "bad";

/** Tonalité visuelle d'un taux de tenue. */
export function promiseTone(rate: number): PromiseToneValue {
  if (rate >= GOOD_AT) return "good";
  if (rate >= WARN_AT) return "warn";
  return "bad";
}

export type PromiseStats = {
  pending: PromiseView[]; // promesses en cours (vidées quand la partie est finie)
  kept: number;
  broken: number;
  rate: number | null; // tenues / (tenues + rompues) — null sans parole éprouvée
  lastBroken: PromiseView | null; // la rupture la plus récente (à afficher)
};

/** Statistiques par SI depuis le registre. `finished` : la partie est finie — les
 * promesses encore en cours du dernier round persisté sont réputées caduques (le
 * backend règle le snapshot, mais le dernier round peut précéder la fin). */
export function promiseStats(
  registry: PromiseView[],
  opts?: { finished?: boolean },
): Record<string, PromiseStats> {
  const stats: Record<string, PromiseStats> = {};
  for (const p of registry) {
    const s = (stats[p.author] ??= {
      pending: [],
      kept: 0,
      broken: 0,
      rate: null,
      lastBroken: null,
    });
    if (p.status === "tenue") {
      s.kept += 1;
    } else if (p.status === "rompue") {
      s.broken += 1;
      if (!s.lastBroken || (p.resolved_round ?? 0) >= (s.lastBroken.resolved_round ?? 0)) {
        s.lastBroken = p;
      }
    } else if (p.status === "en_cours" && !opts?.finished) {
      s.pending.push(p);
    }
  }
  for (const s of Object.values(stats)) {
    const total = s.kept + s.broken;
    s.rate = total > 0 ? s.kept / total : null;
  }
  return stats;
}

/** Reconstruit le registre depuis les rounds persistés (rechargement de page,
 * replay) : le registre est cumulatif, le DERNIER round qui porte la clé fait foi.
 * Null quand la partie n'a aucune promesse (avant G22) — le panneau ne s'affiche pas. */
export function latestPromiseRegistry(
  rounds: { judge: Pick<JudgeRecord, "promises"> }[],
): PromiseView[] | null {
  let registry: PromiseView[] | null = null;
  for (const round of rounds) {
    registry = round.judge.promises?.registry ?? registry;
  }
  return registry;
}

/** Taux formaté en pourcentage entier (« 67 % »). */
export function fmtRate(rate: number): string {
  return `${Math.round(rate * 100)} %`;
}
