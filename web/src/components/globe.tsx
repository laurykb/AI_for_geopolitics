"use client";

/** Planète Terre dézoomée (page d'introduction) : globe orthographique d3-geo rendu
 * depuis le même topojson que la carte — aucune image externe. Rotation lente ;
 * `prefers-reduced-motion` la fige. Les pays du sommet brillent en or. */

import { geoOrthographic, geoPath } from "d3-geo";
import { useEffect, useMemo, useState } from "react";
import { feature } from "topojson-client";
import type { Topology, GeometryCollection } from "topojson-specification";
import world from "world-atlas/countries-110m.json";

import { prefersReducedMotion } from "@/lib/stage";

/** Slug du jeu → id numérique ISO 3166-1 (les six pays connus brillent). */
const SUMMIT_ISO = new Set(["840", "156", "364", "250", "818", "682"]);

const SIZE = 560;
const MARGIN = 56; // la planète « dézoomée » : de l'espace autour du globe

export function Globe({
  className,
  spinning = false,
}: {
  className?: string;
  /** Lancement (Play) : la rotation accélère — la Terre se met à tourner sur elle-même. */
  spinning?: boolean;
}) {
  const [lambda, setLambda] = useState(-12);

  const features = useMemo(() => {
    const topo = world as unknown as Topology<{ countries: GeometryCollection }>;
    return feature(topo, topo.objects.countries).features;
  }, []);

  useEffect(() => {
    if (prefersReducedMotion()) return;
    let velocity = spinning ? 0.4 : 0.12; // degrés par tique
    const timer = setInterval(() => {
      if (spinning) velocity = Math.min(velocity * 1.06, 7); // accélération douce
      setLambda((l) => (l + velocity) % 360);
    }, 40);
    return () => clearInterval(timer);
  }, [spinning]);

  const path = useMemo(() => {
    const projection = geoOrthographic()
      .fitExtent(
        [
          [MARGIN, MARGIN],
          [SIZE - MARGIN, SIZE - MARGIN],
        ],
        { type: "Sphere" },
      )
      .rotate([lambda, -16]);
    return geoPath(projection);
  }, [lambda]);

  return (
    <svg viewBox={`0 0 ${SIZE} ${SIZE}`} className={className} aria-hidden="true">
      <defs>
        <radialGradient id="globe-halo" cx="50%" cy="50%" r="50%">
          <stop offset="62%" stopColor="var(--accent)" stopOpacity="0" />
          <stop offset="82%" stopColor="var(--accent)" stopOpacity="0.14" />
          <stop offset="100%" stopColor="var(--accent)" stopOpacity="0" />
        </radialGradient>
        <radialGradient id="globe-sea" cx="38%" cy="34%" r="72%">
          <stop offset="0%" stopColor="#232345" />
          <stop offset="100%" stopColor="#0c0c1d" />
        </radialGradient>
      </defs>
      {/* Atmosphère dorée, très discrète. */}
      <circle cx={SIZE / 2} cy={SIZE / 2} r={SIZE / 2 - 4} fill="url(#globe-halo)" />
      <path
        d={path({ type: "Sphere" }) ?? undefined}
        fill="url(#globe-sea)"
        stroke="var(--border)"
        strokeWidth="1"
      />
      {features.map((f, i) => {
        const summit = SUMMIT_ISO.has(String(f.id));
        return (
          <path
            key={`${String(f.id)}-${i}`}
            d={path(f) ?? undefined}
            fill={summit ? "var(--accent)" : "var(--muted)"}
            opacity={summit ? 0.9 : 0.75}
            stroke="var(--background)"
            strokeWidth="0.4"
          />
        );
      })}
    </svg>
  );
}
