/** Aides pures de l'éditeur de crises maison (G12-b §5). Extraites pour être testées. */

/** id de crise stable et jouable, déduit d'un titre : a-z0-9 + underscore, capé à 48.
 * Les diacritiques sont retirés (é → e), les séparations deviennent « _ », pas de « _ »
 * en tête/fin. Un titre sans caractère alphanumérique donne une chaîne vide (l'UI le
 * signale : un identifiant est requis). */
export function slugify(text: string): string {
  return text
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 48);
}
