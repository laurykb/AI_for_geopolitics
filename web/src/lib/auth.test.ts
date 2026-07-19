/** Fonctions pures de l'auth (G11 §1 S0) : dérivation du pseudo, validation. */

import { describe, expect, it, vi } from "vitest";

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

describe("OfflineAuth.signOut — purge serveur de l'invité", () => {
  // localStorage minimal (env node) : l'implémentation offline ne dépend que de
  // getItem/setItem/removeItem.
  const makeStorage = () => {
    const bag = new Map<string, string>();
    return {
      getItem: (k: string) => bag.get(k) ?? null,
      setItem: (k: string, v: string) => void bag.set(k, v),
      removeItem: (k: string) => void bag.delete(k),
    } as Storage;
  };

  it("purge le serveur PUIS oublie l'invité localement ; un compte normal n'est jamais purgé", async () => {
    vi.resetModules();
    const deletePlayer = vi.fn().mockResolvedValue(undefined);
    vi.doMock("./api", () => ({ deletePlayer }));
    (globalThis as { localStorage?: Storage }).localStorage = makeStorage();
    const { OfflineAuth } = await import("./auth");

    const auth = new OfflineAuth();
    const res = await auth.continueAsGuest();
    expect(res.ok).toBe(true);
    const guestId = res.ok ? res.player.id : "";
    await auth.signOut();
    expect(deletePlayer).toHaveBeenCalledWith(guestId); // l'historique serveur part avec lui
    expect(await auth.getPlayer()).toBeNull();

    // Compte normal : signOut ne déclenche AUCUNE purge (l'historique est sa progression).
    deletePlayer.mockClear();
    await auth.signUp("laury-test", "secret1");
    await auth.signOut();
    expect(deletePlayer).not.toHaveBeenCalled();
    vi.doUnmock("./api");
  });

  it("la déconnexion locale aboutit même si la purge serveur échoue (backend absent)", async () => {
    vi.resetModules();
    const deletePlayer = vi.fn().mockRejectedValue(new Error("ECONNREFUSED"));
    vi.doMock("./api", () => ({ deletePlayer }));
    (globalThis as { localStorage?: Storage }).localStorage = makeStorage();
    const { OfflineAuth } = await import("./auth");

    const auth = new OfflineAuth();
    await auth.continueAsGuest();
    await auth.signOut(); // ne doit pas jeter
    expect(deletePlayer).toHaveBeenCalled();
    expect(await auth.getPlayer()).toBeNull();
    vi.doUnmock("./api");
  });
});
