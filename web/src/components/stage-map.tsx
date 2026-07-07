"use client";

/** La carte est la scène (G1) : la même carte d3-geo que /monde, mais vivante —
 * teintes U par pays (transition 1,5 s), pulsation ambre sur les acteurs de
 * l'événement, l'orateur s'allume et clignote, voile de brouillard, pays
 * suspendus au banc, gel du verdict, respiration en fin de round. Les keyframes
 * vivent dans `globals.css` (`prefers-reduced-motion` y réduit tout à des
 * opacités simples). */

import { geoNaturalEarth1, geoPath } from "d3-geo";
import { useMemo } from "react";
import { feature } from "topojson-client";
import type { Topology, GeometryCollection } from "topojson-specification";
import world from "world-atlas/countries-110m.json";

import { ISO_NUM, speakerMeta } from "@/lib/countries";
import { fmt } from "@/lib/format";
import { CAPITALS, uTint } from "@/lib/stage";

const WIDTH = 940;
const HEIGHT = 480;
const SUSPENDED_FILL = "rgb(82, 82, 96)"; // gris désaturé : le pays est au banc

export type StageMapProps = {
  countries: string[];
  /** U locale par pays (dérivée : U global nuancé par les deltas du round). */
  uByCountry: Record<string, number>;
  /** Indice U global (légende + pays sans valeur locale). */
  utopia: number;
  /** Orateur courant : le pays s'allume et clignote. */
  speaking?: string | null;
  /** Acteurs de l'événement du round : pulsation ambre (rejouée quand la clé change). */
  pulseActors?: string[];
  pulseKey?: string | number;
  /** Pays désinformés (fog) → la narration qu'ils reçoivent (tooltip). */
  misled?: Record<string, string>;
  /** Pays au banc ce round : gris désaturé + cadenas. */
  suspended?: string[];
  /** Temps suspendu (verdict) : la carte gèle. */
  frozen?: boolean;
  /** Fin de round : la scène « respire » (rejouée quand la clé change). */
  breatheKey?: number;
  /** Titre de l'événement, affiché en carte au-dessus de la scène. */
  eventTitle?: string;
};

export function StageMap({
  countries,
  uByCountry,
  utopia,
  speaking = null,
  pulseActors = [],
  pulseKey = 0,
  misled = {},
  suspended = [],
  frozen = false,
  breatheKey = 0,
  eventTitle,
}: StageMapProps) {
  const features = useMemo(() => {
    const topo = world as unknown as Topology<{ countries: GeometryCollection }>;
    return feature(topo, topo.objects.countries).features;
  }, []);
  const { path, project } = useMemo(() => {
    const projection = geoNaturalEarth1().fitSize([WIDTH, HEIGHT], { type: "Sphere" });
    return {
      path: geoPath(projection),
      project: (lonLat: [number, number]) => projection(lonLat),
    };
  }, []);

  const active = new Map(countries.map((slug) => [ISO_NUM[slug], slug]));
  const suspendedSet = new Set(suspended);

  const capital = (slug: string): [number, number] | null => {
    const lonLat = CAPITALS[slug];
    return lonLat ? project(lonLat) : null;
  };

  return (
    <figure className="relative">
      {eventTitle && (
        <div className="pointer-events-none absolute inset-x-0 top-2 z-10 flex justify-center">
          <p className="max-w-[70%] truncate rounded-md border border-edge bg-surface/85 px-3 py-1.5 text-xs font-medium text-foreground backdrop-blur">
            {eventTitle}
          </p>
        </div>
      )}
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        role="img"
        aria-label={`Scène du sommet — pays teintés par leur trajectoire (U global ${fmt(utopia)})`}
        className={`w-full ${frozen ? "stage-frozen" : ""}`}
      >
        <g key={`breathe-${breatheKey}`} className={breatheKey ? "stage-breathe" : undefined}>
          <path
            d={path({ type: "Sphere" }) ?? undefined}
            fill="var(--surface)"
            stroke="var(--border)"
          />
          {features.map((f, i) => {
            const slug = active.get(String(f.id));
            const isSuspended = slug ? suspendedSet.has(slug) : false;
            const isSpeaking = slug != null && slug === speaking;
            const fill = slug
              ? isSpeaking
                ? "var(--accent-bright)" // le pays qui parle s'allume en direct
                : isSuspended
                  ? SUSPENDED_FILL
                  : uTint(uByCountry[slug] ?? utopia)
              : "var(--muted)";
            return (
              <path
                key={`${String(f.id)}-${i}`} // certains territoires n'ont pas d'id ISO unique
                d={path(f) ?? undefined}
                fill={fill}
                stroke={isSpeaking ? "var(--accent-bright)" : "var(--background)"}
                strokeWidth={isSpeaking ? 1.2 : 0.5}
                opacity={slug ? (isSuspended ? 0.7 : 0.95) : 0.55}
                className={
                  slug
                    ? isSpeaking
                      ? "stage-country stage-country-speaking"
                      : "stage-country"
                    : undefined
                }
              >
                <title>
                  {slug
                    ? isSpeaking
                      ? `${speakerMeta(slug).label} — a la parole`
                      : isSuspended
                        ? `${speakerMeta(slug).label} — suspendu ce round (au banc)`
                        : `${speakerMeta(slug).label} — U locale ${fmt(uByCountry[slug] ?? utopia)}`
                    : ((f.properties as { name?: string })?.name ?? "")}
                </title>
              </path>
            );
          })}

          {/* Voile de brouillard : les pays désinformés voient un autre monde. */}
          {Object.keys(misled).map((slug) => {
            const iso = ISO_NUM[slug];
            const f = features.find((x) => String(x.id) === iso);
            if (!f) return null;
            return (
              <path
                key={`veil-${slug}`}
                d={path(f) ?? undefined}
                fill="#3b82f6"
                opacity={0.3}
                className="stage-veil"
              >
                <title>{`${speakerMeta(slug).label} — désinformé : « ${misled[slug]} »`}</title>
              </path>
            );
          })}

          {/* Assombrissement bref quand l'événement tombe. */}
          {pulseActors.length > 0 && (
            <rect
              key={`dim-${pulseKey}`}
              x="0"
              y="0"
              width={WIDTH}
              height={HEIGHT}
              fill="#000"
              className="stage-dim"
              pointerEvents="none"
            />
          )}

          {/* Pulsation ambre (2 ondes) sur les acteurs de l'événement. */}
          {pulseActors.map((slug) => {
            const xy = capital(slug);
            if (!xy) return null;
            return (
              <g key={`pulse-${slug}-${pulseKey}`} pointerEvents="none">
                <circle cx={xy[0]} cy={xy[1]} r="6" className="stage-pulse" />
                <circle
                  cx={xy[0]}
                  cy={xy[1]}
                  r="6"
                  className="stage-pulse stage-pulse-2"
                />
              </g>
            );
          })}

          {/* Cadenas sur les capitales suspendues. */}
          {suspended.map((slug) => {
            const xy = capital(slug);
            if (!xy) return null;
            const [x, y] = xy;
            return (
              <g key={`lock-${slug}`} pointerEvents="none" opacity={0.9}>
                <rect x={x - 3.2} y={y - 2} width="6.4" height="5.4" rx="1" fill="#cbd5e1" />
                <path
                  d={`M ${x - 2} ${y - 2} v -1.6 a 2 2 0 0 1 4 0 v 1.6`}
                  fill="none"
                  stroke="#cbd5e1"
                  strokeWidth="1.1"
                />
              </g>
            );
          })}

          {/* Œil barré sur les capitales désinformées. */}
          {Object.keys(misled).map((slug) => {
            const xy = capital(slug);
            if (!xy) return null;
            const [x, y] = xy;
            return (
              <g key={`eye-${slug}`} pointerEvents="none" opacity={0.95}>
                <ellipse cx={x} cy={y} rx="4.6" ry="2.8" fill="none" stroke="#93c5fd" strokeWidth="1" />
                <circle cx={x} cy={y} r="1.2" fill="#93c5fd" />
                <line x1={x - 5.5} y1={y + 4} x2={x + 5.5} y2={y - 4} stroke="#93c5fd" strokeWidth="1.2" />
              </g>
            );
          })}
        </g>
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
          teinte = trajectoire du pays (échelle U fixe)
        </span>
        <span>hors sommet en gris</span>
        <span className="ml-auto font-mono tabular-nums" style={{ color: uTint(utopia) }}>
          U = {fmt(utopia)}
        </span>
      </figcaption>
    </figure>
  );
}
