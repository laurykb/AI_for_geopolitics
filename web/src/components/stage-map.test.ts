/** StageMap — le repli SVG sans WebGL (runbook S3) : depuis la décision
 * full-three, la carte plate du théâtre est le globe déplié ; la StageMap ne
 * sert plus qu'en secours, mais elle doit rester INTERACTIVE — pays cliquables
 * (fiche) et marqueur d'événement géolocalisé. Rendu statique : on vérifie le
 * balisage (curseur, rôle, marqueur), pas les handlers. */

import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { SettingsProvider } from "./settings-provider";
import { StageMap, type StageMapProps } from "./stage-map";

function render(props: Partial<StageMapProps>) {
  return renderToStaticMarkup(
    createElement(
      SettingsProvider,
      null,
      createElement(StageMap, {
        countries: ["france", "iran"],
        uByCountry: { france: 0.61, iran: 0.41 },
        utopia: 0.52,
        ...props,
      }),
    ),
  );
}

describe("StageMap interactive (repli sans WebGL)", () => {
  it("sans onCountryClick, les pays ne réclament pas le clic", () => {
    const html = render({});
    expect(html).not.toContain("stage-country-clickable");
  });

  it("avec onCountryClick, les pays du sommet deviennent cliquables", () => {
    const html = render({ onCountryClick: () => undefined });
    expect(html).toContain("stage-country-clickable");
  });

  it("le marqueur d'événement géolocalisé se pose au lieu de crise", () => {
    const html = render({
      eventGeo: { lon: 56.5, lat: 26.6 },
      eventTitle: "Incident naval dans le détroit d'Ormuz",
    });
    expect(html).toContain("stage-event-geo");
    expect(html).toContain("lieu de la crise");
  });

  it("sans eventGeo, aucun marqueur", () => {
    const html = render({});
    expect(html).not.toContain("stage-event-geo");
  });
});
