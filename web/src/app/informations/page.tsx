"use client";

/** Informations : d'où vient chaque attribut de chaque pays. Relit la chaîne de
 * provenance P4 (`GET /api/sources`) — indicateurs bruts sourcés, transformations
 * documentées, valeurs jeu issues du build reproductible. */

import { useEffect, useState } from "react";

import { SpeakerAvatar } from "@/components/avatar";
import { Banner, Hint, Panel, PanelTitle, Pill, Spinner, type Tone } from "@/components/ui";
import { getSources, humanizeError } from "@/lib/api";
import { fmt } from "@/lib/format";
import type { AttributeSource, SourceInfo, SourcesView } from "@/lib/types";

/** « World Bank — GDP (current US$) … » → « World Bank » (le détail passe en infobulle). */
const shortSource = (s: string) => s.split(" — ")[0].split(" (")[0];

function sourceTag(info?: SourceInfo): { tone: Tone; label: string } {
  if (!info) return { tone: "neutral", label: "non renseignée" };
  if (info.note === "subjectif") return { tone: "warn", label: "estimation analyste" };
  if (info.note === "illustratif") return { tone: "warn", label: "illustratif" };
  if (info.note === "dérivé") return { tone: "neutral", label: "dérivé" };
  return { tone: "good", label: "sourcé" };
}

function money(v: number): string {
  if (v >= 1e12) return `${fmt(v / 1e12)} T$`;
  if (v >= 1e9) return `${fmt(v / 1e9)} Md$`;
  return `${fmt(v)} $`;
}

function gameValue(row: AttributeSource): string {
  if (typeof row.game_value === "boolean") return row.game_value ? "Oui" : "Non";
  if (row.raw_unit === "USD") return money(row.game_value);
  if (row.label === "Croissance") return `${fmt(row.game_value)} %`;
  return fmt(row.game_value);
}

function rawValue(row: AttributeSource): string | null {
  if (row.raw_value == null || typeof row.raw_value === "boolean") return null;
  return `${fmt(row.raw_value)} ${row.raw_unit}`.trim();
}

export default function InformationsPage() {
  const [view, setView] = useState<SourcesView | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getSources()
      .then(setView)
      .catch((err) => setError(humanizeError(err)));
  }, []);

  return (
    <div className="space-y-6">
      <section className="max-w-3xl">
        <h1 className="text-2xl font-semibold tracking-tight">D&apos;où viennent les chiffres</h1>
        <p className="mt-2 text-sm leading-relaxed text-fg-muted">
          Les attributs de chaque pays ne sont pas inventés : ils sont construits depuis des
          indicateurs réels sourcés (Banque mondiale, FMI, SIPRI, WIPO…), normalisés par des
          formules documentées, puis figés dans des profils versionnés. Le build est
          reproductible : {view ? <code className="rounded bg-surface-2 px-1.5 py-0.5 font-mono text-xs">{view.build_command}</code> : "…"}{" "}
          vérifie que chaque profil committé se re-dérive exactement des sources.
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          <Pill tone="good">sourcé — indicateur réel daté</Pill>
          <Pill tone="neutral">dérivé — calculé depuis un indicateur réel</Pill>
          <Pill tone="warn">estimation analyste / illustratif — assumé comme tel</Pill>
        </div>
      </section>

      {error && <Banner tone="bad">{error}</Banner>}
      {!error && !view && (
        <p className="flex items-center gap-2 text-sm text-fg-muted">
          <Spinner /> Chargement des sources…
        </p>
      )}

      {view && (
        <>
          <Panel>
            <PanelTitle
              kicker="Provenance"
              title="Sources des indicateurs"
              hint="Un indicateur = une source datée. Les transformations vers les indices 0-1 du jeu sont listées avec chaque attribut concerné."
            />
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-edge text-left text-xs text-fg-faint">
                    <th className="py-2 pr-4 font-medium">Indicateur</th>
                    <th className="py-2 pr-4 font-medium">Source</th>
                    <th className="py-2 pr-4 font-medium">Année</th>
                    <th className="py-2 font-medium">Nature</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-edge">
                  {Object.entries(view.provenance).map(([key, info]) => {
                    const tag = sourceTag(info);
                    return (
                      <tr key={key}>
                        <td className="py-2 pr-4 font-mono text-xs text-fg-muted">{key}</td>
                        <td className="py-2 pr-4">{info.source}</td>
                        <td className="py-2 pr-4 font-mono text-xs tabular-nums text-fg-faint">
                          {info.year ?? "—"}
                        </td>
                        <td className="py-2">
                          <Pill tone={tag.tone}>{tag.label}</Pill>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </Panel>

          <div className="grid gap-6 lg:grid-cols-2">
            {view.countries.map((country) => (
              <Panel key={country.id}>
                <header className="mb-3 flex items-center gap-3">
                  <SpeakerAvatar id={country.id} size={30} />
                  <h2 className="text-sm font-semibold">{country.name}</h2>
                </header>
                <table className="w-full text-sm">
                  <tbody className="divide-y divide-edge">
                    {country.attributes.map((row) => {
                      const info = row.key ? view.provenance[row.key] : undefined;
                      const tag = sourceTag(info);
                      const raw = rawValue(row);
                      return (
                        <tr key={row.label}>
                          <td className="py-1.5 pr-3 text-fg-muted">
                            <span className="flex items-center gap-1.5">
                              {row.label}
                              {row.transformation && (
                                <Hint
                                  text={`Formule : ${view.transformations[row.transformation] ?? row.transformation}`}
                                />
                              )}
                            </span>
                          </td>
                          <td className="py-1.5 pr-3 text-right font-mono text-xs tabular-nums">
                            {gameValue(row)}
                          </td>
                          <td className="py-1.5 pr-3 text-right font-mono text-[10px] tabular-nums text-fg-faint">
                            {raw ? `← ${raw}` : ""}
                          </td>
                          <td className="py-1.5 text-right">
                            <span
                              title={
                                info
                                  ? `${info.source}${info.year ? ` (${info.year})` : ""}`
                                  : "source non renseignée"
                              }
                              className="cursor-help"
                            >
                              <Pill tone={tag.tone}>
                                {info ? shortSource(info.source) : "—"}
                              </Pill>
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
                <p className="mt-3 border-t border-edge pt-3 text-xs leading-relaxed text-fg-faint">
                  Profil qualitatif (analyste) : {country.profile.political_system ?? "?"} ·
                  alliances {country.profile.alliances?.join(", ") || "—"} · rivaux{" "}
                  {country.profile.rivals?.join(", ") || "—"} · priorités{" "}
                  {country.profile.strategic_priorities?.join(", ") || "—"}
                </p>
              </Panel>
            ))}
          </div>

          <Banner tone="neutral">
            Les pays <strong>inventés</strong>{" "}
            en partie (« Inventer mon propre pays ») sont forgés par le modèle et bornés par
            le moteur : ils n&apos;ont pas de source réelle — c&apos;est assumé, ils
            n&apos;apparaissent pas sur cette page ni sur la carte.
          </Banner>
        </>
      )}
    </div>
  );
}
