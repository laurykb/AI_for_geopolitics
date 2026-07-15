"use client";

/** Carte du monde : chaque pays du sommet teinté par SON indice U local (même
 * échelle fixe que la scène — `uTint` de lib/stage), le reste en retrait.
 * d3-geo + world-atlas (topojson 110m embarqué) — pas de lib de charting. */

import { geoNaturalEarth1, geoPath } from "d3-geo";
import { useMemo } from "react";

import { ISO_NUM, speakerMeta } from "@/lib/countries";
import { fmt } from "@/lib/format";
import { uTint } from "@/lib/stage";
import { WORLD_FEATURES } from "@/lib/world";

import { EarthMapDefs } from "./earth-defs";
import { useT } from "./settings-provider";

const WIDTH = 940;
const HEIGHT = 480;

export function WorldMap({
  countries,
  utopia,
  uByCountry = {},
}: {
  countries: string[];
  /** Indice U global : légende + repli des pays sans valeur locale. */
  utopia: number;
  /** U locale par pays — même dérivation que la scène (`localU` de lib/stage). */
  uByCountry?: Record<string, number>;
}) {
  const t = useT();
  const path = useMemo(() => {
    const projection = geoNaturalEarth1().fitSize([WIDTH, HEIGHT], { type: "Sphere" });
    return geoPath(projection);
  }, []);

  const active = new Map(countries.map((slug) => [ISO_NUM[slug], slug]));
  const localU = (slug: string) => uByCountry[slug] ?? utopia;

  return (
    <figure>
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        role="img"
        aria-label={t("worldmap.aria").replace("{u}", fmt(utopia))}
        className="w-full"
      >
        <EarthMapDefs height={HEIGHT} />
        <path
          d={path({ type: "Sphere" }) ?? undefined}
          fill="url(#map-ocean)"
          stroke="var(--border)"
        />
        {WORLD_FEATURES.map((f, i) => {
          const slug = active.get(String(f.id));
          return (
            <path
              key={`${String(f.id)}-${i}`} // certains territoires n'ont pas d'id ISO unique
              d={path(f) ?? undefined}
              fill={slug ? uTint(localU(slug)) : "url(#map-land)"}
              stroke="var(--ocean-night)"
              strokeWidth="0.5"
              opacity={slug ? 0.95 : 0.7}
            >
              <title>
                {slug
                  ? `${speakerMeta(slug).label}${t("worldmap.au-sommet").replace("{u}", fmt(localU(slug)))}`
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
          {t("worldmap.legende")}
        </span>
        <span>{t("worldmap.hors-sommet")}</span>
        <span className="ml-auto font-mono tabular-nums" style={{ color: uTint(utopia) }}>
          {t("worldmap.monde")} {fmt(utopia)}
        </span>
      </figcaption>
    </figure>
  );
}
