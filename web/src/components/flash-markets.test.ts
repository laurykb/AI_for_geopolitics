import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { FlashMarketsPopup } from "@/components/flash-markets";
import { SettingsProvider } from "@/components/settings-provider";
import type { FlashMarket } from "@/lib/market";

const market: FlashMarket = {
  id: "market-1",
  question: "La motion sera-t-elle retenue ?",
  predicate: "motion_upheld",
  status: "open",
  outcomes: [
    { id: "yes", label: "YES", price: 0.62 },
    { id: "no", label: "NO", price: 0.38 },
  ],
};

describe("paris éclair", () => {
  it("demande une sélection puis une validation explicite", () => {
    const html = renderToStaticMarkup(
      createElement(
        SettingsProvider,
        null,
        createElement(FlashMarketsPopup, { markets: [market], onBet: () => undefined }),
      ),
    );

    expect(html).toContain("Choisis une issue, puis valide ton pari.");
    expect(html).toContain("Valider le pari");
    expect(html).toContain('aria-pressed="false"');
    expect(html).toMatch(/<button[^>]*disabled=""[^>]*>Valider le pari<\/button>/);
  });

  it("borne la fenêtre et permet de faire défiler plusieurs marchés", () => {
    const html = renderToStaticMarkup(
      createElement(
        SettingsProvider,
        null,
        createElement(FlashMarketsPopup, { markets: [market], onBet: () => undefined }),
      ),
    );

    expect(html).toContain("max-h-[calc(100%-1.5rem)]");
    expect(html).toContain("overflow-y-auto");
    expect(html).toContain("inset-x-3");
  });
});

