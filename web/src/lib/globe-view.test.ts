import { describe, expect, it } from "vitest";

import { INITIAL, type LiveRound } from "@/hooks/useRoundStream";
import { deriveGlobeView, eventGeoOf } from "./globe-view";
import type { StageViewInput } from "./stage-view";
import type { GeoEvent, RoundView } from "./types";

function input(over: Partial<StageViewInput> = {}): StageViewInput {
  return {
    round: INITIAL,
    detail: null,
    viewed: undefined,
    summit: [],
    streaming: false,
    awaitingHuman: false,
    playedRounds: 0,
    persistedU: [],
    showLive: false,
    selected: "live",
    ...over,
  };
}

const event = (over: Partial<GeoEvent> = {}): GeoEvent => ({
  id: "e1",
  round_id: 1,
  event_type: "incident",
  title: "Blocus de Bab el-Mandeb",
  ...over,
});

const turn = (country: string, text: string, done = false) => ({
  country,
  model: "m",
  passNo: 1,
  raw: "",
  text,
  reasoning: "…",
  done,
});

describe("deriveGlobeView — pense vs parle", () => {
  it("tour non terminé SANS texte public → le délégué PENSE (bulle), personne ne parle", () => {
    const round = {
      ...INITIAL,
      status: "streaming",
      turns: [turn("usa", "", false)],
    } as LiveRound;
    const view = deriveGlobeView(input({ round, summit: ["usa", "iran"], streaming: true }));
    expect(view.thinking).toBe("usa");
    expect(view.speaking).toBeNull();
  });

  it("le texte public streame → il PARLE (ambre), la bulle se ferme", () => {
    const round = {
      ...INITIAL,
      status: "streaming",
      turns: [turn("usa", "Nous proposons…", false)],
    } as LiveRound;
    const view = deriveGlobeView(input({ round, summit: ["usa"], streaming: true }));
    expect(view.thinking).toBeNull();
    expect(view.speaking).toBe("usa");
  });

  it("relecture d'un round passé : ni pensée ni pulsation", () => {
    const viewed = {
      event: event({ actors: ["usa", "iran"] }),
      deltas: [],
      judge: {},
      trajectory: { utopia: 0.5 },
    } as unknown as RoundView;
    const view = deriveGlobeView(input({ viewed, summit: ["usa"], selected: 1 }));
    expect(view.thinking).toBeNull();
    expect(view.pulse).toBe(false);
    expect(view.eventGeo).not.toBeNull(); // l'événement relu reste géolocalisable
  });
});

describe("eventGeoOf — géolocalisation", () => {
  it("champs backend (C1) prioritaires", () => {
    const geo = eventGeoOf(event({ geo_lon: 43.3, geo_lat: 12.6, geo_precision: "place" }));
    expect(geo).toEqual({ lon: 43.3, lat: 12.6, precision: "place" });
  });

  it("sans champs backend : repli barycentre des capitales des acteurs", () => {
    const geo = eventGeoOf(event({ actors: ["usa", "iran"] }));
    expect(geo?.precision).toBe("fallback");
    expect(geo!.lon).toBeCloseTo((-77.04 + 51.39) / 2, 1);
    expect(geo!.lat).toBeCloseTo((38.9 + 35.7) / 2, 1);
  });

  it("aucun acteur à capitale connue → null (pays inventé : pas de marqueur)", () => {
    expect(eventGeoOf(event({ actors: ["atlantis"] }))).toBeNull();
    expect(eventGeoOf(undefined)).toBeNull();
  });
});

describe("deriveGlobeView — cohérence avec la scène 2D", () => {
  it("reprend uByCountry/suspendus de deriveStageView et pulse en direct", () => {
    const round = {
      ...INITIAL,
      status: "streaming",
      event: event(),
      trajectory: { utopia: 0.6 },
      suspendedNow: ["iran"],
    } as LiveRound;
    const view = deriveGlobeView(input({ round, summit: ["usa", "iran"], streaming: true }));
    expect(view.uByCountry).toEqual({ usa: 0.6, iran: 0.6 });
    expect(view.suspended).toEqual(["iran"]);
    expect(view.pulse).toBe(true);
    expect(view.arc).toBeNull(); // interface stable, branchée quand le moteur émettra l'adresse
  });
});
