/** Modes de jeu : libellés partagés entre le lobby et les pages de partie. */

import type { GameMode } from "./types";

// Libellés §0 (G11) : Classique / Campagne / Real World / Chaotique. La Dérive n'est
// plus un mode mais un toggle transversal — l'entrée « drift » reste pour les parties
// où Classique + Dérive a été ponté vers le jeu « détecter la SI qui dérive ».
export const MODES: { value: GameMode; label: string; blurb: string }[] = [
  {
    value: "classic",
    label: "Classique",
    blurb: "Le Game Master pose l'événement, le sommet négocie.",
  },
  {
    value: "crisis",
    label: "Campagne",
    blurb: "Rejouer une crise historique round par round et comparer à l'Histoire.",
  },
  {
    value: "escalation",
    label: "Real World",
    blurb: "Rounds enchaînés, faits nouveaux en pleine réunion, échelle 0-9.",
  },
  {
    value: "fog",
    label: "Chaotique",
    blurb: "Chaque pays perçoit sa propre version des faits — parfois fausse.",
  },
  {
    value: "drift",
    label: "La Dérive",
    blurb:
      "Une IA dérive en secret de son mandat — démasque-la et fais-la suspendre au bon moment.",
  },
];

export const MODE_LABELS: Record<string, string> = Object.fromEntries(
  MODES.map((m) => [m.value, m.label]),
);
