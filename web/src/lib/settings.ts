/** Réglages utilisateur (G14 §1-2) — logique pure, testable sans navigateur.
 *
 * Un seul état : langue + palier de performance + coupe-animations. Le conteneur
 * (`components/settings-provider.tsx`) applique la classe sur `<html>` et fournit
 * `useT` ; ce module porte les règles et la persistance (localStorage aujourd'hui —
 * le profil backend arrive avec CC-3/G14 backend).
 */

import type { Lang } from "./i18n";

export type Perf = "plein" | "confort" | "leger";

/** La vue du théâtre (spec théâtre-globe §5) : le globe, ou le même monde
 * déplié en carte. Un choix du joueur, persisté par appareil — pas un repli. */
export type StageView = "3d" | "2d";

export type Settings = {
  lang: Lang;
  perf: Perf;
  noAnim: boolean; // « désactiver toutes les animations » (raccourci reduced-motion)
  stageView: StageView;
};

export const DEFAULT_SETTINGS: Settings = {
  lang: "fr",
  perf: "plein",
  noAnim: false,
  stageView: "3d",
};

const LANGS: readonly string[] = ["fr", "en"];
const PERFS: readonly string[] = ["plein", "confort", "leger"];
const STAGE_VIEWS: readonly string[] = ["3d", "2d"];

const KEY_LANG = "wosi.lang";
const KEY_PERF = "wosi.perf";
const KEY_NOANIM = "wosi.noanim";
const KEY_STAGE = "wosi.stage";

/** Classe à poser sur `<html>` : `prefers-reduced-motion` impose au minimum
 * « confort » (spec §2) ; « léger » reste léger. « plein » = aucune classe. */
export function perfClass(perf: Perf, reducedMotion: boolean): string {
  if (perf === "leger") return "perf-leger";
  if (perf === "confort" || reducedMotion) return "perf-confort";
  return "";
}

type SettingsStore = Pick<Storage, "getItem" | "setItem">;

export function loadSettings(store: SettingsStore): Settings {
  const lang = store.getItem(KEY_LANG);
  const perf = store.getItem(KEY_PERF);
  const stage = store.getItem(KEY_STAGE);
  return {
    lang: lang !== null && LANGS.includes(lang) ? (lang as Lang) : DEFAULT_SETTINGS.lang,
    perf: perf !== null && PERFS.includes(perf) ? (perf as Perf) : DEFAULT_SETTINGS.perf,
    noAnim: store.getItem(KEY_NOANIM) === "1",
    stageView:
      stage !== null && STAGE_VIEWS.includes(stage)
        ? (stage as StageView)
        : DEFAULT_SETTINGS.stageView,
  };
}

export function saveSettings(settings: Settings, store: SettingsStore): void {
  store.setItem(KEY_LANG, settings.lang);
  store.setItem(KEY_PERF, settings.perf);
  store.setItem(KEY_NOANIM, settings.noAnim ? "1" : "0");
  store.setItem(KEY_STAGE, settings.stageView);
}
