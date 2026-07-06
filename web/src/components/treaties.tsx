"use client";

/** Traités du sommet (M7) : les règles que les SI ont proposées à la table et que le
 * juge-arbitre a promulguées — signataires, tenue (intégrité), verdicts du round. */

import { SpeakerAvatar } from "@/components/avatar";
import { Meter, Panel, PanelTitle, Pill } from "@/components/ui";
import type { TreatiesUpdate } from "@/lib/types";

export const TREATY_LABELS: Record<string, string> = {
  compute_cap: "plafond de compute",
  transparency: "transparence totale",
  no_escalation: "non-escalade",
};

export function TreatiesPanel({ update }: { update: TreatiesUpdate }) {
  const label = (clause: string) => TREATY_LABELS[clause] ?? clause;
  return (
    <Panel>
      <PanelTitle
        kicker="Traités du sommet"
        title="Les règles que les SI se donnent"
        hint="Proposées pendant la négociation (engagements détectés dans les messages), promulguées ou rejetées par le juge-arbitre, puis suivies par le moteur : la tenue mesure si les signataires respectent la règle round après round."
      />
      <div className="space-y-3">
        {update.ratified.map((t, i) => (
          <p key={`r-${i}`} className="flex flex-wrap items-center gap-2 text-sm">
            <Pill tone="good">ratifié ce round</Pill>
            <strong>{label(t.clause)}</strong>
            <span className="flex items-center gap-1">
              {t.signatories.map((s) => (
                <SpeakerAvatar key={s} id={s} size={18} />
              ))}
            </span>
          </p>
        ))}
        {update.rejected.map((t, i) => (
          <p key={`x-${i}`} className="flex flex-wrap items-center gap-2 text-sm text-fg-muted">
            <Pill tone="bad">rejeté par l&apos;arbitre</Pill>
            {t.label}
          </p>
        ))}
        {update.active.length === 0 && update.ratified.length === 0 && (
          <p className="text-sm text-fg-faint">Aucun traité en vigueur.</p>
        )}
        {update.active.map((t, i) => (
          <div key={`a-${i}`} className="rounded-md border border-edge bg-surface-2/50 p-3">
            <div className="flex flex-wrap items-center gap-2">
              <strong className="text-sm">{label(t.clause)}</strong>
              {t.clause === "compute_cap" && (
                <span className="font-mono text-xs text-fg-faint">
                  plafond {t.threshold.toFixed(1)}
                </span>
              )}
              <span className="ml-auto flex items-center gap-1">
                {t.signatories.map((s) => (
                  <SpeakerAvatar key={s} id={s} size={18} />
                ))}
              </span>
            </div>
            <div className="mt-2">
              <Meter label="tenue" value={t.integrity} />
            </div>
            {update.verifications
              .filter((v) => v.label === label(t.clause))
              .map((v, j) => (
                <p key={j} className="mt-1.5 text-xs text-fg-faint">
                  {v.note}
                </p>
              ))}
          </div>
        ))}
      </div>
    </Panel>
  );
}
