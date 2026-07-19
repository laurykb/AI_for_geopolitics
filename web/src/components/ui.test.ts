/** Tests de structure du kit UI (rendu statique, sans DOM — convention du repo) :
 * la bulle d'aide expose son contrat ARIA — bouton et tooltip câblés par
 * `aria-describedby`, état d'ouverture exposé par `aria-expanded`. */

import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { Banner, Hint } from "@/components/ui";

describe("Hint — bulle d'aide cliquable", () => {
  it("fermée : un vrai bouton + une bulle masquée, reliés par aria-describedby", () => {
    const html = renderToStaticMarkup(createElement(Hint, { text: "aide contextuelle" }));
    expect(html).toContain('type="button"');
    expect(html).toContain('aria-expanded="false"');
    expect(html).toContain('role="tooltip"');
    expect(html).toContain('hidden=""'); // bulle présente mais masquée
    expect(html).toContain("aide contextuelle");
    const describedby = html.match(/aria-describedby="([^"]+)"/)?.[1];
    expect(describedby).toBeTruthy();
    expect(html).toContain(`id="${describedby}"`); // la bulle porte bien l'id référencé
  });

  it("ouverte (defaultOpen) : la bulle est visible et l'état exposé", () => {
    const html = renderToStaticMarkup(
      createElement(Hint, { text: "aide", defaultOpen: true }),
    );
    expect(html).toContain('aria-expanded="true"');
    expect(html).not.toContain('hidden=""');
  });

  it("ne repose plus sur l'infobulle native `title` (morte au tactile)", () => {
    const html = renderToStaticMarkup(createElement(Hint, { text: "aide" }));
    expect(html).not.toContain('title="');
  });
});

describe("Banner — bordure et liseré par ton (TONE_BORDER)", () => {
  const render = (tone?: "good" | "warn" | "bad" | "neutral") =>
    renderToStaticMarkup(
      createElement(Banner, { tone } as Parameters<typeof Banner>[0], "message"),
    );

  it("chaque ton colore la bordure ET le liseré gauche assortis", () => {
    for (const tone of ["good", "warn", "bad"] as const) {
      const html = render(tone);
      expect(html).toContain(`border-${tone}/40`);
      expect(html).toContain(`border-l-${tone}`);
    }
  });

  it("le ton neutre garde la bordure discrète et le liseré indigo", () => {
    const html = render("neutral");
    expect(html).toContain("border-edge-strong");
    expect(html).toContain("border-l-indigo-soft");
  });

  it("sans ton : avertissement par défaut (comportement historique)", () => {
    const html = render();
    expect(html).toContain("border-warn/40");
    expect(html).toContain("border-l-warn");
  });
});
