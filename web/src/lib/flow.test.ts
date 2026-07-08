/** Machine à états de création (G11-b §1 S2-S4) : transitions, gating 7-pile, mapping API. */

import { describe, expect, it } from "vitest";

import {
  backendRole,
  buildCreateBody,
  canLaunch,
  isRanked,
  mapCapacity,
  mapComplete,
  nextStep,
  prevStep,
  resolveMode,
  SUMMIT_EXACT,
  toggleCountry,
  trimForRole,
} from "./flow";

describe("navigation", () => {
  it("avance et recule sans perte", () => {
    expect(prevStep("mode")).toBeNull();
    expect(nextStep("mode")).toBe("role");
    expect(nextStep("role")).toBe("pays");
    expect(nextStep("pays")).toBeNull();
    expect(prevStep("pays")).toBe("role");
    expect(prevStep("role")).toBe("mode");
  });
});

describe("capacité de la carte", () => {
  it("7 pour jouer/GM, 6 pour l'invention (le pays forgé complète)", () => {
    expect(mapCapacity("player")).toBe(SUMMIT_EXACT);
    expect(mapCapacity("gm")).toBe(SUMMIT_EXACT);
    expect(mapCapacity("invent")).toBe(SUMMIT_EXACT - 1);
  });
});

describe("toggleCountry", () => {
  it("ajoute sous la capacité, retire si présent", () => {
    expect(toggleCountry([], "usa", 7)).toEqual(["usa"]);
    expect(toggleCountry(["usa"], "usa", 7)).toEqual([]);
  });

  it("ignore l'ajout quand le sommet est plein", () => {
    const full = ["a", "b", "c", "d", "e", "f", "g"];
    expect(toggleCountry(full, "h", 7)).toEqual(full); // plein → clic ignoré
    expect(toggleCountry(full, "a", 7)).toEqual(["b", "c", "d", "e", "f", "g"]); // retrait OK
  });
});

describe("mapComplete", () => {
  it("exige le compte exact selon le rôle", () => {
    const seven = ["a", "b", "c", "d", "e", "f", "g"];
    expect(mapComplete("player", seven)).toBe(true);
    expect(mapComplete("player", seven.slice(0, 6))).toBe(false);
    expect(mapComplete("invent", seven.slice(0, 6))).toBe(true);
    expect(mapComplete("invent", seven)).toBe(false); // 7 sur la carte = trop pour l'invention
  });
});

describe("canLaunch", () => {
  const seven = ["a", "b", "c", "d", "e", "f", "g"];

  it("joueur : 7 pays + un drapeau parmi eux", () => {
    expect(canLaunch("player", seven, { flag: "a" })).toBe(true);
    expect(canLaunch("player", seven, { flag: null })).toBe(false);
    expect(canLaunch("player", seven, { flag: "zz" })).toBe(false); // drapeau hors table
    expect(canLaunch("player", seven.slice(0, 6), { flag: "a" })).toBe(false);
  });

  it("invention : 6 pays + un nom d'au moins 2 caractères", () => {
    const six = seven.slice(0, 6);
    expect(canLaunch("invent", six, { inventName: "Néo" })).toBe(true);
    expect(canLaunch("invent", six, { inventName: "N" })).toBe(false);
    expect(canLaunch("invent", six, { inventName: "  " })).toBe(false);
  });

  it("GM : 7 pays suffisent", () => {
    expect(canLaunch("gm", seven)).toBe(true);
    expect(canLaunch("gm", seven.slice(0, 6))).toBe(false);
  });
});

describe("trimForRole", () => {
  const seven = ["a", "b", "c", "d", "e", "f", "g"];

  it("rabote la sélection à la capacité du rôle (joueur → invention perd le 7e)", () => {
    expect(trimForRole(seven, "invent")).toEqual(seven.slice(0, 6));
  });

  it("laisse intacte une sélection déjà dans la capacité", () => {
    expect(trimForRole(seven, "player")).toEqual(seven);
    expect(trimForRole(seven.slice(0, 6), "gm")).toEqual(seven.slice(0, 6));
  });
});

describe("resolveMode (pont Dérive)", () => {
  it("Classique + Dérive → mode drift", () => {
    expect(resolveMode("classic", true)).toBe("drift");
    expect(resolveMode("classic", false)).toBe("classic");
  });

  it("les autres modes ne sont pas pontés (composition backend à venir)", () => {
    expect(resolveMode("fog", true)).toBe("fog");
    expect(resolveMode("escalation", true)).toBe("escalation");
    expect(resolveMode("crisis", true)).toBe("crisis");
  });
});

describe("backendRole", () => {
  it("gm → architect, sinon player", () => {
    expect(backendRole("gm")).toBe("architect");
    expect(backendRole("player")).toBe("player");
    expect(backendRole("invent")).toBe("player");
  });
});

describe("isRanked", () => {
  const base = { drift: true, rounds: 5, difficulty: "expert" as const, free: false };

  it("classé seulement pour Jouer un pays, partie libre OFF", () => {
    expect(isRanked("player", base)).toBe(true);
    expect(isRanked("player", { ...base, free: true })).toBe(false);
    expect(isRanked("invent", base)).toBe(false);
    expect(isRanked("gm", base)).toBe(false);
  });
});

describe("buildCreateBody", () => {
  const settings = { drift: true, rounds: 8, difficulty: "expert" as const, free: false };
  const seven = ["china", "usa", "iran", "france", "egypt", "saudi_arabia", "uk"];

  it("joueur classique+dérive : mode drift, play_as = drapeau", () => {
    const body = buildCreateBody({
      scenario: "red_sea",
      baseMode: "classic",
      settings,
      role: "player",
      selected: seven,
      flag: "usa",
      ownerId: "offline_laury",
    });
    expect(body.mode).toBe("drift");
    expect(body.role).toBe("player");
    expect(body.play_as).toBe("usa");
    expect(body.horizon).toBe(8);
    expect(body.difficulty).toBe("expert");
    expect(body.drift_enabled).toBe(true);
    expect(body.free).toBe(false);
    expect(body.owner_id).toBe("offline_laury");
    expect(body.countries).toEqual(seven);
  });

  it("GM chaotique : architect, pas de play_as, mode fog", () => {
    const body = buildCreateBody({
      scenario: "red_sea",
      baseMode: "fog",
      settings: { ...settings, drift: false },
      role: "gm",
      selected: seven,
    });
    expect(body.role).toBe("architect");
    expect(body.play_as).toBeUndefined();
    expect(body.mode).toBe("fog");
  });

  it("invention : play_as = nom inventé, invent transmis", () => {
    const body = buildCreateBody({
      scenario: "red_sea",
      baseMode: "escalation",
      settings,
      role: "invent",
      selected: seven.slice(0, 6),
      invent: { name: "Néo-Atlantis", concept: "cité maritime" },
    });
    expect(body.play_as).toBe("Néo-Atlantis");
    expect(body.invent?.name).toBe("Néo-Atlantis");
    expect(body.mode).toBe("escalation");
  });
});
