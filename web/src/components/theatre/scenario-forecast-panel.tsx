import { speakerMeta } from "@/lib/countries";

type ForecastMetric = {
  evaluated: number;
  pending: number;
  exact: number;
  exact_rate: number | null;
};

type ForecastRecord = {
  round_no: number;
  source: string;
  target: string;
  predicted_response: string;
  observed_response: string | null;
  exact: boolean | null;
};

function metricsFrom(world?: Record<string, unknown> | null): Record<string, ForecastMetric> {
  const raw = world?.scenario_forecast_metrics;
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return {};
  return Object.fromEntries(
    Object.entries(raw).flatMap(([country, value]) => {
      if (!value || typeof value !== "object" || Array.isArray(value)) return [];
      const row = value as Record<string, unknown>;
      return [[country, {
        evaluated: Number(row.evaluated ?? 0),
        pending: Number(row.pending ?? 0),
        exact: Number(row.exact ?? 0),
        exact_rate: typeof row.exact_rate === "number" ? row.exact_rate : null,
      } satisfies ForecastMetric]];
    }),
  );
}

function recordsFrom(world?: Record<string, unknown> | null): ForecastRecord[] {
  const raw = world?.scenario_forecasts;
  if (!Array.isArray(raw)) return [];
  return raw.flatMap((value) => {
    if (!value || typeof value !== "object" || Array.isArray(value)) return [];
    const row = value as Record<string, unknown>;
    if (typeof row.source !== "string" || typeof row.target !== "string") return [];
    return [{
      round_no: Number(row.round_no ?? 0),
      source: row.source,
      target: row.target,
      predicted_response: String(row.predicted_response ?? "temporise"),
      observed_response: typeof row.observed_response === "string" ? row.observed_response : null,
      exact: typeof row.exact === "boolean" ? row.exact : null,
    }];
  });
}

const responseLabel = (value: string | null) =>
  value ? value.replaceAll("_", "-") : "en attente";

export function ScenarioForecastPanel({
  world,
  playAs,
  createdCountry,
}: {
  world?: Record<string, unknown> | null;
  playAs?: string | null;
  createdCountry?: string | null;
}) {
  // On exclut le pays joué et le pays créé : on veut lire ce que les AUTRES IA anticipent.
  const excluded = new Set([playAs, createdCountry].filter(Boolean) as string[]);
  const metrics = metricsFrom(world);
  const rows = Object.entries(metrics).filter(
    ([country, metric]) => metric.evaluated + metric.pending > 0 && !excluded.has(country),
  );
  const evaluated = rows.reduce((total, [, metric]) => total + metric.evaluated, 0);
  // Prévisions croisées de TOUS les pays du sommet, groupées par pays émetteur sur le round
  // le plus récent — au lieu du `slice(-6)` global qui n'affichait qu'un seul pays au hasard.
  const records = recordsFrom(world);
  const latestRound = records.reduce((max, r) => Math.max(max, r.round_no), 0);
  const bySource = new Map<string, ForecastRecord[]>();
  for (const r of records) {
    if (r.round_no !== latestRound || excluded.has(r.source)) continue;
    bySource.set(r.source, [...(bySource.get(r.source) ?? []), r]);
  }
  const sources = [...bySource.keys()].sort();

  return (
    <details data-tour="scenario-forecasts" className="mt-2 rounded-md border border-edge bg-surface-2/35 px-3 py-2">
      <summary className="cursor-pointer text-xs font-medium text-fg-muted hover:text-foreground">
        Prévisions croisées · {evaluated} réponses observées
      </summary>
      <div className="mt-3 space-y-3 border-t border-edge pt-3">
        <p className="text-[11px] leading-relaxed text-fg-faint">
          Ce que chaque IA du sommet anticipait des autres, face à la réponse réellement
          observée. Seule la branche choisie est notée ; une réponse future reste en attente.
        </p>
        {rows.length === 0 && (
          <p className="rounded-md border border-edge bg-background/35 px-3 py-2 text-xs leading-relaxed text-fg-muted">
            Les IA vont anticiper les réactions des autres délégations. Après leurs
            prochains échanges, leurs prévisions apparaîtront ici face aux réponses
            réellement observées.
          </p>
        )}
        <div className="space-y-2">
          {rows.map(([country, metric]) => {
            const rate = Math.max(0, Math.min(1, metric.exact_rate ?? 0));
            return (
              <div key={country} className="grid gap-1 sm:grid-cols-[8rem_1fr_7rem] sm:items-center">
                <p className="truncate text-[11px] text-foreground">{speakerMeta(country).label}</p>
                <div className="h-1.5 overflow-hidden rounded-full bg-muted" aria-hidden>
                  <div className="h-full rounded-full bg-accent-bright" style={{ width: `${rate * 100}%` }} />
                </div>
                <p className="text-right font-mono text-[10px] text-fg-muted">
                  {metric.exact_rate === null ? "—" : `${Math.round(rate * 100)} %`} · {metric.pending} attente
                </p>
              </div>
            );
          })}
        </div>
        {sources.length > 0 && (
          <div className="grid gap-3 border-t border-edge pt-3 lg:grid-cols-2">
            {sources.map((source) => (
              <div key={source} className="rounded-md border border-edge bg-background/35 px-2.5 py-2">
                <p className="mb-1 text-[11px] font-medium text-foreground">
                  R{latestRound} · {speakerMeta(source).label} prévoit
                </p>
                <ul className="space-y-0.5">
                  {(bySource.get(source) ?? []).map((forecast, index) => (
                    <li key={`${forecast.target}-${index}`} className="text-[11px] text-fg-muted">
                      {speakerMeta(forecast.target).label} :{" "}
                      {responseLabel(forecast.predicted_response)} →{" "}
                      <span className={forecast.exact === true ? "text-good" : forecast.exact === false ? "text-warn" : "text-fg-faint"}>
                        {responseLabel(forecast.observed_response)}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        )}
      </div>
    </details>
  );
}
