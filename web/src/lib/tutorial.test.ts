import { describe, expect, it } from "vitest";

import steps from "@/data/tutorial.json";
import { needsDemo, type TourStep } from "./tour";

/** Les jalons que le théâtre pose en attributs data-tutorial (aucune logique en dur
 * dans la page — même philosophie que data-tour). */
const MARKERS = ["round-done", "motion-filed", "vote-seen"];

type TutorialStep = TourStep & { advanceOn?: string | null };

describe("les étapes du tutoriel (chapitre 0)", () => {
  const all = steps as TutorialStep[];

  it("vit entièrement dans la partie de démonstration du chapitre", () => {
    expect(all.length).toBeGreaterThanOrEqual(6);
    for (const s of all) expect(needsDemo(s.page)).toBe(true);
  });

  it("chaque étape est complète, ses actions attendues sont des jalons connus", () => {
    for (const s of all) {
      expect(s.title.length).toBeGreaterThan(0);
      expect(s.text.length).toBeGreaterThan(0);
      if (s.advanceOn != null) expect(MARKERS).toContain(s.advanceOn);
    }
  });

  it("les textes sont des placeholders clairs en attendant Cowork", () => {
    for (const s of all) expect(s.text).toContain("TODO_COWORK");
  });

  it("le parcours couvre le verrou du chapitre : round joué, motion, vote", () => {
    const actions = all.map((s) => s.advanceOn).filter(Boolean);
    expect(actions).toEqual(["round-done", "motion-filed", "vote-seen"]);
  });
});
