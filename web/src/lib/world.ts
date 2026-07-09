/** Géométrie du monde — source unique. Le topojson embarqué (world-atlas 110m) est
 * décodé UNE fois au chargement du module, au lieu d'être re-décodé dans chaque carte
 * (globe, sélection, monde, scène). Les features sont immuables et partagées. */

import { feature } from "topojson-client";
import type { GeometryCollection, Topology } from "topojson-specification";
import world from "world-atlas/countries-110m.json";

const topo = world as unknown as Topology<{ countries: GeometryCollection }>;

/** Tous les pays du monde (Feature[]), décodés une seule fois. */
export const WORLD_FEATURES = feature(topo, topo.objects.countries).features;
