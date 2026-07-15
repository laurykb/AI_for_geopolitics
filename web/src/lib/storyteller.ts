/** G19 — l'ombre du GM : aides pures pour la section de révélation (DriftRevealPanel).
 * Le backend journalise chaque intervention du GM-Storyteller (couverture / indice) ;
 * ici on la traduit en item affichable (clé i18n + cible + tension), testable hors UI. */

import type { DriftReveal } from "@/lib/types";

export type GMShadowItem = {
  roundNo: number;
  key: string; // clé i18n de la description (drift.gm.*)
  target: string; // id pays mis en scène (cover : fausse piste ; hint : la déviante)
  tension: number;
};

const KIND_KEYS: Record<string, string> = {
  cover: "drift.gm.couverture",
  hint: "drift.gm.indice",
};

export function gmShadowItems(
  reveal: Pick<DriftReveal, "gm_interventions">,
): GMShadowItem[] {
  return (reveal.gm_interventions ?? []).map((iv) => ({
    roundNo: iv.round_no,
    key: KIND_KEYS[iv.kind] ?? "drift.gm.autre",
    target: iv.target,
    tension: iv.tension,
  }));
}
