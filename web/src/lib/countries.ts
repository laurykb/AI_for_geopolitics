/** Identité visuelle des intervenants : libellés français, sigles, teintes stables.
 *
 * Les six pays de `data/countries/` sont connus ; un pays inventé (country forge)
 * retombe sur un sigle déduit de son id et une teinte dérivée par hachage.
 */

export type SpeakerMeta = {
  label: string;
  code: string; // sigle de l'avatar (2-3 lettres)
  hue: string; // couleur d'accent (bordure de bulle, avatar)
};

const KNOWN: Record<string, SpeakerMeta> = {
  usa: { label: "États-Unis", code: "US", hue: "#60a5fa" },
  china: { label: "Chine", code: "CN", hue: "#f87171" },
  iran: { label: "Iran", code: "IR", hue: "#34d399" },
  france: { label: "France", code: "FR", hue: "#a78bfa" },
  egypt: { label: "Égypte", code: "EG", hue: "#fbbf24" },
  saudi_arabia: { label: "Arabie saoudite", code: "SA", hue: "#2dd4bf" },
  gm: { label: "Game Master", code: "GM", hue: "#eab308" },
  judge: { label: "Juge", code: "JU", hue: "#818cf8" },
};

const FALLBACK_HUES = ["#60a5fa", "#f472b6", "#4ade80", "#facc15", "#c084fc", "#22d3ee"];

function hash(id: string): number {
  let h = 0;
  for (const ch of id) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return h;
}

export function speakerMeta(id: string): SpeakerMeta {
  const known = KNOWN[id];
  if (known) return known;
  const words = id.split(/[_\s-]+/).filter(Boolean);
  const label = words.map((w) => w[0].toUpperCase() + w.slice(1)).join(" ") || id;
  const code = (words.length > 1 ? words.map((w) => w[0]) : [id.slice(0, 2)])
    .join("")
    .toUpperCase()
    .slice(0, 3);
  return { label, code, hue: FALLBACK_HUES[hash(id) % FALLBACK_HUES.length] };
}

export const DEFAULT_COUNTRIES = ["usa", "china", "iran", "france", "egypt", "saudi_arabia"];
