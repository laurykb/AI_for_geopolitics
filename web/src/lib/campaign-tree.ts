/** Disposition en arbre de la campagne (G12-b §4) : range les chapitres par palier.
 *
 * Pur et testable — extrait de la page pour être vérifié isolément (chemins en Y,
 * robustesse à un cycle éventuel dans `requires`). */

import type { ChapterView } from "./types";

/** Palier d'un chapitre dans l'arbre = plus long chemin de prérequis (racine = 0).
 * Un cycle dans `requires` casse l'arête fautive (retourne 0) au lieu de boucler. */
export function tiersOf(chapters: ChapterView[]): Map<number, ChapterView[]> {
  const byId = new Map(chapters.map((c) => [c.id, c]));
  const memo = new Map<string, number>();
  const visiting = new Set<string>();
  const depth = (id: string): number => {
    if (memo.has(id)) return memo.get(id)!;
    if (visiting.has(id)) return 0; // cycle détecté : on ne suit pas cette arête
    const c = byId.get(id);
    if (!c || c.requires.length === 0) {
      memo.set(id, 0);
      return 0;
    }
    visiting.add(id);
    const d = 1 + Math.max(...c.requires.map(depth));
    visiting.delete(id);
    memo.set(id, d);
    return d;
  };
  const tiers = new Map<number, ChapterView[]>();
  for (const c of chapters) {
    const t = depth(c.id);
    (tiers.get(t) ?? tiers.set(t, []).get(t)!).push(c);
  }
  return tiers;
}
