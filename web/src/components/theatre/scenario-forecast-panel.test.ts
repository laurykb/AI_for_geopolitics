import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { ScenarioForecastPanel } from "./scenario-forecast-panel";

describe("ScenarioForecastPanel", () => {
  it("rend la calibration prévu-observé et les prévisions en attente", () => {
    const html = renderToStaticMarkup(
      createElement(ScenarioForecastPanel, {
        world: {
          scenario_forecast_metrics: {
            usa: { evaluated: 4, exact: 3, pending: 1, exact_rate: 0.75 },
          },
          scenario_forecasts: [
            {
              round_no: 2,
              source: "usa",
              target: "iran",
              predicted_response: "resiste",
              observed_response: "resiste",
              exact: true,
            },
          ],
        },
      }),
    );
    expect(html).toContain("Prévisions croisées");
    expect(html).toContain("75 %");
    expect(html).toContain("Iran");
    expect(html).toContain("1 attente");
  });

  it("explique la mécanique avant la première prévision", () => {
    const html = renderToStaticMarkup(
      createElement(ScenarioForecastPanel, { world: {} }),
    );
    expect(html).toContain('data-tour="scenario-forecasts"');
    expect(html).toContain("leurs prévisions apparaîtront ici");
  });

  it("exclut le pays inventé (créé, non incarné) des prévisions croisées", () => {
    // Point 7 : un pays inventé n'a jamais anticipé personne (neuf, sans historique) —
    // ni sa ligne de calibration, ni ses prévisions comme émetteur ne doivent apparaître.
    const world = {
      scenario_forecast_metrics: {
        usa: { evaluated: 2, exact: 1, pending: 0, exact_rate: 0.5 },
        atlantis: { evaluated: 3, exact: 3, pending: 0, exact_rate: 1 },
      },
      scenario_forecasts: [
        {
          round_no: 1,
          source: "atlantis",
          target: "usa",
          predicted_response: "resiste",
          observed_response: null,
          exact: null,
        },
      ],
    };
    const html = renderToStaticMarkup(
      createElement(ScenarioForecastPanel, { world, createdCountry: "atlantis" }),
    );
    expect(html).not.toContain("Atlantis");
    // Seul usa reste : 2 réponses observées (les 3 d'atlantis, exclu, ne comptent plus).
    expect(html).toContain("2 réponses observées");
  });
});
