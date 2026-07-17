/** Tests des décisions pures de la bulle d'aide (`lib/hint.ts`) : ce qui ouvre,
 * ce qui ferme, et la différence survol (volatil) / clic-focus (épinglé). */

import { describe, expect, it } from "vitest";

import { HINT_CLOSED, hintNext, type HintState } from "./hint";

const play = (events: Parameters<typeof hintNext>[1][], from: HintState = HINT_CLOSED) =>
  events.reduce(hintNext, from);

describe("hintNext — ouverture", () => {
  it("le clic ouvre (et épingle : le survol qui s'en va ne referme plus)", () => {
    expect(play(["click"])).toEqual({ open: true, pinned: true });
    expect(play(["click", "unhover"]).open).toBe(true);
  });

  it("le focus clavier ouvre, comme le clic", () => {
    expect(play(["focus"])).toEqual({ open: true, pinned: true });
    expect(play(["focus", "unhover"]).open).toBe(true);
  });

  it("le survol ouvre sans épingler : quitter referme", () => {
    expect(play(["hover"]).open).toBe(true);
    expect(play(["hover"]).pinned).toBe(false);
    expect(play(["hover", "unhover"])).toEqual(HINT_CLOSED);
  });
});

describe("hintNext — fermeture", () => {
  it("Échap referme, même une bulle épinglée", () => {
    expect(play(["click", "escape"])).toEqual(HINT_CLOSED);
    expect(play(["hover", "escape"])).toEqual(HINT_CLOSED);
  });

  it("un clic dehors referme, même une bulle épinglée", () => {
    expect(play(["click", "outside"])).toEqual(HINT_CLOSED);
  });

  it("la perte de focus referme", () => {
    expect(play(["focus", "blur"])).toEqual(HINT_CLOSED);
  });

  it("fermée, les événements de fermeture la laissent fermée", () => {
    expect(play(["escape"])).toEqual(HINT_CLOSED);
    expect(play(["unhover"])).toEqual(HINT_CLOSED);
  });
});
