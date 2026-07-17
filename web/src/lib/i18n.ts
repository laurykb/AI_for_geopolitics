/** i18n minimal (G14 §1) : deux dictionnaires plats, clé → chaîne. Pas de framework
 * tant que 2 langues suffisent (« simplicité d'abord »). Le français est la langue
 * source : l'anglais absent retombe sur le FR, une clé inconnue ressort telle quelle
 * (repérable en dev). Le hook `useT` vit dans `components/settings-provider.tsx`. */

import en from "@/i18n/en.json";
import fr from "@/i18n/fr.json";

export type Lang = "fr" | "en";

export type Dicts = Record<Lang, Record<string, string>>;

/** Cœur pur, dictionnaires injectés (tests) : langue demandée → repli FR → clé. */
export function translateWith(dicts: Dicts, lang: Lang, key: string): string {
  return dicts[lang][key] ?? dicts.fr[key] ?? key;
}

const DICTS: Dicts = { fr, en };

/** Traduction sur les vrais dictionnaires `web/src/i18n/{fr,en}.json`. */
export function translate(lang: Lang, key: string): string {
  return translateWith(DICTS, lang, key);
}
