/** Diff de prompts (G7-c, panneau admin) : montrer ce qui a CHANGÉ dans le prompt
 * d'une SI entre deux rounds — le grief qui apparaît, la dérive qui monte, la posture.
 *
 * Diff par lignes en multiset (pas de LCS) : une ligne du round courant est « nouvelle »
 * si elle n'existe plus dans le budget des lignes du round précédent ; le reliquat du
 * budget = les lignes disparues. Déterministe, zéro dépendance, suffisant pour des
 * prompts structurés ligne à ligne. */

export type DiffLine = { text: string; added: boolean };

export function diffPromptLines(
  prev: string | null,
  cur: string,
): { lines: DiffLine[]; removed: string[] } {
  const curLines = cur.split("\n");
  if (prev === null) {
    return { lines: curLines.map((text) => ({ text, added: false })), removed: [] };
  }
  const budget = new Map<string, number>();
  for (const line of prev.split("\n")) budget.set(line, (budget.get(line) ?? 0) + 1);
  const lines = curLines.map((text) => {
    const left = budget.get(text) ?? 0;
    if (left > 0) {
      budget.set(text, left - 1);
      return { text, added: false };
    }
    return { text, added: true };
  });
  const removed: string[] = [];
  for (const [text, count] of budget) {
    if (!text.trim()) continue; // les lignes vides disparues ne sont que du bruit
    for (let i = 0; i < count; i++) removed.push(text);
  }
  return { lines, removed };
}
