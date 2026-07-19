"use client";

/** Carte de sélection du sommet (G11-b §1 S4). Les pays éligibles sont blancs ;
 * un clic les passe en jaune (au sommet), un re-clic les retire. Compteur « n/7 »,
 * survol → mini-fiche (indices clés). Rôle « Jouer un pays » : une fois les 7 réunis,
 * un clic sur un pays déjà au sommet le désigne comme SIEN (halo doré). */

import { geoNaturalEarth1, geoPath } from "d3-geo";
import { useMemo, useState } from "react";

import { ISO_NUM, MAP_POINT_COUNTRIES, ROSTER, speakerMeta } from "@/lib/countries";
import { CAPITALS } from "@/lib/stage";
import { WORLD_FEATURES } from "@/lib/world";

import { EarthMapDefs } from "./earth-defs";
import { useT } from "./settings-provider";

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
  eligible,
  eligibilityLabel,
}: {
  selected: string[];
  capacity: number;
  onToggle: (slug: string) => void;
  flag?: string | null;
  /** Rôle joueur, 7 réunis : un clic sur un pays au sommet le désigne (au lieu de le retirer). */
  pickingFlag?: boolean;
  onPickFlag?: (slug: string) => void;
  ficheFor?: (slug: string) => Fiche | null;
  eligible?: string[];
  eligibilityLabel?: string;
}) {
  const t = useT();
  const [hovered, setHovered] = useState<string | null>(null);
  const [zoom, setZoom] = useState(1);

  const { path, project } = useMemo(() => {
    const projection = geoNaturalEarth1().fitSize([WIDTH, HEIGHT], { type: "Sphere" });
    return { path: geoPath(projection), project: (lonLat: [number, number]) => projection(lonLat) };
  }, []);

  const chosen = new Set(selected);
  const allowed = eligible ? new Set(eligible) : null;
  const full = selected.length >= capacity;

  const activate = (slug: string) => {
    if (allowed && !allowed.has(slug)) return;
    if (pickingFlag && chosen.has(slug)) onPickFlag?.(slug);
    else onToggle(slug);
  };

  const fiche = hovered ? ficheFor?.(hovered) : null;
  const meta = hovered ? speakerMeta(hovered) : null;

  return (
    <div className="space-y-3">
      <div className="rounded-lg border border-edge bg-surface p-3">
        <div className="mb-2 flex items-center justify-between gap-3">
          <span className="text-xs text-fg-faint">Carte du monde</span>
          <div className="flex items-center gap-1" aria-label="Zoom de la carte">
            <button
              type="button"
              onClick={() => setZoom((value) => Math.max(1, value - 0.5))}
              disabled={zoom <= 1}
              aria-label="Dézoomer la carte"
              className="grid h-7 w-7 place-items-center rounded border border-edge text-sm text-fg-muted transition-colors hover:border-edge-strong hover:text-foreground disabled:cursor-not-allowed disabled:opacity-40"
            >
              −
            </button>
            <button
              type="button"
              onClick={() => setZoom(1)}
              disabled={zoom === 1}
              aria-label="Réinitialiser le zoom"
              className="min-w-12 rounded border border-edge px-2 py-1 text-[11px] font-mono tabular-nums text-fg-muted transition-colors hover:border-edge-strong hover:text-foreground disabled:cursor-default disabled:opacity-70"
            >
              {Math.round(zoom * 100)} %
            </button>
            <button
              type="button"
              onClick={() => setZoom((value) => Math.min(3, value + 0.5))}
              disabled={zoom >= 3}
              aria-label="Zoomer la carte"
              className="grid h-7 w-7 place-items-center rounded border border-edge text-sm text-fg-muted transition-colors hover:border-edge-strong hover:text-foreground disabled:cursor-not-allowed disabled:opacity-40"
            >
              +
            </button>
          </div>
        </div>
        <div className="max-h-[72vh] overflow-auto rounded-md">
          <svg
            viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
            className="block"
            style={{ width: `${zoom * 100}%`, maxWidth: "none" }}
            role="group"
            aria-label={t("selectmap.aria")}
          >
          <EarthMapDefs height={HEIGHT} />
          <path
            d={path({ type: "Sphere" }) ?? undefined}
            fill="url(#map-ocean)"
            stroke="var(--border)"
          />
          {WORLD_FEATURES.map((f, i) => {
            const slug = ISO_TO_SLUG.get(String(f.id));
            if (!slug) {
              return (
                <path
                  key={`bg-${i}`}
                  d={path(f) ?? undefined}
                  fill="url(#map-land)"
                  stroke="var(--ocean-night)"
                  strokeWidth="0.5"
                  opacity={0.78}
                />
              );
            }
            const on = chosen.has(slug);
            const disabled = Boolean(allowed && !allowed.has(slug));
            // Le halo doré du pays joué ne se montre qu'une fois le sommet complet
            // (sinon il persiste, incohérent, quand on redescend sous 7).
            const isFlag = flag === slug && full;
            const label = speakerMeta(slug).label;
            return (
              <path
                key={`${slug}-${i}`}
                d={path(f) ?? undefined}
                role="button"
                tabIndex={disabled ? -1 : 0}
                aria-disabled={disabled}
                aria-pressed={on}
                aria-label={`${label}${on ? t("selectmap.aria-au-sommet") : ""}${isFlag ? t("selectmap.aria-ton-pays") : ""}`}
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
                className={`${disabled ? "cursor-not-allowed" : "cursor-pointer"} outline-none transition-[fill,opacity] focus-visible:opacity-100`}
                fill={disabled ? "#525866" : isFlag ? "var(--accent-bright)" : on ? "var(--accent)" : "#e7e9ef"}
                fillOpacity={disabled ? 0.28 : on ? 0.95 : full ? 0.5 : 0.82}
                stroke={isFlag ? "var(--accent-bright)" : "var(--background)"}
                strokeWidth={isFlag ? 1.4 : 0.5}
              />
            );
          })}
          {[...MAP_POINT_COUNTRIES].map((slug) => {
            const xy = project(CAPITALS[slug]);
            if (!xy || !ROSTER.includes(slug)) return null;
            const on = chosen.has(slug);
            const disabled = Boolean(allowed && !allowed.has(slug));
            const isFlag = flag === slug && full;
            const label = speakerMeta(slug).label;
            return (
              <g
                key={`point-${slug}`}
                role="button"
                tabIndex={disabled ? -1 : 0}
                aria-disabled={disabled}
                aria-pressed={on}
                aria-label={`${label}${on ? t("selectmap.aria-au-sommet") : ""}${isFlag ? t("selectmap.aria-ton-pays") : ""}`}
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
                className={`${disabled ? "cursor-not-allowed" : "cursor-pointer"} outline-none`}
              >
                <circle cx={xy[0]} cy={xy[1]} r="10" fill="transparent" />
                <circle
                  cx={xy[0]}
                  cy={xy[1]}
                  r={isFlag ? 5.5 : 4.5}
                  fill={disabled ? "#525866" : isFlag ? "var(--accent-bright)" : on ? "var(--accent)" : "#e7e9ef"}
                  fillOpacity={disabled ? 0.28 : on ? 0.95 : full ? 0.5 : 0.9}
                  stroke={isFlag ? "var(--accent-bright)" : "var(--background)"}
                  strokeWidth={isFlag ? 2 : 1.2}
                />
              </g>
            );
          })}
          </svg>
        </div>
        <p className="mt-2 flex items-center justify-between text-xs text-fg-faint">
          <span>{eligibilityLabel || t("selectmap.legende")}</span>
          <span
            className={`font-mono tabular-nums ${
              selected.length === capacity ? "text-accent-bright" : "text-warn"
            }`}
          >
            {selected.length}/{capacity}
          </span>
        </p>
      </div>

      {/* Fiche compacte : bandeau sous la carte, alimenté au survol ou au focus clavier. */}
      <div
        role="status"
        aria-live="polite"
        className="min-h-14 rounded-lg border border-edge bg-surface px-4 py-3"
      >
        {meta ? (
          <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
            <div className="flex min-w-fit items-center gap-2">
              <span
                className="grid h-7 w-7 place-items-center rounded-full text-[11px] font-semibold text-background"
                style={{ background: meta.hue }}
              >
                {meta.code}
              </span>
              <span className="font-semibold">{meta.label}</span>
            </div>
            {fiche && fiche.rows.length > 0 ? (
              <dl className="flex flex-wrap gap-x-5 gap-y-1 text-xs">
                {fiche.rows.map((r) => (
                  <div key={r.label} className="flex gap-2">
                    <dt className="text-fg-faint">{r.label}</dt>
                    <dd className="font-mono tabular-nums text-fg-muted">{r.value}</dd>
                  </div>
                ))}
              </dl>
            ) : (
              <p className="text-xs text-fg-faint">{t("selectmap.infos-indisponibles")}</p>
            )}
            {chosen.has(hovered!) && (
              <p className="ml-auto text-xs text-accent-bright">
                {flag === hovered ? t("selectmap.ton-pays") : t("selectmap.au-sommet")}
              </p>
            )}
          </div>
        ) : (
          <p className="text-xs text-fg-faint">
            {t("selectmap.survole")}
            {pickingFlag && ` ${t("selectmap.designer")}`}
          </p>
        )}
      </div>
    </div>
  );
}
