"use client";

import type { AttributeDelta } from "@/lib/types";
import { speakerMeta } from "@/lib/countries";

export function RoundConclusion({
  roundNo,
  horizon,
  eventTitle,
  deltas,
  motionUpheld,
  busy,
  onContinue,
}: {
  roundNo: number;
  horizon: number;
  eventTitle?: string;
  deltas: AttributeDelta[];
  motionUpheld?: boolean;
  busy: boolean;
  onContinue: () => void;
}) {
  const remaining = Math.max(0, horizon - roundNo);

  return (
    <section
      data-tour="round-conclusion"
      aria-labelledby="round-conclusion-title"
      className="rise-in overflow-hidden rounded-xl border border-accent/50 bg-[linear-gradient(135deg,rgba(202,138,4,0.13),rgba(13,18,38,0.96)_48%)] p-5 shadow-[0_24px_80px_-44px_rgba(234,179,8,0.8)]"
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="max-w-2xl">
          <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-accent-bright">
            Conséquences enregistrées
          </p>
          <h2 id="round-conclusion-title" className="mt-1 text-lg font-semibold">
            Round {roundNo} terminé
          </h2>
          <p className="mt-1 text-sm leading-relaxed text-fg-muted">
            {eventTitle ? `« ${eventTitle} » est tranché.` : "Le verdict est rendu."} {" "}
            {deltas.length > 0
              ? `${deltas.length} évolution${deltas.length > 1 ? "s" : ""} ont été appliquées au monde.`
              : "Le monde reste stable pour ce round."}
            {motionUpheld === true && " La motion a été retenue."}
            {motionUpheld === false && " La motion a été rejetée."}
          </p>
        </div>
        <div className="rounded-lg border border-edge bg-surface/70 px-3 py-2 text-right">
          <p className="font-mono text-lg font-semibold tabular-nums text-foreground">{remaining}</p>
          <p className="text-[10px] uppercase tracking-[0.12em] text-fg-faint">
            round{remaining > 1 ? "s" : ""} restant{remaining > 1 ? "s" : ""}
          </p>
        </div>
      </div>

      {deltas.length > 0 && (
        <ul className="mt-4 grid gap-2 sm:grid-cols-2" aria-label="Principales conséquences">
          {deltas.slice(0, 4).map((delta, index) => {
            const change = delta.after - delta.before;
            return (
              <li
                key={`${delta.country}-${delta.label}-${index}`}
                className="flex items-center justify-between gap-3 rounded-lg border border-edge bg-surface/55 px-3 py-2 text-xs"
              >
                <span className="min-w-0">
                  <strong className="block truncate text-foreground">
                    {speakerMeta(delta.country).label}
                  </strong>
                  <span className="truncate text-fg-faint">{delta.label}</span>
                </span>
                <span
                  className={`font-mono tabular-nums ${
                    change > 0 ? "text-utopia" : change < 0 ? "text-dystopia" : "text-fg-muted"
                  }`}
                >
                  {change > 0 ? "+" : ""}{change.toFixed(2)}
                </span>
              </li>
            );
          })}
        </ul>
      )}

      <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-edge pt-4">
        <p className="text-xs text-fg-faint">
          Tu peux relire les prises de parole ou poursuivre immédiatement le sommet.
        </p>
        <button
          data-tour="next-round"
          onClick={onContinue}
          disabled={busy}
          className="flex min-w-52 cursor-pointer items-center justify-center rounded-lg bg-accent px-5 py-3 text-sm font-semibold text-background transition-colors hover:bg-accent-bright disabled:cursor-not-allowed disabled:opacity-50"
        >
          {busy ? "Préparation…" : "Continuer la partie →"}
        </button>
      </div>
    </section>
  );
}
