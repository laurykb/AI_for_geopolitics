/** Le verrou « lexique banni » (CC-15b) — la passe de vocabulaire ne doit jamais
 * régresser. Trois gardes :
 *
 * 1. les dictionnaires fr/en ne contiennent aucun terme banni par l'audit de
 *    simplicité (`docs/AUDIT_SIMPLICITE.md`, règle « jouable de 12 à 65 ans ») ;
 * 2. les sources front (hors commentaires) n'affichent plus les libellés bannis ;
 * 3. parité i18n : toute clé française existe en anglais, et inversement.
 *
 * Les commentaires de code peuvent garder le jargon (ce sont des notes de dev) :
 * on les retire avant de scanner. Les slugs backend (« corroboré » comparé à une
 * valeur d'API) restent légitimes en code — ils ne sont bannis que des dictionnaires.
 */

import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import en from "./en.json";
import fr from "./fr.json";

/** Termes interdits dans les VALEURS du dictionnaire français. */
const BANNED_FR_DICT = [
  "Leaderboard",
  "scrubber",
  "UTC",
  "LMSR",
  "purgé",
  "P&L",
  "ΔU",
  "Real World",
  "turfiste",
  "uchronie",
  "forfait",
  "corroboré",
  "psycholinguistique",
  "duplicité",
  "agentivité",
  "Fog Engine",
  "Escalation Ladder",
  "Crisis Replay",
  // RG-1 — les LP / la ligue / le cadrage « classé » sont retirés du jeu.
  "points de ligue",
  "ligue",
];

/** Termes interdits dans les VALEURS du dictionnaire anglais. */
const BANNED_EN_DICT = [
  "ΔU",
  "scrubber",
  "UTC",
  "LMSR",
  "purged",
  "Real World",
  "league point", // RG-1 — les LP sont retirés
];

/** Les sigles « SI »/« SIs » nus (les IA) — bannis des dictionnaires (décision : « IA »).
 * En regex bornée : « crisis » ou « SIPRI » ne comptent pas. */
const BARE_SI = /\bSIs?\b/;

/** Le sigle « LP » nu (points de ligue) — banni des dictionnaires ET des sources visibles.
 * RG-1 a retiré les LP / la ligue du jeu ; la borne de mot évite « help », « alpha »… */
const BARE_LP = /\bLP\b/;

/** Termes interdits dans les sources front, commentaires retirés. */
const BANNED_SOURCES = [
  "turfiste",
  "uchronie",
  "flagrance",
  "éligibles",
  "scrubber",
  "token par token",
  "fog engine",
  "escalation ladder",
  "crisis replay",
  "real world",
  "défaite forfaitaire",
  "acteur flou",
  "world of super",
  "désinformé",
  "psycholinguistique",
  "gm humain",
  "gm automatique",
];

/** Retire les commentaires (/* … *\/, // …, {/* … *\/}) — le jargon y reste permis. */
function stripComments(source: string): string {
  return source
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/^\s*\/\/.*$/gm, "")
    .replace(/(?<=\s)\/\/ .*$/gm, "");
}

/** Tous les fichiers .ts/.tsx de src, hors tests (qui citent le lexique banni). */
function sourceFiles(): string[] {
  const root = join(__dirname, "..");
  return readdirSync(root, { recursive: true, encoding: "utf8" })
    .filter((f) => /\.(ts|tsx)$/.test(f) && !/\.test\.tsx?$/.test(f))
    .map((f) => join(root, f));
}

describe("lexique banni — dictionnaires", () => {
  it("le français ne contient aucun terme banni", () => {
    const offenders: string[] = [];
    for (const [key, value] of Object.entries(fr as Record<string, string>)) {
      for (const term of BANNED_FR_DICT) {
        if (value.toLowerCase().includes(term.toLowerCase())) {
          offenders.push(`fr:${key} contient « ${term} »`);
        }
      }
      if (BARE_SI.test(value)) offenders.push(`fr:${key} contient le sigle nu « SI »`);
      if (BARE_LP.test(value)) offenders.push(`fr:${key} contient le sigle nu « LP »`);
    }
    expect(offenders).toEqual([]);
  });

  it("l'anglais ne contient aucun terme banni", () => {
    const offenders: string[] = [];
    for (const [key, value] of Object.entries(en as Record<string, string>)) {
      for (const term of BANNED_EN_DICT) {
        if (value.toLowerCase().includes(term.toLowerCase())) {
          offenders.push(`en:${key} contient « ${term} »`);
        }
      }
      if (BARE_SI.test(value)) offenders.push(`en:${key} contient le sigle nu « SI »`);
      if (BARE_LP.test(value)) offenders.push(`en:${key} contient le sigle nu « LP »`);
    }
    expect(offenders).toEqual([]);
  });
});

describe("lexique banni — sources front (hors commentaires)", () => {
  it("aucun libellé banni ne survit dans les .ts/.tsx", () => {
    const offenders: string[] = [];
    for (const file of sourceFiles()) {
      const stripped = stripComments(readFileSync(file, "utf8"));
      const clean = stripped.toLowerCase();
      for (const term of BANNED_SOURCES) {
        if (clean.includes(term)) offenders.push(`${file} contient « ${term} »`);
      }
      // Le sigle « SI » nu affiché à l'écran (hors commentaires, qui gardent le jargon) —
      // on teste la casse d'origine : « si » minuscule est légitime en français.
      if (BARE_SI.test(stripped)) offenders.push(`${file} affiche le sigle nu « SI » (→ « IA »)`);
    }
    expect(offenders).toEqual([]);
  });
});

describe("parité i18n", () => {
  it("toute clé française existe en anglais, et inversement", () => {
    const frKeys = Object.keys(fr).sort();
    const enKeys = Object.keys(en).sort();
    expect(enKeys).toEqual(frKeys);
  });
});
