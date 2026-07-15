/** CC-15c — la table des pays fusionnée (« Ta position » + « État des pays ») :
 * vue réduite par défaut (pays + posture + tendance), 5 colonnes au clic (ou
 * d'office via defaultDetailed — densité Expert), ta ligne en avant. Rendu
 * statique sans DOM, convention du repo. */

import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { CountryTable, type CountrySnapshot } from "@/components/country-table";

const world: Record<string, CountrySnapshot> = {
  usa: { economy: { growth: 2.1 }, political_stability: 0.8, technology_level: 0.9 },
  iran: { economy: { growth: 1.2 }, political_stability: 0.5, technology_level: 0.6 },
};

const history = {
  usa: { croissance: [1.8, 1.9, 2.0, 2.1], stabilité: [0.7, 0.74, 0.78, 0.8] },
  iran: { croissance: [1.6, 1.5, 1.3, 1.2], stabilité: [0.6, 0.56, 0.52, 0.5] },
};

describe("CountryTable — vue réduite par défaut", () => {
  it("montre pays + tendance, pas les 5 colonnes de chiffres", () => {
    const html = renderToStaticMarkup(
      createElement(CountryTable, { worldCountries: world, history }),
    );
    expect(html).toContain("Tendance");
    expect(html).not.toContain("Croissance");
    expect(html).not.toContain("Puissance de calcul");
  });

  it("la tendance se lit en mots (hausse / baisse)", () => {
    const html = renderToStaticMarkup(
      createElement(CountryTable, { worldCountries: world, history }),
    );
    expect(html).toContain("en hausse");
    expect(html).toContain("en baisse");
  });

  it("propose le passage au détail", () => {
    const html = renderToStaticMarkup(
      createElement(CountryTable, { worldCountries: world, history }),
    );
    expect(html).toContain("Voir les 5 colonnes");
  });
});

describe("CountryTable — densité Expert (defaultDetailed)", () => {
  it("affiche les 5 colonnes d'office", () => {
    const html = renderToStaticMarkup(
      createElement(CountryTable, { worldCountries: world, history, defaultDetailed: true }),
    );
    expect(html).toContain("Croissance");
    expect(html).toContain("Stabilité");
    expect(html).toContain("Puissance de calcul");
    expect(html).not.toContain("Voir les 5 colonnes"); // le bouton propose la vue simple
  });
});

describe("CountryTable — ta ligne en avant (fusion « Ta position »)", () => {
  it("le pays joué passe en tête et porte la pastille « toi »", () => {
    const html = renderToStaticMarkup(
      createElement(CountryTable, { worldCountries: world, history, playAs: "usa" }),
    );
    expect(html).toContain("toi");
    expect(html.indexOf("États-Unis")).toBeLessThan(html.indexOf("Iran"));
  });

  it("sans pays joué : ordre alphabétique, pas de pastille", () => {
    const html = renderToStaticMarkup(
      createElement(CountryTable, { worldCountries: world, history }),
    );
    expect(html).not.toContain(">toi<");
    expect(html.indexOf("Iran")).toBeLessThan(html.indexOf("États-Unis"));
  });
});
