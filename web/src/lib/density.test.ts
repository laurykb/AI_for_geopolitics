/** CC-15c — la densité d'affichage suit la difficulté, dans le sens de l'audit
 * (`docs/AUDIT_SIMPLICITE.md`) : Débutant/Intermédiaire = surface RÉDUITE (vues
 * simples, replis fermés), Expert = tout affiché par défaut. La difficulté
 * gameplay (budget, seuils du juge, amplitude — moteur) ne change pas ici. */

import { describe, expect, it } from "vitest";

import { advancedOpenByDefault, densityFor, tableDetailedByDefault } from "./density";

describe("densityFor — la règle unique de densité", () => {
  it("Débutant joue en surface réduite", () => {
    expect(densityFor("beginner")).toBe("reduced");
  });

  it("Intermédiaire joue en surface réduite", () => {
    expect(densityFor("intermediate")).toBe("reduced");
  });

  it("Expert voit tout", () => {
    expect(densityFor("expert")).toBe("full");
  });

  it("difficulté absente : surface réduite (défaut sûr)", () => {
    expect(densityFor(undefined)).toBe("reduced");
  });
});

describe("tableDetailedByDefault — la table des pays", () => {
  it("vue réduite (pays + posture + tendance) en Débutant et Intermédiaire", () => {
    expect(tableDetailedByDefault("beginner")).toBe(false);
    expect(tableDetailedByDefault("intermediate")).toBe(false);
  });

  it("les 5 colonnes d'un coup en Expert", () => {
    expect(tableDetailedByDefault("expert")).toBe(true);
  });
});

describe("advancedOpenByDefault — les replis « Options avancées »", () => {
  it("fermés en Débutant et Intermédiaire", () => {
    expect(advancedOpenByDefault("beginner")).toBe(false);
    expect(advancedOpenByDefault("intermediate")).toBe(false);
  });

  it("ouverts en Expert (tout affiché)", () => {
    expect(advancedOpenByDefault("expert")).toBe(true);
  });
});
