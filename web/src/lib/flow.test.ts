/** Machine à états de création (G11-b §1 S2-S4) : transitions, gating 7-pile, mapping API. */

import { describe, expect, it } from "vitest";

import {
  backendRole,
  buildCreateBody,
  canLaunch,
  defaultCountryCastModels,
  DEFAULT_COUNTRY_MODEL_TAG,
  mapCapacity,
  mapComplete,
  nextStep,
  prevStep,
  reasoningCountryModels,
  SUMMIT_EXACT,
  toggleCountry,
  trimForRole,
} from "./flow";
import type { ResearchModel } from "./types";

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

describe("backendRole", () => {
  it("gm → architect, sinon player", () => {
    expect(backendRole("gm")).toBe("architect");
    expect(backendRole("player")).toBe("player");
    expect(backendRole("invent")).toBe("player");
  });
});

describe("buildCreateBody", () => {
  // Le Brouillard et le Réel/escalade sont des drapeaux cochables du Classique.
  const settings = {
    fog: false,
    escalation: false,
    rounds: 8,
    difficulty: "expert" as const,
    free: false,
  };
  const seven = ["china", "usa", "iran", "france", "egypt", "saudi_arabia", "uk"];

  it("joueur classique : mode classic, play_as = drapeau, réglages transmis", () => {
    const body = buildCreateBody({
      scenario: "red_sea",
      baseMode: "classic",
      settings,
      role: "player",
      selected: seven,
      flag: "usa",
      ownerId: "offline_laury",
    });
    expect(body.mode).toBe("classic");
    expect(body.role).toBe("player");
    expect(body.play_as).toBe("usa");
    expect(body.horizon).toBe(8);
    expect(body.difficulty).toBe("expert");
    expect(body.fog).toBe(false);
    expect(body.escalation).toBe(false);
    expect(body.free).toBe(false);
    expect(body.owner_id).toBe("offline_laury");
    expect(body.countries).toEqual(seven);
  });

  it("réglages Brouillard + Crise qui monte : drapeaux composables transmis", () => {
    const body = buildCreateBody({
      scenario: "red_sea",
      baseMode: "classic",
      settings: { ...settings, fog: true, escalation: true },
      role: "gm",
      selected: seven,
    });
    expect(body.role).toBe("architect");
    expect(body.play_as).toBeUndefined();
    expect(body.mode).toBe("classic");
    expect(body.fog).toBe(true);
    expect(body.escalation).toBe(true);
  });

  it("invention : play_as = nom inventé, invent transmis", () => {
    const body = buildCreateBody({
      scenario: "red_sea",
      baseMode: "classic",
      settings,
      role: "invent",
      selected: seven.slice(0, 6),
      invent: { name: "Néo-Atlantis", concept: "cité maritime" },
    });
    expect(body.play_as).toBe("Néo-Atlantis");
    expect(body.invent?.name).toBe("Néo-Atlantis");
    expect(body.mode).toBe("classic");
  });

  it("Campagne : le mode passe tel quel (la sélection de chapitre suit)", () => {
    const body = buildCreateBody({
      scenario: "red_sea",
      baseMode: "campaign",
      settings,
      role: "gm",
      selected: seven,
    });
    expect(body.mode).toBe("campaign");
  });

  it("fige le casting multi-modèle choisi pour une partie classique", () => {
    const body = buildCreateBody({
      scenario: "red_sea",
      baseMode: "classic",
      settings,
      role: "gm",
      selected: seven,
      modelCast: {
        strategy: "balanced",
        models: ["model-a:4b", "model-b:7b"],
        game_master_model: "model-a:4b",
        judge_model: "model-b:7b",
      },
    });
    expect(body.model_cast?.models).toEqual(["model-a:4b", "model-b:7b"]);
    expect(body.model_cast?.judge_model).toBe("model-b:7b");
  });
});

describe("casting des pays (décision design pensée native, 2026-07-19)", () => {
  const model = (tag: string, role: string, installed = true): ResearchModel => ({
    tag,
    family: tag,
    parameter_tier: "test",
    expected_size_gb: 1,
    role,
    source: "test",
    known_digest: "",
    installed,
    local_digest: installed ? `sha-${tag}` : "",
    local_size_bytes: 0,
    modified_at: "",
    benchmark_status: "unmeasured",
    benchmark_wall_time_s: 0,
    benchmark_load_time_s: 0,
    benchmark_warm_run_s: 0,
    benchmark_tokens_per_second: 0,
    benchmark_prompt_version: "",
  });

  it("ne propose pour un pays que les modèles reasoning installés", () => {
    const models = [
      model("deepseek-r1:7b", "reasoning"),
      model("qwen3:4b", "reasoning", false), // pas installé, exclu
      model("mistral:latest", "capacity_comparison"),
      model("llama3.2:3b", "retired"),
    ];
    expect(reasoningCountryModels(models).map((m) => m.tag)).toEqual(["deepseek-r1:7b"]);
  });

  it("préfère deepseek-r1:7b comme casting pays par défaut quand il est installé", () => {
    const eligible = [model("qwen3:4b", "reasoning"), model("deepseek-r1:7b", "reasoning")];
    expect(defaultCountryCastModels(eligible)).toEqual([DEFAULT_COUNTRY_MODEL_TAG]);
  });

  it("retombe sur le premier modèle reasoning disponible si deepseek-r1:7b est absent", () => {
    const eligible = [model("qwen3:4b", "reasoning")];
    expect(defaultCountryCastModels(eligible)).toEqual(["qwen3:4b"]);
  });

  it("rend un casting vide si aucun modèle reasoning n'est disponible", () => {
    expect(defaultCountryCastModels([])).toEqual([]);
  });
});
