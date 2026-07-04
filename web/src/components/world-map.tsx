"use client";

/** Carte du monde : les pays du jeu colorés par l'indice Utopie global, le reste en
 * retrait. d3-geo + world-atlas (topojson 110m embarqué) — pas de lib de charting. */

import { geoNaturalEarth1, geoPath } from "d3-geo";
import { useMemo } from "react";
import { feature } from "topojson-client";
import type { Topology, GeometryCollection } from "topojson-specification";
import world from "world-atlas/countries-110m.json";

import { speakerMeta } from "@/lib/countries";
import { fmt } from "@/lib/format";

/** Slug du jeu → id numérique ISO 3166-1 utilisé par world-atlas. */
const ISO_NUM: Record<string, string> = {
  usa: "840",
  china: "156",
  iran: "364",
  france: "250",
  egypt: "818",
  saudi_arabia: "682",
};

/** Rouge dystopie → ambre 0,5 → vert utopie (échelle fixe, même sémantique que l'arc U). */
function uFill(u: number): string {
  const lerp = (a: number, b: number, t: number) => Math.round(a + (b - a) * t);
  const mix = (from: [number, number, number], to: [number, number, number], t: number) =>
    `rgb(${lerp(from[0], to[0], t)}, ${lerp(from[1], to[1], t)}, ${lerp(from[2], to[2], t)})`;
  const red: [number, number, number] = [248, 113, 113];
  const amber: [number, number, number] = [251, 191, 36];
  const green: [number, number, number] = [52, 211, 153];
  return u < 0.5 ? mix(red, amber, u * 2) : mix(amber, green, (u - 0.5) * 2);
}

const WIDTH = 940;
const HEIGHT = 480;

export function WorldMap({ countries, utopia }: { countries: string[]; utopia: number }) {
  const features = useMemo(() => {
    const topo = world as unknown as Topology<{ countries: GeometryCollection }>;
    return feature(topo, topo.objects.countries).features;
  }, []);
  const path = useMemo(() => {
    const projection = geoNaturalEarth1().fitSize([WIDTH, HEIGHT], { type: "Sphere" });
    return geoPath(projection);
  }, []);

  const active = new Map(countries.map((slug) => [ISO_NUM[slug], slug]));
  const fill = uFill(utopia);

  return (
    <figure>
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        role="img"
        aria-label={`Carte du monde — pays du sommet colorés par l'indice Utopie ${fmt(utopia)}`}
        className="w-full"
      >
        <path
          d={path({ type: "Sphere" }) ?? undefined}
          fill="var(--surface)"
          stroke="var(--border)"
        />
        {features.map((f, i) => {
          const slug = active.get(String(f.id));
          return (
            <path
              key={`${String(f.id)}-${i}`} // certains territoires n'ont pas d'id ISO unique
              d={path(f) ?? undefined}
              fill={slug ? fill : "var(--muted)"}
              stroke="var(--background)"
              strokeWidth="0.5"
              opacity={slug ? 0.95 : 0.55}
            >
              <title>
                {slug
                  ? `${speakerMeta(slug).label} — au sommet (U ${fmt(utopia)})`
                  : ((f.properties as { name?: string })?.name ?? "")}
              </title>
            </path>
          );
        })}
      </svg>
      <figcaption className="mt-2 flex items-center gap-3 text-xs text-fg-faint">
        <span className="flex items-center gap-1.5">
          <span
            className="inline-block h-2 w-8 rounded-full"
            style={{
              background:
                "linear-gradient(to right, var(--dystopia), var(--warn), var(--utopia))",
            }}
          />
          indice Utopie (0 → 1), échelle fixe
        </span>
        <span>pays hors sommet en gris</span>
        <span className="ml-auto font-mono tabular-nums" style={{ color: fill }}>
          U = {fmt(utopia)}
        </span>
      </figcaption>
    </figure>
  );
}
