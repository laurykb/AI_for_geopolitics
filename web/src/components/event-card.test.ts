/** Tests de la carte d'événement (rendu statique, sans DOM) : un type inconnu
 * affiche « événement », jamais le slug technique brut. */

import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { EventCard } from "@/components/event-card";
import { SettingsProvider } from "@/components/settings-provider";
import type { GeoEvent } from "@/lib/types";

function render(event: GeoEvent): string {
  return renderToStaticMarkup(
    createElement(SettingsProvider, null, createElement(EventCard, { event })),
  );
}

const base = (event_type: string): GeoEvent => ({
  id: "e1",
  round_id: 1,
  event_type,
  title: "Sommet sous tension",
});

describe("EventCard — libellé du type d'événement", () => {
  it("un type inconnu affiche « événement », pas le slug brut", () => {
    const html = render(base("cyber_flashpoint_v2"));
    expect(html).not.toContain("cyber_flashpoint_v2");
    expect(html).toContain("événement");
  });

  it("les types connus gardent leur libellé dédié", () => {
    expect(render(base("human"))).toContain("décrété par l&#x27;humain");
    expect(render(base("motion"))).toContain("motion de suspension");
  });
});
