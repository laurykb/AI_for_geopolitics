import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { SettingsProvider } from "@/components/settings-provider";
import { MotionVoteForm } from "@/components/theatre/motion-vote-form";

describe("bulletin humain de motion", () => {
  it("propose les trois choix et exige une validation explicite", () => {
    const html = renderToStaticMarkup(
      createElement(
        SettingsProvider,
        null,
        createElement(MotionVoteForm, {
          country: "france",
          target: "iran",
          deadlineTs: Date.now() / 1000 + 60,
          onSubmit: async () => undefined,
        }),
      ),
    );

    expect(html).toContain("Faut-il suspendre Iran du prochain round ?");
    expect(html).toContain("Pour la suspension");
    expect(html).toContain("Contre la suspension");
    expect(html).toContain("Abstention");
    expect(html).toContain("Valider mon vote");
    expect(html).toMatch(/<button[^>]*disabled=""[^>]*>Valider mon vote<\/button>/);
  });
});
