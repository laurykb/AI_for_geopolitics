/** Couleur sémantique d'un bulletin de motion : un vote affirmatif est positif
 * visuellement (vert), un vote négatif est rouge, l'abstention reste neutre. */
export type MotionVoteTone = "good" | "bad" | "neutral";

export function motionVoteTone(vote: string): MotionVoteTone {
  const normalized = vote.trim().toLocaleLowerCase("fr");
  if (normalized === "pour") return "good";
  if (normalized === "contre") return "bad";
  return "neutral";
}

