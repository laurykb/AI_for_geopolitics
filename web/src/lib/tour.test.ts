import { describe, expect, it } from "vitest";

import tourSteps from "@/data/tour.json";
import { translate } from "./i18n";
import {
  initialTour,
  isShowable,
  loadTourFlags,
  needsDemo,
  nextIndexWithoutDemo,
  nextStep,
  previousStep,
  resolvePage,
  resumeTour,
  saveDemoId,
  saveTourDone,
  saveTourStep,
  skipTour,
  startTour,
  type TourStep,
} from "./tour";

const step = (page: string, target: string | null = "cible"): TourStep => ({
  page,
  target,
  title: "t",
  text: "x",
});

/** Store en mémoire, même surface que localStorage (tests sans navigateur). */
function fakeStore(): Storage {
  const m = new Map<string, string>();
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

describe("états du tour (proposition, avance, sortie)", () => {
  it("propose la visite quand le flag tour_done est absent", () => {
    expect(initialTour(false)).toEqual({ status: "proposed", index: 0 });
  });

  it("ne re-propose jamais quand le flag est posé", () => {
    expect(initialTour(true)).toEqual({ status: "done", index: 0 });
  });

  it("start ouvre la visite à la première étape", () => {
    expect(startTour()).toEqual({ status: "active", index: 0 });
  });

  it("next avance d'une étape", () => {
    expect(nextStep({ status: "active", index: 0 }, 12)).toEqual({
      status: "active",
      index: 1,
    });
  });

  it("next sur la dernière étape termine la visite", () => {
    expect(nextStep({ status: "active", index: 11 }, 12)).toEqual({
      status: "done",
      index: 12,
    });
  });

  it("next hors visite active ne change rien", () => {
    expect(nextStep({ status: "proposed", index: 0 }, 12)).toEqual({
      status: "proposed",
      index: 0,
    });
  });

  it("retour recule et ignore les jalons silencieux", () => {
    const steps = [step("/a"), { ...step("/b"), silent: true }, step("/c")];
    expect(previousStep({ status: "active", index: 2 }, steps)).toEqual({
      status: "active",
      index: 0,
    });
    expect(previousStep({ status: "active", index: 0 }, steps)).toEqual({
      status: "active",
      index: 0,
    });
  });

  it("skip sort proprement depuis la proposition comme en pleine visite", () => {
    expect(skipTour({ status: "proposed", index: 0 }).status).toBe("done");
    expect(skipTour({ status: "active", index: 7 }).status).toBe("done");
  });

  it("resume reprend à l'étape sauvegardée, bornée aux étapes existantes", () => {
    expect(resumeTour(5, 12)).toEqual({ status: "active", index: 5 });
    expect(resumeTour(null, 12)).toEqual({ status: "active", index: 0 });
    expect(resumeTour(99, 12)).toEqual({ status: "active", index: 11 });
    expect(resumeTour(-3, 12)).toEqual({ status: "active", index: 0 });
  });
});

describe("étapes affichables (cible manquante sautée sans crash)", () => {
  it("une étape sans cible (bulle centrée) est toujours affichable", () => {
    expect(isShowable(step("/accueil", null), () => false)).toBe(true);
  });

  it("une étape ciblée dépend de la présence de [data-tour=…]", () => {
    expect(isShowable(step("/accueil"), () => true)).toBe(true);
    expect(isShowable(step("/accueil"), () => false)).toBe(false);
  });
});

describe("pages de la démo jetable", () => {
  it("résout le jeton {demo} vers l'id de la partie de démonstration", () => {
    expect(resolvePage("/games/{demo}", "abc")).toBe("/games/abc");
    expect(resolvePage("/games/{demo}/marche", "abc")).toBe("/games/abc/marche");
  });

  it("une page sans jeton passe telle quelle, même sans démo", () => {
    expect(resolvePage("/informations", null)).toBe("/informations");
  });

  it("sans partie de démo, une page {demo} est irrésoluble (→ étape sautée)", () => {
    expect(resolvePage("/games/{demo}", null)).toBeNull();
    expect(needsDemo("/games/{demo}")).toBe(true);
    expect(needsDemo("/lobby?etape=mode")).toBe(false);
  });

  it("saute d'un bloc toutes les étapes démo consécutives (API injoignable)", () => {
    const steps = [
      step("/accueil"),
      step("/games/{demo}"),
      step("/games/{demo}/marche"),
      step("/informations"),
    ];
    expect(nextIndexWithoutDemo(steps, 1)).toBe(3);
    expect(nextIndexWithoutDemo(steps, 0)).toBe(0);
    expect(nextIndexWithoutDemo([step("/games/{demo}")], 0)).toBe(1);
  });
});

describe("flags par joueur (localStorage aujourd'hui, profil en G14)", () => {
  it("un joueur vierge n'a ni flag, ni étape, ni démo", () => {
    expect(loadTourFlags("p1", fakeStore())).toEqual({
      done: false,
      step: null,
      demoId: null,
    });
  });

  it("le flag done, l'étape courante et la démo se relisent après écriture", () => {
    const store = fakeStore();
    saveTourDone("p1", store);
    saveTourStep("p1", 4, store);
    saveDemoId("p1", "game-42", store);
    expect(loadTourFlags("p1", store)).toEqual({ done: true, step: 4, demoId: "game-42" });
  });

  it("les flags sont isolés par joueur", () => {
    const store = fakeStore();
    saveTourDone("p1", store);
    expect(loadTourFlags("p2", store).done).toBe(false);
  });

  it("une étape sauvegardée corrompue se lit comme absente", () => {
    const store = fakeStore();
    store.setItem("wosi.tour.p1.step", "pas-un-nombre");
    expect(loadTourFlags("p1", store).step).toBeNull();
  });
});

describe("les étapes de la visite guidée", () => {
  it("chaque titre et texte est traduit (fr et en)", () => {
    for (const s of tourSteps as TourStep[]) {
      for (const lang of ["fr", "en"] as const) {
        for (const key of [s.title, s.text]) {
          const v = translate(lang, key);
          expect(v).not.toBe(key); // la clé existe dans le dictionnaire
        }
      }
    }
  });
});
