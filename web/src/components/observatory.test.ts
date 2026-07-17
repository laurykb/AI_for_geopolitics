/** CC-15c — la salle des observables à onglets (rendu statique, convention du repo) :
 * un TabGroup montre UN contenu à la fois, saute les onglets vides, disparaît sans
 * contenu (sauf état vide fourni), et masque la barre d'onglets quand il n'y en a
 * qu'un — le budget de surface du PRINCIPE_SIMPLICITE en composant. */

import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { TabGroup } from "@/components/observatory";

const tab = (key: string, label: string, content: React.ReactNode) => ({
  key,
  label,
  content,
});

describe("TabGroup — un panneau, des onglets", () => {
  it("affiche le premier onglet disponible, pas les autres contenus", () => {
    const html = renderToStaticMarkup(
      createElement(TabGroup, {
        label: "Renseignement",
        tabs: [
          tab("a", "Onglet A", createElement("p", null, "contenu A")),
          tab("b", "Onglet B", createElement("p", null, "contenu B")),
        ],
      }),
    );
    expect(html).toContain("contenu A");
    expect(html).not.toContain("contenu B");
    expect(html).toContain('role="tablist"');
    expect(html).toContain('aria-selected="true"');
  });

  it("saute les onglets sans contenu (null)", () => {
    const html = renderToStaticMarkup(
      createElement(TabGroup, {
        label: "Le monde",
        tabs: [
          tab("a", "Onglet A", null),
          tab("b", "Onglet B", createElement("p", null, "contenu B")),
        ],
      }),
    );
    expect(html).not.toContain("Onglet A");
    expect(html).toContain("contenu B");
  });

  it("un seul onglet : pas de barre d'onglets, juste le contenu", () => {
    const html = renderToStaticMarkup(
      createElement(TabGroup, {
        label: "La table",
        tabs: [tab("a", "Onglet A", createElement("p", null, "seul contenu"))],
      }),
    );
    expect(html).toContain("seul contenu");
    expect(html).not.toContain('role="tablist"');
  });

  it("aucun contenu : le groupe disparaît", () => {
    const html = renderToStaticMarkup(
      createElement(TabGroup, {
        label: "Renseignement",
        tabs: [tab("a", "Onglet A", null)],
      }),
    );
    expect(html).toBe("");
  });

  it("aucun contenu mais état vide fourni : le groupe reste (ancre de visite)", () => {
    const html = renderToStaticMarkup(
      createElement(TabGroup, {
        label: "Renseignement",
        dataTour: "renseignement",
        tabs: [tab("a", "Onglet A", null)],
        empty: createElement("p", null, "les jauges se remplissent en jouant"),
      }),
    );
    expect(html).toContain("les jauges se remplissent en jouant");
    expect(html).toContain('data-tour="renseignement"');
  });
});
