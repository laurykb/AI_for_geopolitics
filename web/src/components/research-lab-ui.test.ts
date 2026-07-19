import { describe, expect, it } from "vitest";

import {
  effectiveCountryEligibility,
  frontierCandidateModels,
  LAB_STEPS,
  preferredLabProtocol,
} from "./research-lab";
import type { ExperimentProtocol, ResearchModel } from "@/lib/types";

describe("entrée du Laboratoire", () => {
  it("ouvre le tournoi dyadique plutôt que l’ancien premier protocole", () => {
    const protocols = [
      { id: "legacy", execution_mode: "automated" },
      { id: "ai-arms-dyadic-tournament-v1", execution_mode: "automated" },
    ] as ExperimentProtocol[];

    expect(preferredLabProtocol(protocols)?.id).toBe("ai-arms-dyadic-tournament-v1");
  });

  it("restreint le scénario de ressource à Alpha nucléaire et Bêta non nucléaire", () => {
    const protocol = {
      factors: [
        {
          id: "scenario",
          levels: [
            {
              id: "strategic_resource_race",
              value: "strategic_resource_race",
            },
          ],
        },
      ],
      country_eligibility: [
        {
          scenario_id: "strategic_resource_race",
          alpha: { label: "Nucléaire", description: "capacité", countries: ["usa", "china"] },
          beta: { label: "Non nucléaire", description: "sans capacité", countries: ["iran"] },
          pairing_note: "asymétrie",
        },
      ],
    } as ExperimentProtocol;

    const result = effectiveCountryEligibility(protocol, {
      scenario: ["strategic_resource_race"],
    });
    expect(result.alpha.countries).toEqual(["usa", "china"]);
    expect(result.beta.countries).toEqual(["iran"]);
    expect(result.notes).toEqual(["asymétrie"]);
  });

  it("fractionne la préparation, le théâtre et les preuves en cinq écrans mémorisés", () => {
    expect(LAB_STEPS.map((step) => step.id)).toEqual([
      "intro",
      "hypothesis",
      "casting",
      "theatre",
      "results",
    ]);
    expect(new Set(LAB_STEPS.map((step) => step.tour)).size).toBe(LAB_STEPS.length);
  });
});

describe("candidats du Laboratoire (décision design pensée native, 2026-07-19)", () => {
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

  it("ne propose que les rôles reasoning et slow_robustness_only pour une NOUVELLE expérience", () => {
    const models = [
      model("deepseek-r1:7b", "reasoning"),
      model("qwen3:4b", "reasoning"),
      model("gpt-oss:latest", "slow_robustness_only"),
      model("mistral:latest", "capacity_comparison"),
      model("llama3.2:3b", "retired"),
    ];
    expect(frontierCandidateModels(models).map((m) => m.tag)).toEqual([
      "deepseek-r1:7b",
      "qwen3:4b",
      "gpt-oss:latest",
    ]);
  });

  it("garde un modèle frontière non installé dans les candidats (proposé « à installer »)", () => {
    const models = [model("magistral:latest", "slow_robustness_only", false)];
    expect(frontierCandidateModels(models)).toHaveLength(1);
  });

  it("exclut totalement un généraliste retraité, même installé", () => {
    const models = [model("gemma3:4b", "retired", true)];
    expect(frontierCandidateModels(models)).toHaveLength(0);
  });
});
