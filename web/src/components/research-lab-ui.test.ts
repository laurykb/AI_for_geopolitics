import { describe, expect, it } from "vitest";

import { effectiveCountryEligibility, LAB_STEPS, preferredLabProtocol } from "./research-lab";
import type { ExperimentProtocol } from "@/lib/types";

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
