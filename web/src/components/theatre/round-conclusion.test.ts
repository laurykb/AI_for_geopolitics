import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { RoundConclusion } from "./round-conclusion";

describe("conclusion de round", () => {
  it("rend la continuation impossible à manquer", () => {
    const html = renderToStaticMarkup(
      createElement(RoundConclusion, {
        roundNo: 2,
        horizon: 8,
        eventTitle: "Crise test",
        deltas: [],
        busy: false,
        onContinue: () => undefined,
      }),
    );

    expect(html).toContain("Round 2 terminé");
    expect(html).toContain("Continuer la partie");
    expect(html).toContain('data-tour="next-round"');
  });
});
