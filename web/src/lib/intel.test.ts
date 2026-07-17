/** G23 — la vue de l'analyse psycholinguistique porte TOUJOURS le caveat. */

import { describe, expect, it } from "vitest";

import { translate } from "./i18n";
import { alertLabel, buildAnalysisView } from "./intel";
import type { IntelAnalysis } from "./types";

const t = (key: string) => key; // identité : on vérifie les clés, pas la langue
const label = (id: string) => `#${id}`;

const BASE: IntelAnalysis = {
  target: "iran",
  rounds: [2, 3, 4],
  gauges: { sentiment: 0.4, politeness: 0.5, future: 0.2, sentences: 9 },
  previous: { sentiment: 0.9, politeness: 0.6, future: 0.3, sentences: 9 },
  alerts: [
    { towards: "france", gauge: "sentiment", drop: 0.5 },
    { towards: "france", gauge: "politeness", drop: 0.3 },
    { towards: null, gauge: "sentiment", drop: 0.4 },
  ],
};

describe("buildAnalysisView (G23)", () => {
  it("porte TOUJOURS le caveat — un indice, pas une preuve", () => {
    const withAlerts = buildAnalysisView(BASE, t, label);
    expect(withAlerts.caveat).toBe("intel.analyse.caveat");

    const calm = buildAnalysisView({ ...BASE, previous: null, alerts: [] }, t, label);
    expect(calm.caveat).toBe("intel.analyse.caveat"); // même sans alerte ni comparaison
  });

  it("le caveat réel mentionne la précision historique (~57 %) en fr ET en", () => {
    const fr = translate("fr", "intel.analyse.caveat");
    const en = translate("en", "intel.analyse.caveat");
    expect(fr).toContain("57");
    expect(fr).toContain("indice");
    expect(en).toContain("57");
    expect(en.toLowerCase()).toContain("clue");
  });

  it("trois lignes de jauges, bornées, avec l'écart vs fenêtre précédente", () => {
    const view = buildAnalysisView(BASE, t, label);
    expect(view.rows.map((r) => r.gauge)).toEqual(["sentiment", "politeness", "future"]);
    expect(view.rows[0].value).toBeCloseTo(0.4);
    expect(view.rows[0].delta).toBeCloseTo(-0.5);
    for (const row of view.rows) {
      expect(row.value).toBeGreaterThanOrEqual(0);
      expect(row.value).toBeLessThanOrEqual(1);
    }
  });

  it("début de partie : pas de fenêtre précédente → delta null", () => {
    const view = buildAnalysisView({ ...BASE, previous: null, alerts: [] }, t, label);
    expect(view.rows.every((r) => r.delta === null)).toBe(true);
    expect(view.alerts).toEqual([]);
  });

  it("déduplique les alertes par cible et nomme le pays", () => {
    const view = buildAnalysisView(BASE, t, label);
    expect(view.alerts).toEqual([
      "intel.analyse.alerte #france",
      "intel.analyse.alerte-generale",
    ]);
  });

  it("les libellés d'alerte existent en fr ET en", () => {
    const towards = { towards: "france", gauge: "sentiment" as const, drop: 0.5 };
    const general = { towards: null, gauge: "sentiment" as const, drop: 0.5 };
    for (const lang of ["fr", "en"] as const) {
      const tr = (key: string) => translate(lang, key);
      expect(alertLabel(towards, tr, label)).toContain("#france");
      expect(alertLabel(towards, tr, label)).not.toContain("intel.analyse");
      expect(alertLabel(general, tr, label)).not.toContain("intel.analyse");
    }
  });
});
