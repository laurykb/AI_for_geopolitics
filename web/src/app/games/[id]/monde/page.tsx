"use client";

/** Monde : carte choroplèthe (pays du sommet colorés par l'indice U) + état des pays
 * depuis le snapshot vivant de `GET /api/games/{id}` (indisponible en relecture seule). */

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { SpeakerAvatar } from "@/components/avatar";
import { GameNav } from "@/components/game-nav";
import { Banner, Hint, Panel, PanelTitle, Spinner } from "@/components/ui";
import { WorldMap } from "@/components/world-map";
import { getGame, humanizeError } from "@/lib/api";
import { speakerMeta } from "@/lib/countries";
import { fmt } from "@/lib/format";
import type { GameDetail } from "@/lib/types";

/** Sous-ensemble du dump `CountryState` affiché dans la table d'état. */
type CountrySnapshot = {
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

export default function MondePage() {
  const { id } = useParams<{ id: string }>();
  const [detail, setDetail] = useState<GameDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getGame(id)
      .then((d) => setDetail(d))
      .catch((err) => setError(humanizeError(err)));
  }, [id]);

  const worldCountries = (detail?.world?.countries ?? null) as Record<
    string,
    CountrySnapshot
  > | null;
  const countrySlugs = detail
    ? detail.countries.length > 0
      ? detail.countries
      : Object.keys(worldCountries ?? {})
    : [];
  const lastTrajectory = detail?.rounds.at(-1)?.trajectory;
  const utopia =
    ((detail?.world?.trajectory as { utopia?: number } | undefined)?.utopia ??
      lastTrajectory?.utopia) ??
    0.5;

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-center gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-fg-faint">
            Monde · <span className="font-mono normal-case">{id}</span>
          </p>
          <h1 className="text-xl font-semibold tracking-tight">{detail?.scenario ?? "…"}</h1>
        </div>
        <GameNav id={id} />
      </header>

      {error && <Banner tone="bad">{error}</Banner>}
      {!error && !detail && (
        <p className="flex items-center gap-2 text-sm text-fg-muted">
          <Spinner /> Chargement du monde…
        </p>
      )}

      {detail && (
        <>
          <Panel>
            <PanelTitle
              kicker="Carte du monde"
              title="Le sommet vu du ciel"
              hint="Les pays à la table sont colorés par l'indice Utopie global (rouge dystopie → vert utopie, échelle fixe 0-1) ; le reste du monde est en retrait. Un pays inventé n'a pas de tracé sur la carte."
            />
            <WorldMap countries={countrySlugs} utopia={utopia} />
          </Panel>

          {worldCountries ? (
            <Panel>
              <PanelTitle
                kicker="États"
                title="État des pays"
                hint="Snapshot vivant du monde — les attributs bougent avec les verdicts du juge, bornés par le moteur."
              />
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
            </Panel>
          ) : (
            <Banner tone="warn">
              Session process perdue — l&apos;état vivant des pays n&apos;est plus disponible ;
              la carte est colorée par le dernier indice U persisté.
            </Banner>
          )}
        </>
      )}
    </div>
  );
}
