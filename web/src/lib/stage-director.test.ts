import { describe, expect, it } from "vitest";

import { INITIAL_DIRECTOR, directorReducer, phaseDefaults } from "./stage-director";

describe("stage-director", () => {
  it("part en connexion avec le globe par défaut (pas de picking)", () => {
    expect(INITIAL_DIRECTOR.phase).toBe("connexion");
    expect(INITIAL_DIRECTOR.stage.pickable).toBeUndefined();
    // Les props requises de GlobeStage sont toujours fournies par les défauts.
    expect(INITIAL_DIRECTOR.stage.countries).toBeDefined();
    expect(INITIAL_DIRECTOR.stage.uByCountry).toBeDefined();
    expect(INITIAL_DIRECTOR.stage.utopia).toBe(0.5);
  });

  it("phaseDefaults(config) ouvre le liseré doré du hall", () => {
    expect(phaseDefaults("config").lisere).toBe("#ffc14d");
    expect(phaseDefaults("hall").lisere).toBeUndefined();
  });

  it("goPhase config bascule la phase et applique ses défauts", () => {
    const s = directorReducer(INITIAL_DIRECTOR, { type: "goPhase", phase: "config" });
    expect(s.phase).toBe("config");
    expect(s.stage.lisere).toBe("#ffc14d");
  });

  it("goPhase applique les défauts de phase PUIS l'override", () => {
    const s = directorReducer(INITIAL_DIRECTOR, {
      type: "goPhase",
      phase: "config",
      stage: { countries: ["usa", "china"], chosen: "usa" },
    });
    expect(s.stage.countries).toEqual(["usa", "china"]);
    expect(s.stage.chosen).toBe("usa");
    expect(s.stage.lisere).toBe("#ffc14d"); // défaut de phase conservé
  });

  it("setStage fusionne sans perdre les autres clés", () => {
    const a = directorReducer(INITIAL_DIRECTOR, {
      type: "goPhase",
      phase: "config",
      stage: { countries: ["usa"] },
    });
    const b = directorReducer(a, { type: "setStage", stage: { chosen: "usa" } });
    expect(b.stage.countries).toEqual(["usa"]);
    expect(b.stage.chosen).toBe("usa");
    expect(b.phase).toBe("config");
  });

  it("goPhase repart des défauts (les clés d'une phase précédente ne fuient pas)", () => {
    const cfg = directorReducer(INITIAL_DIRECTOR, {
      type: "goPhase",
      phase: "config",
      stage: { pickable: ["usa", "china"], chosen: "usa" },
    });
    const hall = directorReducer(cfg, { type: "goPhase", phase: "hall" });
    expect(hall.stage.pickable).toBeUndefined();
    expect(hall.stage.chosen).toBeUndefined();
  });
});
