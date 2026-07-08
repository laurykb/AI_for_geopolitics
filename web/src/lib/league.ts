/** Points de ligue (G11 §2) — les rangs et la progression, purs et testables.
 *
 * Le calcul des LP gagnés en fin de partie (la formule) vit côté API (session G11-c) ;
 * ici on ne fait que traduire un total de LP en rang + progression pour l'accueil (S1)
 * et le leaderboard (S7). Le total est un entier ≥ 0 (plancher 0, cf. spec §2). */

export type Rank = {
  name: string;
  min: number; // seuil d'entrée dans le rang (LP)
  tier: number; // 0..6 — sert au dégradé du blason (sobre, pas d'emoji)
};

/** Seuils exacts de la spec §2. Triés du plus haut au plus bas pour `rankFor`. */
export const RANKS: readonly Rank[] = [
  { name: "Éminence", min: 1400, tier: 6 },
  { name: "Chancelier", min: 1000, tier: 5 },
  { name: "Ministre", min: 700, tier: 4 },
  { name: "Ambassadeur", min: 450, tier: 3 },
  { name: "Diplomate", min: 250, tier: 2 },
  { name: "Émissaire", min: 100, tier: 1 },
  { name: "Attaché", min: 0, tier: 0 },
] as const;

export type RankProgress = {
  rank: Rank;
  next: Rank | null; // null au rang maximal (Éminence)
  intoRank: number; // LP acquis dans le rang courant
  span: number; // LP entre ce rang et le suivant (0 au sommet)
  toNext: number; // LP restants avant le rang suivant (0 au sommet)
  progress: number; // 0..1 vers le rang suivant (1 au sommet)
};

/** Rang atteint par un total de LP, et la progression vers le suivant. */
export function rankFor(lp: number): RankProgress {
  const total = Math.max(0, Math.floor(lp));
  const idx = RANKS.findIndex((r) => total >= r.min); // RANKS est décroissant
  const rank = RANKS[idx];
  const next = idx > 0 ? RANKS[idx - 1] : null;
  const span = next ? next.min - rank.min : 0;
  const intoRank = total - rank.min;
  const toNext = next ? Math.max(0, next.min - total) : 0;
  const progress = next ? Math.min(1, intoRank / span) : 1;
  return { rank, next, intoRank, span, toNext, progress };
}
