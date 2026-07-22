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

  it("chaque phase de la coquille a une intention caméra distincte (transitions animées)", () => {
    // Full immersion : entrer/sortir d'un mode GLISSE la caméra (jamais de coupure nette).
    // Chaque phase a une clé unique -> tout changement de phase (aller ET retour) rejoue un vol.
    expect(phaseDefaults("config").flyTo).toMatchObject({ lon: 38, lat: 24, dist: 3.1 });
    expect(phaseDefaults("connexion").flyTo?.key).toBe("connexion");
    expect(phaseDefaults("hall").flyTo?.key).toBe("hall");
    expect(phaseDefaults("fin").flyTo?.key).toBe("fin");
    // Le théâtre se repeint par SSE (son propre globe) : pas d'intention de vol ici.
    expect(phaseDefaults("theatre").flyTo).toBeUndefined();
    // Les clés sont toutes différentes -> chaque transition déclenche l'animation.
    const keys = ["connexion", "hall", "config", "fin"].map((p) => phaseDefaults(p as never).flyTo?.key);
    expect(new Set(keys).size).toBe(4);
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
