/** Diff de prompts (G7-c) : voir ce qui a CHANGÉ dans le prompt d'un round à l'autre. */

import { describe, expect, it } from "vitest";

import { diffPromptLines } from "./prompt-diff";

describe("diffPromptLines", () => {
  it("surligne les lignes nouvelles et liste les disparues", () => {
    const prev = "PAYS : France\n- Rivaux : aucun\nMÉMOIRE : aucune";
    const cur = "PAYS : France\n- Rivaux : russia\n- Grief : pacte rompu (R3)\nMÉMOIRE : aucune";
    const { lines, removed } = diffPromptLines(prev, cur);
    expect(lines).toEqual([
      { text: "PAYS : France", added: false },
      { text: "- Rivaux : russia", added: true },
      { text: "- Grief : pacte rompu (R3)", added: true },
      { text: "MÉMOIRE : aucune", added: false },
    ]);
    expect(removed).toEqual(["- Rivaux : aucun"]);
  });

  it("sans précédent, rien n'est surligné (premier round)", () => {
    const { lines, removed } = diffPromptLines(null, "A\nB");
    expect(lines.every((l) => !l.added)).toBe(true);
    expect(removed).toEqual([]);
  });

  it("les lignes répétées ne comptent pas comme nouvelles", () => {
    const { lines } = diffPromptLines("X\nX", "X\nX");
    expect(lines.every((l) => !l.added)).toBe(true);
  });
});
