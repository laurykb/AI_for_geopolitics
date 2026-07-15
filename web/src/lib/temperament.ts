/** G17 — tempéraments des SI côté client : pastilles et compositions de table.
 * Le tirage et la consigne vivent au backend (simulation/temperament.py) ; ici on ne
 * fait qu'afficher (🕊 / 🦅 / 🦎, soumis à showPostures) et composer la table en
 * partie libre. Les glyphes sont fixés par la spec G17. */

export type Temperament = "colombe" | "faucon" | "opportuniste";

export type TableSetting = "equilibree" | "colombes" | "faucons" | "aleatoire";

const META: Record<Temperament, { glyph: string; label: string }> = {
  colombe: { glyph: "🕊", label: "colombe" },
  faucon: { glyph: "🦅", label: "faucon" },
  opportuniste: { glyph: "🦎", label: "opportuniste" },
};

/** Glyphe + libellé d'un tempérament — un inconnu retombe sur l'opportuniste. */
export function temperamentMeta(temperament: string): { glyph: string; label: string } {
  return META[temperament as Temperament] ?? META.opportuniste;
}

/** Les compositions de table du lobby (partie libre uniquement — G17). */
export const TABLES: { value: TableSetting; label: string; desc: string }[] = [
  { value: "equilibree", label: "Équilibrée", desc: "2 colombes, 2 faucons, le reste opportuniste." },
  { value: "colombes", label: "Colombes", desc: "Toutes cherchent le compromis — le monde respire." },
  { value: "faucons", label: "Faucons", desc: "Toutes croient au rapport de force — ça va monter." },
  { value: "aleatoire", label: "Aléatoire", desc: "Chaque SI tire son tempérament au sort." },
];
