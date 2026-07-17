/** Modes de jeu : libellés partagés entre le lobby et les pages de partie. */

import type { GameMode } from "./types";

// RG-2 — deux modes seulement : Classique et Campagne. Le Brouillard et le Réel/escalade
// sont devenus des réglages cochables (voir `flow.ts`), plus des modes.
export const MODES: { value: GameMode; label: string; blurb: string }[] = [
  {
    value: "classic",
    label: "Classique",
    blurb: "Le Game Master pose l'événement, le sommet négocie.",
  },
  {
    value: "campaign",
    label: "Campagne",
    blurb: "Rejouer une crise historique round par round et comparer à l'Histoire.",
  },
];

export const MODE_LABELS: Record<string, string> = Object.fromEntries(
  MODES.map((m) => [m.value, m.label]),
);
