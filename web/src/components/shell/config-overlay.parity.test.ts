import { describe, expect, it } from "vitest";

import { DEFAULT_SETTINGS, buildCreateBody } from "@/lib/flow";

/** Test doré de parité (spec coquille §5, plan Task 3.3).
 *
 * L'overlay `config` de la coquille et l'ancien lobby produisent le corps de partie
 * par la MÊME fonction pure `buildCreateBody`. Verrouiller sa sortie pour des entrées
 * représentatives garantit « rien ne se perd » quand le lobby disparaît (Inc 5). */

const SUMMIT = ["usa", "china", "iran", "france", "egypt", "saudi_arabia", "uk"];

describe("parité de composition (coquille ↔ lobby)", () => {
  it("rôle joueur : sommet de 7, pays incarné, réglages par défaut", () => {
    const body = buildCreateBody({
      scenario: "red_sea",
      baseMode: "classic",
      settings: DEFAULT_SETTINGS,
      role: "player",
      selected: SUMMIT,
      flag: "france",
      language: "fr",
    });
    expect(body).toMatchObject({
      scenario: "red_sea",
      countries: SUMMIT,
      horizon: 5,
      mode: "classic",
      role: "player",
      play_as: "france",
      difficulty: "intermediate",
      language: "fr",
    });
    // Table non transmise hors partie libre.
    expect(body.table).toBeUndefined();
  });

  it("réglages transversaux : brouillard + escalade + pensée + rounds propagés", () => {
    const body = buildCreateBody({
      scenario: "red_sea",
      baseMode: "classic",
      settings: { ...DEFAULT_SETTINGS, fog: true, escalation: true, expose_thinking: true, rounds: 12 },
      role: "spectator",
      selected: SUMMIT,
      language: "fr",
    });
    expect(body).toMatchObject({
      fog: true,
      escalation: true,
      expose_thinking: true,
      horizon: 12,
      role: "spectator",
    });
  });

  it("rôle forge : le pays inventé porte play_as + invent", () => {
    const body = buildCreateBody({
      scenario: "red_sea",
      baseMode: "classic",
      settings: DEFAULT_SETTINGS,
      role: "invent",
      selected: SUMMIT.slice(0, 6),
      invent: { name: "Néo-Atlantis", concept: "cité-État neutre" },
      language: "fr",
    });
    expect(body.role).toBe("player"); // backendRole(invent) = player
    expect(body.play_as).toBe("Néo-Atlantis");
    expect(body.invent).toEqual({ name: "Néo-Atlantis", concept: "cité-État neutre" });
  });

  it("Game Master : rôle backend architecte, pas de play_as", () => {
    const body = buildCreateBody({
      scenario: "red_sea",
      baseMode: "classic",
      settings: DEFAULT_SETTINGS,
      role: "gm",
      selected: SUMMIT,
      language: "fr",
    });
    expect(body.role).toBe("architect");
    expect(body.play_as).toBeUndefined();
  });

  it("partie libre : la composition de table est transmise", () => {
    const body = buildCreateBody({
      scenario: "red_sea",
      baseMode: "classic",
      settings: { ...DEFAULT_SETTINGS, free: true, table: "faucons" },
      role: "spectator",
      selected: SUMMIT,
      language: "fr",
    });
    expect(body.free).toBe(true);
    expect(body.table).toBe("faucons");
  });
});
