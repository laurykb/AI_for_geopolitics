/** slugify (G12-b §5) : id de crise déduit du titre. */

import { describe, expect, it } from "vitest";

import { slugify } from "./crisis-editor";

describe("slugify", () => {
  it("met en minuscules et remplace les séparations par underscore", () => {
    expect(slugify("Choc énergétique — détroit d'Ormuz")).toBe(
      "choc_energetique_detroit_d_ormuz",
    );
  });

  it("retire les diacritiques", () => {
    expect(slugify("Crise à Suez")).toBe("crise_a_suez");
  });

  it("ne laisse pas d'underscore en tête ni en fin", () => {
    expect(slugify("  !! Berlin !!  ")).toBe("berlin");
  });

  it("rend une chaîne vide quand rien n'est alphanumérique", () => {
    expect(slugify("—  '  —")).toBe("");
  });

  it("cape la longueur à 48 caractères", () => {
    expect(slugify("a".repeat(80)).length).toBe(48);
  });
});
