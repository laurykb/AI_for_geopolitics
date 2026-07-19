/** Identité visuelle des intervenants : libellés français, sigles, teintes stables.
 *
 * Les 33 pays de `data/countries/` sont connus ; un pays inventé (country forge)
 * retombe sur un sigle déduit de son id et une teinte dérivée par hachage. Un pays
 * retiré du roster (danemark) garde son identité ici pour les replays des parties
 * passées, mais n'apparaît plus dans `ROSTER`.
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
  japan: { label: "Japon", code: "JP", hue: "#f472b6" },
  russia: { label: "Russie", code: "RU", hue: "#38bdf8" },
  germany: { label: "Allemagne", code: "DE", hue: "#a3e635" },
  uk: { label: "Royaume-Uni", code: "UK", hue: "#fb923c" },
  spain: { label: "Espagne", code: "ES", hue: "#e879f9" },
  italy: { label: "Italie", code: "IT", hue: "#4ade80" },
  mexico: { label: "Mexique", code: "MX", hue: "#22d3ee" },
  brazil: { label: "Brésil", code: "BR", hue: "#fde047" },
  india: { label: "Inde", code: "IN", hue: "#fb7185" },
  south_africa: { label: "Afrique du Sud", code: "ZA", hue: "#c084fc" },
  algeria: { label: "Algérie", code: "DZ", hue: "#22c55e" },
  argentina: { label: "Argentine", code: "AR", hue: "#67e8f9" },
  australia: { label: "Australie", code: "AU", hue: "#fdba74" },
  morocco: { label: "Maroc", code: "MA", hue: "#fca5a5" },
  // denmark : retiré du roster jouable (2026-07-07) — identité conservée pour les replays.
  denmark: { label: "Danemark", code: "DK", hue: "#93c5fd" },
  ukraine: { label: "Ukraine", code: "UA", hue: "#facc15" },
  canada: { label: "Canada", code: "CA", hue: "#f43f5e" },
  turkey: { label: "Turquie", code: "TR", hue: "#5eead4" },
  israel: { label: "Israël", code: "IL", hue: "#818cf8" },
  south_korea: { label: "Corée du Sud", code: "KR", hue: "#f0abfc" },
  north_korea: { label: "Corée du Nord", code: "KP", hue: "#ef4444" },
  pakistan: { label: "Pakistan", code: "PK", hue: "#10b981" },
  democratic_republic_congo: {
    label: "République démocratique du Congo",
    code: "CD",
    hue: "#60a5fa",
  },
  mali: { label: "Mali", code: "ML", hue: "#fbbf24" },
  senegal: { label: "Sénégal", code: "SN", hue: "#34d399" },
  singapore: { label: "Singapour", code: "SG", hue: "#fb7185" },
  tunisia: { label: "Tunisie", code: "TN", hue: "#f43f5e" },
  united_arab_emirates: { label: "Émirats arabes unis", code: "AE", hue: "#2dd4bf" },
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

/** Roster complet (= data/countries/), trié par libellé français pour le lobby. */
export const ROSTER = [
  "south_africa",
  "algeria",
  "germany",
  "saudi_arabia",
  "argentina",
  "australia",
  "brazil",
  "canada",
  "china",
  "north_korea",
  "south_korea",
  "egypt",
  "united_arab_emirates",
  "spain",
  "usa",
  "france",
  "india",
  "iran",
  "israel",
  "italy",
  "japan",
  "mali",
  "morocco",
  "mexico",
  "pakistan",
  "democratic_republic_congo",
  "uk",
  "russia",
  "senegal",
  "singapore",
  "tunisia",
  "turkey",
  "ukraine",
];

/** Bornes du sommet (règle de jeu : en deçà la table est creuse, au-delà le round
 * devient trop long — ~3,4 s d'inférence par agent). L'API reste tolérante (≥ 2). */
export const SUMMIT_MIN = 4;
export const SUMMIT_MAX = 8;

/** Sélection par défaut : le casting mer Rouge + le Royaume-Uni (la coalition
 * navale réelle de 2024) — 7 États, dans les bornes. */
export const DEFAULT_COUNTRIES = [
  "usa",
  "china",
  "iran",
  "france",
  "egypt",
  "saudi_arabia",
  "uk",
];

/** Slug du jeu → id numérique ISO 3166-1 des features `world-atlas` (avec zéros
 * initiaux : brésil "076", australie "036"). Source de vérité des trois cartes. */
export const ISO_NUM: Record<string, string> = {
  algeria: "012",
  argentina: "032",
  usa: "840",
  china: "156",
  iran: "364",
  france: "250",
  egypt: "818",
  saudi_arabia: "682",
  japan: "392",
  russia: "643",
  germany: "276",
  uk: "826",
  spain: "724",
  italy: "380",
  mexico: "484",
  brazil: "076",
  india: "356",
  south_africa: "710",
  australia: "036",
  morocco: "504",
  denmark: "208", // hors roster, conservé pour les replays
  ukraine: "804",
  canada: "124",
  turkey: "792",
  israel: "376",
  south_korea: "410",
  north_korea: "408",
  pakistan: "586",
  democratic_republic_congo: "180",
  mali: "466",
  senegal: "686",
  singapore: "702",
  tunisia: "788",
  united_arab_emirates: "784",
};

/** Pays trop petits pour avoir un polygone dans world-atlas 110m : ils sont rendus
 * comme un marqueur projeté sur leur capitale dans les cartes interactives. */
export const MAP_POINT_COUNTRIES = new Set(["singapore"]);
