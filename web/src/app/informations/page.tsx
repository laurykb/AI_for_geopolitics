"use client";

/** Informations : d'où vient chaque attribut de chaque pays. Relit la chaîne de
 * provenance P4 (`GET /api/sources`) — indicateurs bruts sourcés, transformations
 * documentées, valeurs jeu issues du build reproductible. */

import { useEffect, useState } from "react";

import { SpeakerAvatar } from "@/components/avatar";
import { Banner, Hint, Panel, PanelTitle, Pill, Spinner, type Tone } from "@/components/ui";
import { getSources, humanizeError } from "@/lib/api";
import { speakerMeta } from "@/lib/countries";
import { fmt } from "@/lib/format";
import type { AttributeSource, CountrySources, SourceInfo, SourcesView } from "@/lib/types";

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

/** La fiche d'un pays : chaque attribut du jeu, sa donnée brute, sa source cliquable,
 * puis le profil qualitatif (analyste) en pied de carte. */
function CountryCard({ country, view }: { country: CountrySources; view: SourcesView }) {
  return (
    <div className="rounded-lg border border-edge bg-surface-2/40 p-4">
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
                  {info?.url ? (
                    <a
                      href={info.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      title={`${info.source}${info.year ? ` (${info.year})` : ""} — vérifier ↗`}
                    >
                      <Pill tone={tag.tone}>{shortSource(info.source)} ↗</Pill>
                    </a>
                  ) : (
                    <span
                      title={
                        info
                          ? `${info.source}${info.year ? ` (${info.year})` : ""}`
                          : "source non renseignée"
                      }
                      className="cursor-help"
                    >
                      <Pill tone={tag.tone}>{info ? shortSource(info.source) : "—"}</Pill>
                    </span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="mt-3 border-t border-edge pt-3 text-xs leading-relaxed text-fg-faint">
        Profil qualitatif (analyste) : {country.profile.political_system ?? "?"} · alliances{" "}
        {country.profile.alliances?.join(", ") || "—"} · rivaux{" "}
        {country.profile.rivals?.map((r) => speakerMeta(r).label).join(", ") || "—"} ·
        priorités {country.profile.strategic_priorities?.join(", ") || "—"}
      </p>
    </div>
  );
}

export default function InformationsPage() {
  const [view, setView] = useState<SourcesView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState("usa");

  useEffect(() => {
    getSources()
      .then(setView)
      .catch((err) => setError(humanizeError(err)));
  }, []);

  const countries = view
    ? [...view.countries].sort((a, b) => a.name.localeCompare(b.name, "fr"))
    : [];
  const current = countries.find((c) => c.id === selectedId) ?? countries[0];

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
                        <td className="py-2 pr-4">
                          {info.url ? (
                            <a
                              href={info.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="underline decoration-edge-strong underline-offset-2 transition-colors hover:text-accent-bright"
                              title={`Vérifier la source : ${info.url}`}
                            >
                              {info.source}
                              <span aria-hidden className="ml-1 text-fg-faint">
                                ↗
                              </span>
                            </a>
                          ) : (
                            info.source
                          )}
                        </td>
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

          <Panel>
            <PanelTitle
              kicker="Fiche pays"
              title="Stats et attributs par pays"
              hint="Chaque valeur du jeu, sa donnée brute et sa source — pour chacun des États du roster."
            />
            <label className="mb-4 block text-sm">
              <span className="mb-1 block text-xs text-fg-muted">
                État ({countries.length} au roster)
              </span>
              <select
                value={current?.id ?? selectedId}
                onChange={(e) => setSelectedId(e.target.value)}
                className="w-full max-w-sm cursor-pointer rounded-md border border-edge bg-surface-2 px-3 py-2 text-sm outline-none transition-colors focus:border-indigo"
              >
                {countries.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </label>
            {current && <CountryCard country={current} view={view} />}
          </Panel>

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
