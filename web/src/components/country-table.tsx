"use client";

/** État des pays : snapshot vivant du monde (attributs bougés par les verdicts).
 * Extrait de l'ancienne page /monde — vit désormais sous la scène (G1).
 * CC-15c : « Ta position » et « État des pays » fusionnent ici — ta ligne passe
 * en tête (pastille « toi ») ; vue RÉDUITE par défaut (pays + posture + tendance),
 * les 5 colonnes de chiffres au clic (ou d'office en Expert via defaultDetailed).
 * G9 §4 : badge de posture et sparkline 3 rounds par indice en vue détaillée. */

import { useState } from "react";

import { SpeakerAvatar } from "@/components/avatar";
import { useT } from "@/components/settings-provider";
import { Hint, Pill, type Tone } from "@/components/ui";
import { speakerMeta } from "@/lib/countries";
import { fmt } from "@/lib/format";
import { temperamentMeta } from "@/lib/temperament";
import { countryTrend, type Trend } from "@/lib/trend";

/** Sous-ensemble du dump `CountryState` affiché dans la table d'état. */
export type CountrySnapshot = {
  economy?: { growth?: number };
  political_stability?: number;
  technology_level?: number;
  military?: { projection?: number };
  compute?: number;
  temperament?: string; // G17 — colombe | faucon | opportuniste
};

const COLUMNS: {
  key: string;
  label: string; // clé i18n (table.col.*)
  hint: string; // clé i18n (table.col.*-aide)
  serie: string | null; // label de la série IndexHistory (sparkline), null = pas de série
  value: (c: CountrySnapshot) => number | undefined;
  format: (v: number) => string;
}[] = [
  {
    key: "growth",
    label: "table.col.croissance",
    hint: "table.col.croissance-aide",
    serie: "croissance",
    value: (c) => c.economy?.growth,
    format: (v) => `${fmt(v)} %`,
  },
  {
    key: "stability",
    label: "table.col.stabilite",
    hint: "table.col.stabilite-aide",
    serie: "stabilité",
    value: (c) => c.political_stability,
    format: fmt,
  },
  {
    key: "tech",
    label: "table.col.techno",
    hint: "table.col.techno-aide",
    serie: "techno",
    value: (c) => c.technology_level,
    format: fmt,
  },
  {
    key: "projection",
    label: "table.col.armee",
    hint: "table.col.armee-aide",
    serie: "projection",
    value: (c) => c.military?.projection,
    format: fmt,
  },
  {
    key: "compute",
    label: "table.col.calcul",
    hint: "table.col.calcul-aide",
    serie: null,
    value: (c) => c.compute,
    format: fmt,
  },
];

const POSTURE_TONE: Record<string, Tone> = {
  prospère: "good",
  stable: "neutral",
  sous_pression: "warn",
  aux_abois: "bad",
};

/** Slug de posture (backend) → clé i18n ; un slug inconnu s'affiche brut. */
const POSTURE_KEY: Record<string, string> = {
  prospère: "table.posture.prospere",
  stable: "table.posture.stable",
  sous_pression: "table.posture.sous-pression",
  aux_abois: "table.posture.aux-abois",
};

/** La tendance en un mot (vue réduite) — dérivée des mêmes séries que les sparklines. */
const TREND_VIEW: Record<Trend, { glyph: string; label: string; cls: string }> = {
  up: { glyph: "↗", label: "table.tendance.up", cls: "text-good" },
  flat: { glyph: "→", label: "table.tendance.flat", cls: "text-fg-muted" },
  down: { glyph: "↘", label: "table.tendance.down", cls: "text-bad" },
};

/** Sparkline 3 rounds (4 points) d'un indice — la spirale se voit d'un coup d'œil. */
function Sparkline({ serie }: { serie: number[] }) {
  const points = serie.slice(-4);
  if (points.length < 2) return null;
  const min = Math.min(...points);
  const max = Math.max(...points);
  const span = max - min || 1;
  const w = 40;
  const h = 12;
  const path = points
    .map((v, i) => `${(i / (points.length - 1)) * w},${h - 2 - ((v - min) / span) * (h - 4)}`)
    .join(" ");
  const falling = points[points.length - 1] < points[0];
  return (
    <svg
      width={w}
      height={h}
      viewBox={`0 0 ${w} ${h}`}
      aria-hidden
      className="mt-0.5 block opacity-80"
    >
      <polyline
        points={path}
        fill="none"
        strokeWidth="1.5"
        stroke={falling ? "var(--bad)" : "var(--good)"}
      />
    </svg>
  );
}

export function CountryTable({
  worldCountries,
  postures,
  history,
  playAs = null,
  defaultDetailed = false,
}: {
  worldCountries: Record<string, CountrySnapshot>;
  /** G9 §4 — état de posture par pays (badge sur la fiche). */
  postures?: Record<string, string>;
  /** G9 §4 — séries d'indices par pays (IndexHistory.values) pour sparklines et tendance. */
  history?: Record<string, Record<string, number[]>>;
  /** CC-15c — ton pays : sa ligne passe en tête avec la pastille « toi ». */
  playAs?: string | null;
  /** CC-15c — densité Expert : les 5 colonnes d'office (le bouton bascule toujours). */
  defaultDetailed?: boolean;
}) {
  const t = useT();
  const [detailed, setDetailed] = useState(defaultDetailed);
  const showPosture = postures && Object.keys(postures).length > 0;
  const rows = Object.entries(worldCountries).sort(([a], [b]) => {
    if (playAs) {
      if (a === playAs) return -1;
      if (b === playAs) return 1;
    }
    return a.localeCompare(b);
  });
  return (
    <div className="overflow-x-auto">
      <div className="mb-1 flex justify-end">
        <button
          onClick={() => setDetailed((v) => !v)}
          aria-pressed={detailed}
          className="cursor-pointer text-xs text-fg-faint underline transition-colors hover:text-fg-muted"
        >
          {detailed ? t("table.simple") : t("table.detail")}
        </button>
      </div>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-edge text-left text-xs text-fg-faint">
            <th className="py-2 pr-4 font-medium">{t("table.col.pays")}</th>
            {showPosture && (
              <th className="py-2 pr-4 font-medium">
                <span className="flex items-center gap-1.5">
                  {t("table.col.posture")}
                  <Hint text={t("table.col.posture-aide")} />
                </span>
              </th>
            )}
            {!detailed && (
              <th className="py-2 pr-4 font-medium">
                <span className="flex items-center gap-1.5">
                  {t("table.col.tendance")}
                  <Hint text={t("table.col.tendance-aide")} />
                </span>
              </th>
            )}
            {detailed &&
              COLUMNS.map((col) => (
                <th key={col.key} className="py-2 pr-4 font-medium">
                  <span className="flex items-center gap-1.5">
                    {t(col.label)}
                    <Hint text={t(col.hint)} />
                  </span>
                </th>
              ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-edge">
          {rows.map(([slug, c]) => {
            const you = slug === playAs;
            const trend = TREND_VIEW[countryTrend(history?.[slug])];
            return (
              <tr key={slug} className={you ? "bg-surface-2/50" : undefined}>
                <td className="py-2.5 pr-4">
                  <span className="flex items-center gap-2">
                    <SpeakerAvatar id={slug} size={24} />
                    <span className={you ? "font-medium" : undefined}>
                      {speakerMeta(slug).label}
                    </span>
                    {you && <Pill tone="accent">{t("table.toi")}</Pill>}
                    {c.temperament && (
                      <span
                        role="img"
                        aria-label={t("table.temperament").replace(
                          "{t}",
                          t(`temperament.${temperamentMeta(c.temperament).label}`),
                        )}
                        title={t("table.temperament").replace(
                          "{t}",
                          t(`temperament.${temperamentMeta(c.temperament).label}`),
                        )}
                        className="text-sm"
                      >
                        {temperamentMeta(c.temperament).glyph}
                      </span>
                    )}
                  </span>
                </td>
                {showPosture && (
                  <td className="py-2.5 pr-4">
                    <Pill tone={POSTURE_TONE[postures![slug] ?? "stable"] ?? "neutral"}>
                      {POSTURE_KEY[postures![slug] ?? "stable"]
                        ? t(POSTURE_KEY[postures![slug] ?? "stable"])
                        : postures![slug]}
                    </Pill>
                  </td>
                )}
                {!detailed && (
                  <td className={`py-2.5 pr-4 text-xs ${trend.cls}`}>
                    <span aria-hidden>{trend.glyph}</span> {t(trend.label)}
                  </td>
                )}
                {detailed &&
                  COLUMNS.map((col) => {
                    const v = col.value(c);
                    const serie = col.serie ? history?.[slug]?.[col.serie] : undefined;
                    return (
                      <td
                        key={col.key}
                        className="py-2.5 pr-4 font-mono text-xs tabular-nums text-fg-muted"
                      >
                        {v === undefined ? "—" : col.format(v)}
                        {serie && <Sparkline serie={serie} />}
                      </td>
                    );
                  })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
