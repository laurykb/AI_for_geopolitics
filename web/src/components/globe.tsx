"use client";

/** Planète Terre dézoomée (connexion / intro) : globe orthographique d3-geo rendu depuis
 * le topojson embarqué — AUCUNE image externe. Rendu réaliste : océans dégradés éclairés
 * par le soleil (haut-gauche), terres vertes/sable, calottes glaciaires, halo atmosphérique
 * cyan au limbe, ombrage de sphère (volume jour/nuit) et voile nuageux. Rotation lente ;
 * `prefers-reduced-motion` la fige. Les six pays du sommet luisent en or par-dessus. */

import { geoOrthographic, geoPath } from "d3-geo";
import { useEffect, useMemo, useState } from "react";
import { feature } from "topojson-client";
import type { Topology, GeometryCollection } from "topojson-specification";
import world from "world-atlas/countries-110m.json";

import { prefersReducedMotion } from "@/lib/stage";

/** Slug du jeu → id numérique ISO 3166-1 (les six pays connus luisent). */
const SUMMIT_ISO = new Set(["840", "156", "364", "250", "818", "682"]);

const SIZE = 560;
const MARGIN = 56; // la planète « dézoomée » : de l'espace autour du globe
const C = SIZE / 2; // centre du disque
const R = (SIZE - 2 * MARGIN) / 2; // rayon de la sphère

export function Globe({
  className,
  spinning = false,
  arriving = false,
}: {
  className?: string;
  /** Lancement (Play) : la rotation accélère — la Terre se met à tourner sur elle-même. */
  spinning?: boolean;
  /** Retour au menu : la rotation décélère — on ressort de l'atmosphère. */
  arriving?: boolean;
}) {
  const [lambda, setLambda] = useState(-12);

  const features = useMemo(() => {
    const topo = world as unknown as Topology<{ countries: GeometryCollection }>;
    return feature(topo, topo.objects.countries).features;
  }, []);

  useEffect(() => {
    if (prefersReducedMotion()) return;
    // Au repos, la Terre tourne LENTEMENT mais visiblement (~0,28°/tique ≈ un tour/50 s).
    let velocity = spinning ? 0.5 : arriving ? 6 : 0.28; // degrés par tique
    const timer = setInterval(() => {
      if (spinning) velocity = Math.min(velocity * 1.06, 7); // accélération douce
      else if (arriving) velocity = Math.max(velocity * 0.94, 0.28); // décélération
      setLambda((l) => (l + velocity) % 360);
    }, 40);
    return () => clearInterval(timer);
  }, [spinning, arriving]);

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
        {/* Océan : éclairé haut-gauche (soleil), grands fonds vers le limbe nuit. */}
        <radialGradient id="earth-ocean" cx="34%" cy="29%" r="80%">
          <stop offset="0%" stopColor="var(--ocean-lit)" />
          <stop offset="48%" stopColor="var(--ocean)" />
          <stop offset="82%" stopColor="var(--ocean-deep)" />
          <stop offset="100%" stopColor="var(--ocean-night)" />
        </radialGradient>
        {/* Terres : biomes par latitude (calottes vertes, bande sable, forêts). */}
        <linearGradient
          id="earth-land"
          gradientUnits="userSpaceOnUse"
          x1={C}
          y1={MARGIN}
          x2={C}
          y2={SIZE - MARGIN}
        >
          <stop offset="0%" stopColor="var(--land-lit)" />
          <stop offset="34%" stopColor="var(--land)" />
          <stop offset="52%" stopColor="var(--land-warm)" />
          <stop offset="72%" stopColor="var(--land)" />
          <stop offset="100%" stopColor="var(--land-dark)" />
        </linearGradient>
        {/* Ombrage de sphère : le limbe bas-droit tombe dans la nuit (volume 3D). */}
        <radialGradient id="earth-shade" cx="36%" cy="30%" r="82%">
          <stop offset="0%" stopColor="#000" stopOpacity="0" />
          <stop offset="60%" stopColor="#000" stopOpacity="0" />
          <stop offset="100%" stopColor="var(--space-deep)" stopOpacity="0.62" />
        </radialGradient>
        {/* Reflet solaire diffus (haut-gauche). */}
        <radialGradient id="earth-spec" cx="30%" cy="24%" r="44%">
          <stop offset="0%" stopColor="#eaf4ff" stopOpacity="0.32" />
          <stop offset="55%" stopColor="#eaf4ff" stopOpacity="0.05" />
          <stop offset="100%" stopColor="#eaf4ff" stopOpacity="0" />
        </radialGradient>
        {/* Halo atmosphérique : anneau cyan au bord du disque. */}
        <radialGradient id="earth-atmo" cx="50%" cy="50%" r="50%">
          <stop offset="86%" stopColor="var(--atmosphere)" stopOpacity="0" />
          <stop offset="93%" stopColor="var(--atmosphere)" stopOpacity="0.5" />
          <stop offset="100%" stopColor="var(--atmosphere)" stopOpacity="0" />
        </radialGradient>
        {/* Calotte / voile nuageux : blanc doux. */}
        <radialGradient id="earth-ice" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="var(--ice)" stopOpacity="0.85" />
          <stop offset="70%" stopColor="var(--ice)" stopOpacity="0.35" />
          <stop offset="100%" stopColor="var(--ice)" stopOpacity="0" />
        </radialGradient>
        <clipPath id="earth-clip">
          <circle cx={C} cy={C} r={R} />
        </clipPath>
        <filter id="earth-soft" x="-30%" y="-30%" width="160%" height="160%">
          <feGaussianBlur stdDeviation="4" />
        </filter>
      </defs>

      {/* Halo atmosphérique externe. */}
      <circle cx={C} cy={C} r={R + 15} fill="url(#earth-atmo)" />

      {/* Disque océan. */}
      <circle cx={C} cy={C} r={R} fill="url(#earth-ocean)" />

      <g clipPath="url(#earth-clip)">
        {/* Terres. */}
        {features.map((f, i) => (
          <path
            key={`land-${String(f.id)}-${i}`}
            d={path(f) ?? undefined}
            fill="url(#earth-land)"
            stroke="var(--ocean-deep)"
            strokeWidth="0.3"
          />
        ))}

        {/* Les pays du sommet luisent en or par-dessus les terres. */}
        {features
          .filter((f) => SUMMIT_ISO.has(String(f.id)))
          .map((f, i) => (
            <path
              key={`summit-${String(f.id)}-${i}`}
              d={path(f) ?? undefined}
              fill="var(--accent)"
              fillOpacity="0.55"
              stroke="var(--accent-bright)"
              strokeWidth="0.5"
            />
          ))}

        {/* Calottes glaciaires (pôles) + voile nuageux discret. */}
        <ellipse cx={C} cy={C - R * 0.82} rx={R * 0.62} ry={R * 0.26} fill="url(#earth-ice)" />
        <ellipse cx={C} cy={C + R * 0.86} rx={R * 0.66} ry={R * 0.24} fill="url(#earth-ice)" />
        <g filter="url(#earth-soft)" opacity="0.16" fill="#f4f8ff">
          <ellipse cx={C - R * 0.3} cy={C - R * 0.2} rx={R * 0.34} ry={R * 0.1} />
          <ellipse cx={C + R * 0.28} cy={C + R * 0.12} rx={R * 0.3} ry={R * 0.09} />
          <ellipse cx={C + R * 0.05} cy={C + R * 0.45} rx={R * 0.26} ry={R * 0.08} />
        </g>

        {/* Volume : ombre de sphère + reflet solaire. */}
        <circle cx={C} cy={C} r={R} fill="url(#earth-shade)" />
        <circle cx={C} cy={C} r={R} fill="url(#earth-spec)" />
      </g>
    </svg>
  );
}
