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
});
