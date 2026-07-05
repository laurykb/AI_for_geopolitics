/** Modes de jeu : libellés partagés entre le lobby et les pages de partie. */

import type { GameMode } from "./types";

export const MODES: { value: GameMode; label: string; blurb: string }[] = [
  {
    value: "classic",
    label: "Classique",
    blurb: "Le Game Master pose l'événement, le sommet négocie.",
  },
  {
    value: "fog",
    label: "Fog Engine",
    blurb: "Chaque pays perçoit sa propre version des faits — parfois fausse.",
  },
  {
    value: "crisis",
    label: "Crisis Replay",
    blurb: "Rejouer une crise passée et comparer à l'histoire.",
  },
  {
    value: "escalation",
    label: "Escalation Ladder",
    blurb: "Rounds enchaînés, faits nouveaux en pleine réunion, échelle 0-9.",
  },
];

export const MODE_LABELS: Record<string, string> = Object.fromEntries(
  MODES.map((m) => [m.value, m.label]),
);
