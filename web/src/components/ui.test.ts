/** Tests de structure du kit UI (rendu statique, sans DOM — convention du repo) :
 * la bulle d'aide expose son contrat ARIA — bouton et tooltip câblés par
 * `aria-describedby`, état d'ouverture exposé par `aria-expanded`. */

import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { Hint } from "@/components/ui";

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
