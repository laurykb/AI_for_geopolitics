/** Fonctions pures de l'auth (G11 §1 S0) : dérivation du pseudo, validation. */

import { describe, expect, it } from "vitest";

import { adminDenied, emailForPseudo, slugify, validateCredentials, type Player } from "./auth";

describe("slugify", () => {
  it("réduit à l'alphanumérique en minuscules, sans accents", () => {
    expect(slugify("Laury")).toBe("laury");
    expect(slugify("Éric Zünd")).toBe("eric-zund");
    expect(slugify("  jean  dupont  ")).toBe("jean-dupont");
  });

  it("ne laisse pas de tiret aux bords", () => {
    expect(slugify("!!Néo!!")).toBe("neo");
    expect(slugify("__a b__")).toBe("a-b");
  });
});

describe("emailForPseudo", () => {
  it("dérive un email technique jamais montré à l'utilisateur", () => {
    expect(emailForPseudo("Laury")).toBe("laury@wosi.local");
    expect(emailForPseudo("Jean Dupont")).toBe("jean-dupont@wosi.local");
  });
});

describe("validateCredentials", () => {
  it("accepte un pseudo et un mot de passe valides", () => {
    expect(validateCredentials("laury", "secret1")).toBeNull();
  });

  it("refuse un pseudo trop court une fois slugifié", () => {
    expect(validateCredentials("ab", "secret1")).toMatch(/pseudo/i);
    expect(validateCredentials("!!", "secret1")).toMatch(/pseudo/i);
  });

  it("refuse un mot de passe trop court", () => {
    expect(validateCredentials("laury", "12345")).toMatch(/mot de passe/i);
  });
});

describe("adminDenied (garde de la vue admin)", () => {
  const player = (is_admin: boolean): Player => ({ id: "p1", pseudo: "laury", is_admin });

  it("renvoie le visiteur non connecté (player null) — pas de spinner infini", () => {
    expect(adminDenied(false, null)).toBe(true);
  });

  it("renvoie le joueur connecté non-admin", () => {
    expect(adminDenied(false, player(false))).toBe(true);
  });

  it("laisse entrer l'admin", () => {
    expect(adminDenied(false, player(true))).toBe(false);
  });

  it("ne décide rien tant que la session charge", () => {
    expect(adminDenied(true, null)).toBe(false);
    expect(adminDenied(true, player(false))).toBe(false);
  });
});
