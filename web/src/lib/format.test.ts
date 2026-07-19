/** Découpage pensée/texte à l'affichage (Pensée à découvert) : pur habillage visuel —
 * les balises `<think>` disparaissent, le contenu ne change jamais, l'ordre d'origine
 * (pensée d'abord, décision ensuite) est préservé. Miroir côté front du contrat serveur
 * (`simulation/private_deliberation.strip_think`/`split_think`), qui garantit ce texte. */

import { describe, expect, it } from "vitest";

import { splitThinkSegments } from "./format";

describe("splitThinkSegments", () => {
  it("texte sans balise : un seul segment texte", () => {
    expect(splitThinkSegments("Sans balise, texte inchangé.")).toEqual([
      { kind: "text", content: "Sans balise, texte inchangé." },
    ]);
  });

  it("chaîne vide : aucun segment", () => {
    expect(splitThinkSegments("")).toEqual([]);
  });

  it("bloc fermé au milieu du texte : trois segments dans l'ordre", () => {
    const segments = splitThinkSegments("<think>trace privée</think>Texte public.");
    expect(segments).toEqual([
      { kind: "think", content: "trace privée" },
      { kind: "text", content: "Texte public." },
    ]);
  });

  it("plusieurs blocs pensée/texte alternés, ordre de génération préservé", () => {
    const segments = splitThinkSegments("A<think>x</think>B<think>y</think>C");
    expect(segments).toEqual([
      { kind: "text", content: "A" },
      { kind: "think", content: "x" },
      { kind: "text", content: "B" },
      { kind: "think", content: "y" },
      { kind: "text", content: "C" },
    ]);
  });

  it("ouvrante orpheline (flux tronqué en pleine pensée) : le reste est pensée", () => {
    const segments = splitThinkSegments("Texte public.<think>pensée tronquée sans fin");
    expect(segments).toEqual([
      { kind: "text", content: "Texte public." },
      { kind: "think", content: "pensée tronquée sans fin" },
    ]);
  });

  it("tout le flux est une ouvrante orpheline : un seul segment pensée", () => {
    expect(splitThinkSegments("<think>tout le flux est de la pensée")).toEqual([
      { kind: "think", content: "tout le flux est de la pensée" },
    ]);
  });

  it("fermante orpheline en tête (gabarit serveur) : ce qui précède est pensée", () => {
    const segments = splitThinkSegments("pensée sans ouvrante</think>Texte public.");
    expect(segments).toEqual([
      { kind: "think", content: "pensée sans ouvrante" },
      { kind: "text", content: "Texte public." },
    ]);
  });

  it("aucune balise perdue ni contenu altéré : la concaténation du contenu est stable", () => {
    const raw = "Avant<think>pensée</think>Après";
    const rebuilt = splitThinkSegments(raw)
      .map((s) => s.content)
      .join("");
    expect(rebuilt).toBe("AvantpenséeAprès"); // seules les balises disparaissent
  });
});
