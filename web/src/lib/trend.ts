/** CC-15c — la « Tendance » d'un pays en un mot, pour la vue réduite de la table
 * des pays : dérivée des mêmes séries d'indices que les sparklines (fenêtre de
 * 4 points). Vote majoritaire des directions : plus de séries qui montent → en
 * hausse ; plus qui descendent → en baisse ; égalité ou rien → stable. */

const WINDOW = 4; // même fenêtre que les sparklines (3 rounds, 4 points)

export type Trend = "up" | "down" | "flat";

export function countryTrend(series: Record<string, number[]> | undefined): Trend {
  if (!series) return "flat";
  let ups = 0;
  let downs = 0;
  for (const values of Object.values(series)) {
    const window = values.slice(-WINDOW);
    if (window.length < 2) continue; // trop court pour une direction honnête
    const delta = window[window.length - 1] - window[0];
    if (delta > 0) ups += 1;
    else if (delta < 0) downs += 1;
  }
  if (ups > downs) return "up";
  if (downs > ups) return "down";
  return "flat";
}
