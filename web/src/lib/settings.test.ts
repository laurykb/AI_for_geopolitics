import { describe, expect, it } from "vitest";

import {
  DEFAULT_SETTINGS,
  loadSettings,
  perfClass,
  saveSettings,
} from "./settings";

/** Store en mémoire, même surface que localStorage (tests sans navigateur). */
function fakeStore(seed: Record<string, string> = {}): Storage {
  const m = new Map<string, string>(Object.entries(seed));
  return {
    getItem: (k: string) => m.get(k) ?? null,
    setItem: (k: string, v: string) => void m.set(k, v),
    removeItem: (k: string) => void m.delete(k),
    clear: () => m.clear(),
    key: () => null,
    get length() {
      return m.size;
    },
  } as Storage;
}

describe("mapping perf → classe sur <html>", () => {
  it("plein n'ajoute aucune classe", () => {
    expect(perfClass("plein", false)).toBe("");
  });

  it("confort et léger posent leur classe", () => {
    expect(perfClass("confort", false)).toBe("perf-confort");
    expect(perfClass("leger", false)).toBe("perf-leger");
  });

  it("prefers-reduced-motion impose au minimum confort", () => {
    expect(perfClass("plein", true)).toBe("perf-confort");
    expect(perfClass("confort", true)).toBe("perf-confort");
    expect(perfClass("leger", true)).toBe("perf-leger"); // léger reste léger
  });
});

describe("persistance des réglages (localStorage aujourd'hui, profil en CC-3)", () => {
  it("sans rien en stock, les défauts sortent (fr, plein, animations on)", () => {
    expect(loadSettings(fakeStore())).toEqual(DEFAULT_SETTINGS);
  });

  it("relit ce qui a été sauvé", () => {
    const store = fakeStore();
    saveSettings(
      { lang: "en", perf: "leger", noAnim: true, stageView: "2d", planetQuality: "light" },
      store,
    );
    expect(loadSettings(store)).toEqual({
      lang: "en",
      perf: "leger",
      noAnim: true,
      stageView: "2d",
      planetQuality: "light",
    });
  });

  it("une valeur corrompue retombe sur le défaut", () => {
    const store = fakeStore({ "wosi.lang": "klingon", "wosi.perf": "turbo", "wosi.stage": "4d" });
    expect(loadSettings(store)).toEqual(DEFAULT_SETTINGS);
  });

  it("la vue du théâtre : « 3d » par défaut, un choix persisté par appareil (spec §5)", () => {
    expect(loadSettings(fakeStore()).stageView).toBe("3d");
    expect(loadSettings(fakeStore({ "wosi.stage": "2d" })).stageView).toBe("2d");
  });

  it("la qualité de la planète : « realistic » par défaut, un choix persisté (spec A7)", () => {
    expect(DEFAULT_SETTINGS.planetQuality).toBe("realistic");
    expect(loadSettings(fakeStore()).planetQuality).toBe("realistic");
    expect(loadSettings(fakeStore({ "wosi.planet": "light" })).planetQuality).toBe("light");
  });
});
