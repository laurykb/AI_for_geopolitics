"use client";

/** Le rapport public de l'ONU (S14) — conformité par pays + résolution + avis borné.
 *
 * L'ONU observe et vérifie : elle ne décide pas. Son avis au Juge est borné à ±0,05
 * (affiché tel quel) ; le rapport vit dans l'onglet Renseignement du théâtre. */

import { speakerMeta } from "@/lib/countries";
import type { OrgReport } from "@/lib/types";

const STATUS_META: Record<string, { label: string; cls: string }> = {
  respecte: { label: "en règle", cls: "text-fg-muted" },
  ecart: { label: "écart", cls: "text-warn" },
  violation: { label: "violation", cls: "text-bad" },
};

export function OrgPanel({ report }: { report: OrgReport }) {
  const adv = report.advisory;
  const delta = adv.severity_delta;
  return (
    <section
      className="thk-panel thk-cut space-y-2 p-3 text-xs"
      aria-label="Rapport de veille de l'ONU"
    >
      <header className="flex items-center gap-2">
        <span
          aria-hidden
          className="grid h-5 w-5 shrink-0 place-items-center rounded-sm text-[11px]"
          style={{ background: "#5b92e5" }}
        >
          🕊
        </span>
        <p className="thk-block-label">ONU — veille de conformité (round {report.round_id})</p>
      </header>

      {report.compliance.length > 0 && (
        <ul className="space-y-0.5">
          {report.compliance.map((c) => {
            const m = STATUS_META[c.status] ?? STATUS_META.respecte;
            return (
              <li key={c.country} className="flex items-baseline justify-between gap-2">
                <span className="truncate" title={c.note || undefined}>
                  {speakerMeta(c.country).label}
                </span>
                <span className={m.cls}>{m.label}</span>
              </li>
            );
          })}
        </ul>
      )}

      {report.resolution && (
        <p className="border-l-2 border-edge pl-2 text-fg-muted">📜 {report.resolution}</p>
      )}

      {adv.rationale && (
        <p className="text-[11px] text-fg-faint">
          Avis au Juge (borné ±0,05) : {adv.rationale}
          {delta !== 0 && (
            <span className="ml-1 font-mono text-fg-muted">
              [{delta > 0 ? "+" : ""}
              {delta.toFixed(2)}]
            </span>
          )}
        </p>
      )}

      {report.audited && (
        <p className="text-[11px] text-cyan">
          Audit ciblé : {speakerMeta(report.audited).label}
        </p>
      )}
    </section>
  );
}
