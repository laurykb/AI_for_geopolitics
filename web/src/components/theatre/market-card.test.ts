import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { MarketCard } from "@/components/theatre/market-card";
import type { MarketView } from "@/lib/types";

const market: MarketView = {
  id: "m1",
  round_id: 1,
  game_id: "g",
  question: "Une trahison sera-t-elle démasquée ?",
  type: "binary",
  status: "open",
  b: 100,
  resolved_outcome: null,
  outcomes: [
    { id: "yes", label: "YES", q: 0, price: 0.31 },
    { id: "no", label: "NO", q: 0, price: 0.69 },
  ],
  volume: 60,
  target: { type: "summit", slug: null },
};

describe("MarketCard", () => {
  it("montre la question, la barre de cote OUI, le pot et une mise EXPLICITE par issue", () => {
    const html = renderToStaticMarkup(
      createElement(MarketCard, {
        market,
        busy: false,
        onBet: () => undefined,
        enjeuLabel: "en jeu",
      }),
    );
    expect(html).toContain("Une trahison sera-t-elle démasquée ?");
    expect(html).toContain("OUI 31%"); // barre de cote (label)
    expect(html).toContain("width:31%"); // fill proportionnel au prix YES
    expect(html).toContain("💰 60 ₲ en jeu"); // pot du marché
    expect(html).toContain("Miser 10 ₲ · YES");
    expect(html).toContain("Miser 10 ₲ · NO");
  });

  it("busy désactive les boutons de mise", () => {
    const html = renderToStaticMarkup(
      createElement(MarketCard, { market, busy: true, onBet: () => undefined, enjeuLabel: "x" }),
    );
    expect(html).toMatch(/<button[^>]*disabled=""/);
  });

  it("un marché fermé désactive les mises", () => {
    const closed: MarketView = { ...market, status: "resolved" };
    const html = renderToStaticMarkup(
      createElement(MarketCard, { market: closed, busy: false, onBet: () => undefined, enjeuLabel: "x" }),
    );
    expect(html).toMatch(/<button[^>]*disabled=""/);
  });
});
