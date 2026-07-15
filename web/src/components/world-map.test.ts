/** Tests de la carte du monde (rendu statique, sans DOM) : chaque pays du sommet
 * est teinté par SON indice U local — l'échelle fixe de la scène (`uTint`), comme
 * le promettent la visite guidée (tour.7) et le tutoriel (tuto.2). */

import { createElement, type ComponentProps } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { SettingsProvider } from "@/components/settings-provider";
import { WorldMap } from "@/components/world-map";
import { uTint } from "@/lib/stage";

// La carte est i18n (CC-15b) : le rendu statique passe par le provider (langue FR).
function render(props: ComponentProps<typeof WorldMap>): string {
  return renderToStaticMarkup(
    createElement(SettingsProvider, null, createElement(WorldMap, props)),
  );
}

describe("WorldMap — teintes locales", () => {
  it("teinte chaque pays du sommet par son U local, pas par la couleur globale", () => {
    const html = render({
      countries: ["usa", "iran"],
      utopia: 0.5,
      uByCountry: { usa: 0.8, iran: 0.2 },
    });
    expect(uTint(0.8)).not.toBe(uTint(0.2)); // deux paliers bien distincts
    expect(html).toContain(`fill="${uTint(0.8)}"`);
    expect(html).toContain(`fill="${uTint(0.2)}"`);
  });

  it("sans valeur locale, un pays du sommet retombe sur l'indice global", () => {
    const html = render({ countries: ["france"], utopia: 0.72 });
    expect(html).toContain(`fill="${uTint(0.72)}"`);
  });
});
