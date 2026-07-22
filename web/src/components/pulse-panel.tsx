"use client";

/** Le Pouls du monde (S15) — les dépêches autonomes tombées ce round.
 *
 * Chocs (séisme, krach, cyber…) et aubaines (manne, percée) qui frappent les stats
 * des pays joués, indépendamment du Game Master. Style hors-récit, bref. */

import { speakerMeta } from "@/lib/countries";
import type { PulseEvent } from "@/lib/types";

export function PulsePanel({ events }: { events: PulseEvent[] }) {
  if (events.length === 0) return null;
  return (
    <section className="thk-panel thk-cut space-y-1.5 p-3 text-xs" aria-label="Pouls du monde">
      <p className="thk-block-label">🌐 Pouls du monde</p>
      <ul className="space-y-0.5">
        {events.map((e, i) => (
          <li key={`${e.country}-${i}`} className="flex items-baseline justify-between gap-2">
            <span className="min-w-0 truncate">
              <span aria-hidden>{e.boon ? "▲" : "▼"}</span> {e.label}
              <span className="text-fg-faint"> — {speakerMeta(e.country).label}</span>
            </span>
            <span className={e.boon ? "shrink-0 text-cyan" : "shrink-0 text-bad"}>
              {e.boon ? "aubaine" : "choc"}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
