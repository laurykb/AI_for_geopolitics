"use client";

/** Carte de sélection du sommet (G11-b §1 S4). Les pays éligibles sont blancs ;
 * un clic les passe en jaune (au sommet), un re-clic les retire. Compteur « n/7 »,
 * survol → mini-fiche (indices clés). Rôle « Jouer un pays » : une fois les 7 réunis,
 * un clic sur un pays déjà au sommet le désigne comme SIEN (halo doré). */

import { geoNaturalEarth1, geoPath } from "d3-geo";
import { useMemo, useState } from "react";
import { feature } from "topojson-client";
import type { Topology, GeometryCollection } from "topojson-specification";
import world from "world-atlas/countries-110m.json";

import { ISO_NUM, ROSTER, speakerMeta } from "@/lib/countries";

const WIDTH = 940;
const HEIGHT = 480;

/** ISO numérique → slug, restreint au roster jouable (les seuls cliquables). */
const ISO_TO_SLUG = new Map(
  ROSTER.filter((s) => ISO_NUM[s]).map((s) => [ISO_NUM[s], s] as const),
);

export type Fiche = { rows: { label: string; value: string }[] };

export function SelectMap({
  selected,
  capacity,
  onToggle,
  flag = null,
  pickingFlag = false,
  onPickFlag,
  ficheFor,
}: {
  selected: string[];
  capacity: number;
  onToggle: (slug: string) => void;
  flag?: string | null;
  /** Rôle joueur, 7 réunis : un clic sur un pays au sommet le désigne (au lieu de le retirer). */
  pickingFlag?: boolean;
  onPickFlag?: (slug: string) => void;
  ficheFor?: (slug: string) => Fiche | null;
}) {
  const [hovered, setHovered] = useState<string | null>(null);

  const features = useMemo(() => {
    const topo = world as unknown as Topology<{ countries: GeometryCollection }>;
    return feature(topo, topo.objects.countries).features;
  }, []);
  const path = useMemo(() => {
    const projection = geoNaturalEarth1().fitSize([WIDTH, HEIGHT], { type: "Sphere" });
    return geoPath(projection);
  }, []);

  const chosen = new Set(selected);
  const full = selected.length >= capacity;

  const activate = (slug: string) => {
    if (pickingFlag && chosen.has(slug)) onPickFlag?.(slug);
    else onToggle(slug);
  };

  const fiche = hovered ? ficheFor?.(hovered) : null;
  const meta = hovered ? speakerMeta(hovered) : null;

  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_16rem]">
      <div className="rounded-lg border border-edge bg-surface p-3">
        <svg
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          className="w-full"
          role="group"
          aria-label="Carte du monde — choisis les 7 États du sommet"
        >
          <path
            d={path({ type: "Sphere" }) ?? undefined}
            fill="var(--surface)"
            stroke="var(--border)"
          />
          {features.map((f, i) => {
            const slug = ISO_TO_SLUG.get(String(f.id));
            if (!slug) {
              return (
                <path
                  key={`bg-${i}`}
                  d={path(f) ?? undefined}
                  fill="var(--muted)"
                  stroke="var(--background)"
                  strokeWidth="0.5"
                  opacity={0.32}
                />
              );
            }
            const on = chosen.has(slug);
            // Le halo doré du pays joué ne se montre qu'une fois le sommet complet
            // (sinon il persiste, incohérent, quand on redescend sous 7).
            const isFlag = flag === slug && full;
            const label = speakerMeta(slug).label;
            return (
              <path
                key={`${slug}-${i}`}
                d={path(f) ?? undefined}
                role="button"
                tabIndex={0}
                aria-pressed={on}
                aria-label={`${label}${on ? " — au sommet" : ""}${isFlag ? " — ton pays" : ""}`}
                onClick={() => activate(slug)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    activate(slug);
                  }
                }}
                onMouseEnter={() => setHovered(slug)}
                onFocus={() => setHovered(slug)}
                onMouseLeave={() => setHovered((h) => (h === slug ? null : h))}
                className="cursor-pointer outline-none transition-[fill,opacity] focus-visible:opacity-100"
                fill={isFlag ? "var(--accent-bright)" : on ? "var(--accent)" : "#e7e9ef"}
                fillOpacity={on ? 0.95 : full ? 0.5 : 0.82}
                stroke={isFlag ? "var(--accent-bright)" : "var(--background)"}
                strokeWidth={isFlag ? 1.4 : 0.5}
              />
            );
          })}
        </svg>
        <p className="mt-2 flex items-center justify-between text-xs text-fg-faint">
          <span>Éligibles en blanc · au sommet en jaune · clique pour ajouter/retirer</span>
          <span
            className={`font-mono tabular-nums ${
              selected.length === capacity ? "text-accent-bright" : "text-warn"
            }`}
          >
            {selected.length}/{capacity}
          </span>
        </p>
      </div>

      {/* Mini-fiche au survol (indices clés) — panneau stable, plus accessible qu'un tooltip. */}
      <aside className="rounded-lg border border-edge bg-surface p-4">
        {meta ? (
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <span
                className="grid h-7 w-7 place-items-center rounded-full text-[11px] font-semibold text-background"
                style={{ background: meta.hue }}
              >
                {meta.code}
              </span>
              <span className="font-semibold">{meta.label}</span>
            </div>
            {fiche && fiche.rows.length > 0 ? (
              <dl className="space-y-1 text-xs">
                {fiche.rows.map((r) => (
                  <div key={r.label} className="flex justify-between gap-3">
                    <dt className="text-fg-faint">{r.label}</dt>
                    <dd className="font-mono tabular-nums text-fg-muted">{r.value}</dd>
                  </div>
                ))}
              </dl>
            ) : (
              <p className="text-xs text-fg-faint">Indices clés indisponibles.</p>
            )}
            {chosen.has(hovered!) && (
              <p className="text-xs text-accent-bright">
                {flag === hovered ? "★ Ton pays" : "Au sommet"}
              </p>
            )}
          </div>
        ) : (
          <p className="text-xs text-fg-faint">
            Survole un pays pour voir ses indices clés.
            {pickingFlag && " Clique un pays au sommet pour le jouer."}
          </p>
        )}
      </aside>
    </div>
  );
}
