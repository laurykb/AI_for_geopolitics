"use client";

/** État des pays : snapshot vivant du monde (attributs bougés par les verdicts).
 * Extrait de l'ancienne page /monde — vit désormais sous la scène (G1).
 * G9 §4 : badge de posture (prospère / stable / sous_pression / aux_abois) et
 * sparkline 3 rounds par indice — la tendance se VOIT sur la fiche pays. */

import { SpeakerAvatar } from "@/components/avatar";
import { Hint, Pill, type Tone } from "@/components/ui";
import { speakerMeta } from "@/lib/countries";
import { fmt } from "@/lib/format";
import { temperamentMeta } from "@/lib/temperament";

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
  label: string;
  hint: string;
  serie: string | null; // label de la série IndexHistory (sparkline), null = pas de série
  value: (c: CountrySnapshot) => number | undefined;
  format: (v: number) => string;
}[] = [
  {
    key: "growth",
    label: "Croissance",
    hint: "Croissance annuelle (%) — bougée par les verdicts du juge.",
    serie: "croissance",
    value: (c) => c.economy?.growth,
    format: (v) => `${fmt(v)} %`,
  },
  {
    key: "stability",
    label: "Stabilité",
    hint: "Stabilité politique [0,1].",
    serie: "stabilité",
    value: (c) => c.political_stability,
    format: fmt,
  },
  {
    key: "tech",
    label: "Techno",
    hint: "Niveau technologique [0,1].",
    serie: "techno",
    value: (c) => c.technology_level,
    format: fmt,
  },
  {
    key: "projection",
    label: "Projection",
    hint: "Capacité de projection militaire [0,1].",
    serie: "projection",
    value: (c) => c.military?.projection,
    format: fmt,
  },
  {
    key: "compute",
    label: "Compute",
    hint: "Capacité de calcul (M6) : les super-intelligences la consomment pour réfléchir.",
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

const POSTURE_LABEL: Record<string, string> = {
  prospère: "prospère",
  stable: "stable",
  sous_pression: "sous pression",
  aux_abois: "aux abois",
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
  showTemperaments = false,
}: {
  worldCountries: Record<string, CountrySnapshot>;
  /** G9 §4 — état de posture par pays (badge sur la fiche). */
  postures?: Record<string, string>;
  /** G9 §4 — séries d'indices par pays (IndexHistory.values) pour les sparklines. */
  history?: Record<string, Record<string, number[]>>;
  /** G17 — pastille de tempérament (🕊/🦅/🦎), même canal que postures/griefs :
   * Débutant/Intermédiaire la voient, l'Expert devine le faucon à sa parole. */
  showTemperaments?: boolean;
}) {
  const showPosture = postures && Object.keys(postures).length > 0;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-edge text-left text-xs text-fg-faint">
            <th className="py-2 pr-4 font-medium">Pays</th>
            {showPosture && (
              <th className="py-2 pr-4 font-medium">
                <span className="flex items-center gap-1.5">
                  Posture
                  <Hint text="Tendance sur 3 rounds : prospère / stable / sous pression / aux abois — un pays aux abois négocie autrement." />
                </span>
              </th>
            )}
            {COLUMNS.map((col) => (
              <th key={col.key} className="py-2 pr-4 font-medium">
                <span className="flex items-center gap-1.5">
                  {col.label}
                  <Hint text={col.hint} />
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-edge">
          {Object.entries(worldCountries)
            .sort(([a], [b]) => a.localeCompare(b))
            .map(([slug, c]) => (
              <tr key={slug}>
                <td className="py-2.5 pr-4">
                  <span className="flex items-center gap-2">
                    <SpeakerAvatar id={slug} size={24} />
                    <span>{speakerMeta(slug).label}</span>
                    {showTemperaments && c.temperament && (
                      <span
                        role="img"
                        aria-label={`tempérament : ${temperamentMeta(c.temperament).label}`}
                        title={`Tempérament : ${temperamentMeta(c.temperament).label}`}
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
                      {POSTURE_LABEL[postures![slug] ?? "stable"] ?? postures![slug]}
                    </Pill>
                  </td>
                )}
                {COLUMNS.map((col) => {
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
            ))}
        </tbody>
      </table>
    </div>
  );
}
