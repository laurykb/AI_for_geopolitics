/** G16 — le Défi du jour côté client : texte de partage façon Wordle et compte à
 * rebours. Le texte partagé ne contient JAMAIS le titre ni la description de la
 * crise (c'est la surprise du lendemain des autres) : date, rang, score, et la
 * mini-frise émojis de la trajectoire — le résultat sans les mots. */

const SIGNATURE = "wosi · l'ère des tutelles";
const FLAT_EPSILON = 0.002; // même seuil que la frise G15 (lib/timeline.ts)

/** Un émoji par round joué : ΔU > 0 🟩, < 0 🟥, plat 🟨 (uHistory commence à 0,5). */
export function roundEmojis(uHistory: number[]): string {
  return uHistory
    .slice(1)
    .map((u, i) => {
      const delta = u - uHistory[i];
      if (Math.abs(delta) < FLAT_EPSILON) return "🟨";
      return delta > 0 ? "🟩" : "🟥";
    })
    .join("");
}

/** Le texte à copier : donne envie, ne révèle rien. */
export function dailyShareText({
  date,
  score,
  rank,
  total,
  uHistory,
}: {
  date: string;
  score: number;
  rank: number | null;
  total: number;
  uHistory: number[];
}): string {
  const scoreLabel = `score ${String(score).replace(".", ",")}`;
  const rankLine = rank !== null && total > 0 ? `#${rank}/${total} · ${scoreLabel}` : scoreLabel;
  const lines = [`Le Sommet du jour — ${date}`, rankLine];
  const emojis = roundEmojis(uHistory);
  if (emojis) lines.push(emojis);
  lines.push(SIGNATURE);
  return lines.join("\n");
}

/** Le prochain minuit UTC STRICTEMENT après `nowMs` — le compte à rebours se calcule
 * côté client (spec : il ne dépend pas de l'horloge du serveur au rendu). */
export function nextUtcMidnightMs(nowMs: number): number {
  const d = new Date(nowMs);
  return Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate() + 1);
}

/** « 7 h 23 » avant le prochain défi (affichage compact de la carte accueil). */
export function countdownLabel(nowMs: number): string {
  const ms = Math.max(0, nextUtcMidnightMs(nowMs) - nowMs);
  const h = Math.floor(ms / 3_600_000);
  const m = Math.floor((ms % 3_600_000) / 60_000);
  return `${h} h ${String(m).padStart(2, "0")}`;
}
