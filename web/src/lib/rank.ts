/** Rangs de carrière (RG-1) — les blasons suivent le NIVEAU d'XP, plus les points de ligue.
 *
 * L'art des blasons (`RankBadge`) est inchangé : seule la SOURCE du rang bascule des LP
 * vers le niveau. On traduit un niveau en rang + progression vers le rang suivant, pour
 * l'accueil et le profil. Miroir de `simulation/xp.py` (`RANKS` / `rank_for_level`). */

export type Rank = {
  name: string;
  minLevel: number; // niveau minimal pour entrer dans le rang
  tier: number; // 0..6 — sert au dégradé du blason (sobre, pas d'emoji)
};

/** Seuils par niveau, miroir du backend. Triés du plus haut au plus bas pour `rankForLevel`. */
export const RANKS: readonly Rank[] = [
  { name: "Éminence", minLevel: 30, tier: 6 },
  { name: "Chancelier", minLevel: 22, tier: 5 },
  { name: "Ministre", minLevel: 15, tier: 4 },
  { name: "Ambassadeur", minLevel: 10, tier: 3 },
  { name: "Diplomate", minLevel: 6, tier: 2 },
  { name: "Émissaire", minLevel: 3, tier: 1 },
  { name: "Attaché", minLevel: 1, tier: 0 },
] as const;

export type RankProgress = {
  rank: Rank;
  next: Rank | null; // null au rang maximal (Éminence)
  toNext: number; // niveaux restants avant le rang suivant (0 au sommet)
  progress: number; // 0..1 vers le rang suivant (1 au sommet)
};

/** Rang atteint à un niveau donné, et la progression (en niveaux) vers le suivant. */
export function rankForLevel(level: number): RankProgress {
  const lvl = Math.max(1, Math.floor(level));
  const idx = RANKS.findIndex((r) => lvl >= r.minLevel); // RANKS est décroissant
  const rank = RANKS[idx];
  const next = idx > 0 ? RANKS[idx - 1] : null;
  const span = next ? next.minLevel - rank.minLevel : 0;
  const toNext = next ? Math.max(0, next.minLevel - lvl) : 0;
  const progress = next ? Math.min(1, (lvl - rank.minLevel) / span) : 1;
  return { rank, next, toNext, progress };
}
