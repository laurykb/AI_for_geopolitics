import { describe, expect, it } from "vitest";

import { parseScenarioPlan } from "./scenario-planning";

describe("parseScenarioPlan", () => {
  it("extrait les branches, les réactions anticipées et le choix", () => {
    const plan = parseScenarioPlan(
      [
        "FUTUR 1 | option: compromis | réponses prévues: iran=accepte; france=soutient | issue: accord | utilité: 78 | confiance: 64",
        "FUTUR 2 | option: menace | réponses prévues: iran=résiste | issue: escalade | utilité: 35 | confiance: 52",
        "CHOIX | FUTUR 1 | motif: meilleur rapport gain-risque",
        "INCERTITUDE | la réaction iranienne reste ambiguë",
      ].join("\n"),
    );
    expect(plan?.branches).toHaveLength(2);
    expect(plan?.branches[0].responses).toContain("iran=accepte");
    expect(plan?.branches[0].utility).toBe(78);
    expect(plan?.selected).toBe(1);
    expect(plan?.selectionReason).toContain("gain-risque");
  });

  it("reste tolérant avec une réflexion historique non structurée", () => {
    expect(parseScenarioPlan("Je privilégie un accord.")).toBeNull();
  });
});
