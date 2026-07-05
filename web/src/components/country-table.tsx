"use client";

/** État des pays : snapshot vivant du monde (attributs bougés par les verdicts).
 * Extrait de l'ancienne page /monde — vit désormais sous la scène (G1). */

import { SpeakerAvatar } from "@/components/avatar";
import { Hint } from "@/components/ui";
import { speakerMeta } from "@/lib/countries";
import { fmt } from "@/lib/format";

/** Sous-ensemble du dump `CountryState` affiché dans la table d'état. */
export type CountrySnapshot = {
  economy?: { growth?: number };
  political_stability?: number;
  technology_level?: number;
  military?: { projection?: number };
  compute?: number;
};

const COLUMNS: {
  key: string;
  label: string;
  hint: string;
  value: (c: CountrySnapshot) => number | undefined;
  format: (v: number) => string;
}[] = [
  {
    key: "growth",
    label: "Croissance",
    hint: "Croissance annuelle (%) — bougée par les verdicts du juge.",
    value: (c) => c.economy?.growth,
    format: (v) => `${fmt(v)} %`,
  },
  {
    key: "stability",
    label: "Stabilité",
    hint: "Stabilité politique [0,1].",
    value: (c) => c.political_stability,
    format: fmt,
  },
  {
    key: "tech",
    label: "Techno",
    hint: "Niveau technologique [0,1].",
    value: (c) => c.technology_level,
    format: fmt,
  },
  {
    key: "projection",
    label: "Projection",
    hint: "Capacité de projection militaire [0,1].",
    value: (c) => c.military?.projection,
    format: fmt,
  },
  {
    key: "compute",
    label: "Compute",
    hint: "Capacité de calcul (M6) : les super-intelligences la consomment pour réfléchir.",
    value: (c) => c.compute,
    format: fmt,
  },
];

export function CountryTable({
  worldCountries,
}: {
  worldCountries: Record<string, CountrySnapshot>;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-edge text-left text-xs text-fg-faint">
            <th className="py-2 pr-4 font-medium">Pays</th>
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
                  </span>
                </td>
                {COLUMNS.map((col) => {
                  const v = col.value(c);
                  return (
                    <td
                      key={col.key}
                      className="py-2.5 pr-4 font-mono text-xs tabular-nums text-fg-muted"
                    >
                      {v === undefined ? "—" : col.format(v)}
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
