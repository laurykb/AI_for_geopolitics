import { describe, expect, it } from "vitest";

import { revealDetectionSentence, revealWorldSentence } from "./reveal";

/** Faux `t` : renvoie des gabarits reconnaissables (avec placeholders) par clé, pour
 * tester la LOGIQUE de composition (quelle clé + interpolation des nombres), pas la
 * copie finale (livrée par Cowork). */
const fakeT = (key: string): string => {
  const map: Record<string, string> = {
    "reveal.monde.utopie": "Le monde a fini du bon côté.",
    "reveal.monde.dystopie": "Le monde a sombré.",
    "reveal.monde.équilibre": "Le monde a fini en équilibre.",
    "reveal.detection.tous_1": "Tu as démasqué le traître.",
    "reveal.detection.tous_2": "Tu as démasqué les deux traîtres.",
    "reveal.detection.aucun_1": "Le traître a agi dans l'ombre jusqu'au bout.",
    "reveal.detection.aucun_2": "Les traîtres ont agi dans l'ombre jusqu'au bout.",
    "reveal.detection.partiel": "Tu as démasqué {caught} traître sur {deviants}.",
    "reveal.detection.faux_positif_1": "Tu as aussi suspendu un pays loyal.",
    "reveal.detection.faux_positif_n": "Tu as aussi suspendu {n} pays loyaux.",
  };
  return map[key] ?? key;
};

describe("phrase du monde", () => {
  it("suit le verdict", () => {
    expect(revealWorldSentence(fakeT, "utopie")).toBe("Le monde a fini du bon côté.");
    expect(revealWorldSentence(fakeT, "dystopie")).toBe("Le monde a sombré.");
    expect(revealWorldSentence(fakeT, "équilibre")).toBe("Le monde a fini en équilibre.");
  });
});

describe("phrase de détection (le nombre de traîtres était caché)", () => {
  it("un seul traître, démasqué", () => {
    expect(revealDetectionSentence(fakeT, { deviants: 1, caught: 1, falsePositives: 0 })).toBe(
      "Tu as démasqué le traître.",
    );
  });

  it("un seul traître, raté", () => {
    expect(revealDetectionSentence(fakeT, { deviants: 1, caught: 0, falsePositives: 0 })).toBe(
      "Le traître a agi dans l'ombre jusqu'au bout.",
    );
  });

  it("deux traîtres, les deux démasqués", () => {
    expect(revealDetectionSentence(fakeT, { deviants: 2, caught: 2, falsePositives: 0 })).toBe(
      "Tu as démasqué les deux traîtres.",
    );
  });

  it("deux traîtres, un raté : interpole 1 sur 2", () => {
    expect(revealDetectionSentence(fakeT, { deviants: 2, caught: 1, falsePositives: 0 })).toBe(
      "Tu as démasqué 1 traître sur 2.",
    );
  });

  it("deux traîtres, aucun démasqué", () => {
    expect(revealDetectionSentence(fakeT, { deviants: 2, caught: 0, falsePositives: 0 })).toBe(
      "Les traîtres ont agi dans l'ombre jusqu'au bout.",
    );
  });

  it("un faux positif s'ajoute (singulier)", () => {
    expect(revealDetectionSentence(fakeT, { deviants: 1, caught: 1, falsePositives: 1 })).toBe(
      "Tu as démasqué le traître. Tu as aussi suspendu un pays loyal.",
    );
  });

  it("plusieurs faux positifs s'ajoutent (pluriel interpolé)", () => {
    expect(revealDetectionSentence(fakeT, { deviants: 2, caught: 1, falsePositives: 2 })).toBe(
      "Tu as démasqué 1 traître sur 2. Tu as aussi suspendu 2 pays loyaux.",
    );
  });
});
