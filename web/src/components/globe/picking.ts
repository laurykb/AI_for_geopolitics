/** Picking du globe (spec théâtre-globe §2) — géométrie PURE, sans three ni DOM.
 *
 * Le même mapping lon/lat ↔ sphère que le prototype (rayon 1, Greenwich face
 * caméra à lon 0) : `toXYZ` plante les objets, `inverseLL` retrouve le lieu
 * sous un point d'impact du raycast, `countryAt` répond « quel pays du sommet
 * est sous ce clic ? » via d3.geoContains sur les features du fond de carte. */

import { geoContains } from "d3-geo";

import { ISO_NUM } from "@/lib/countries";

/** Feature d'un fond world-atlas (110m ou 50m) : id ISO numérique + géométrie. */
export type GlobeFeature = Parameters<typeof geoContains>[0] & {
  id?: string | number;
};

export type SummitFeature = { slug: string; feat: GlobeFeature | undefined };

/** lon/lat (degrés) → point sur la sphère de rayon `r`. */
export function toXYZ(lon: number, lat: number, r = 1): [number, number, number] {
  const phi = ((90 - lat) * Math.PI) / 180;
  const th = ((lon + 180) * Math.PI) / 180;
  return [-r * Math.sin(phi) * Math.cos(th), r * Math.cos(phi), r * Math.sin(phi) * Math.sin(th)];
}

/** Point 3D (n'importe quel rayon) → [lon, lat] en degrés. */
export function inverseLL([x, y, z]: [number, number, number]): [number, number] {
  const len = Math.hypot(x, y, z) || 1;
  const lat = 90 - (Math.acos(Math.max(-1, Math.min(1, y / len))) * 180) / Math.PI;
  const lon = ((((Math.atan2(z, -x) * 180) / Math.PI - 180 + 540) % 360) + 360) % 360 - 180;
  return [lon, lat];
}

/** Résout le casting du sommet vers les features du fond par ISO numérique.
 * Un pays inventé n'a pas d'ISO : `feat` reste undefined (pas de liseré,
 * pas de clic-pays — même règle que la StageMap). */
export function summitFeatures(countries: string[], features: GlobeFeature[]): SummitFeature[] {
  const byIso = new Map(features.map((f) => [String(f.id), f]));
  return countries.map((slug) => ({ slug, feat: byIso.get(ISO_NUM[slug] ?? "") }));
}

/** Pays du sommet sous le point, ou null (océan, hors sommet, pick raté). */
export function countryAt(
  lonlat: [number, number] | null,
  feats: SummitFeature[],
): string | null {
  if (!lonlat) return null;
  for (const s of feats) if (s.feat && geoContains(s.feat, lonlat)) return s.slug;
  return null;
}
