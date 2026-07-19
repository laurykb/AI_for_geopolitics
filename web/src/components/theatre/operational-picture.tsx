"use client";

import { Pill } from "@/components/ui";
import { speakerMeta } from "@/lib/countries";
import type { OperationalPicture } from "@/lib/types";

const actionLabel = (value: string) =>
  value
    .replace("motion_vote:pour", "vote pour la motion")
    .replace("motion_vote:contre", "vote contre la motion")
    .replace("motion_vote:abstention", "abstention sur la motion")
    .replace("intel:", "renseignement · ")
    .replaceAll("_", " ");

export function OperationalPicturePanel({ picture }: { picture?: OperationalPicture }) {
  if (!picture || picture.objects.length === 0) return null;
  const countries = picture.objects.filter((item) => item.kind === "country").length;
  const events = picture.objects.filter((item) => item.kind === "event").length;
  const commitments = picture.objects.filter(
    (item) => item.kind === "promise" || item.kind === "treaty",
  ).length;
  const latest = picture.actions.slice(-5).reverse();

  return (
    <details className="rounded-lg border border-edge bg-surface/75 p-3">
      <summary className="cursor-pointer select-none text-xs font-semibold text-foreground">
        Image opérationnelle
        <span className="ml-2 font-normal text-fg-faint">
          graphe auditable · R{picture.generated_round}
        </span>
      </summary>
      <p className="mt-2 text-[11px] leading-relaxed text-fg-faint">
        Une vue commune relie les faits, les engagements et les décisions. Chaque élément garde
        sa provenance ; une confiance faible reste visible comme telle.
      </p>
      <div className="mt-3 grid grid-cols-3 gap-2 text-center">
        {[
          [countries, "pays"],
          [events, "événements"],
          [commitments, "engagements"],
        ].map(([value, label]) => (
          <div
            key={String(label)}
            className="rounded-md border border-edge bg-surface-2/60 px-2 py-2"
          >
            <strong className="block font-mono text-sm tabular-nums">{value}</strong>
            <span className="text-[10px] text-fg-faint">{label}</span>
          </div>
        ))}
      </div>
      {latest.length > 0 && (
        <div className="mt-3 border-t border-edge pt-3">
          <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-fg-faint">
            Décisions reliées
          </p>
          <ul className="mt-2 space-y-2">
            {latest.map((action) => (
              <li
                key={action.id}
                className="rounded-md border border-edge bg-surface-2/45 px-2.5 py-2"
              >
                <div className="flex flex-wrap items-center gap-1.5">
                  <strong className="text-xs">
                    {action.actor === "council" ? "Conseil" : speakerMeta(action.actor).label}
                  </strong>
                  <Pill tone={action.action_type.includes("nucleaire") ? "bad" : "neutral"}>
                    {actionLabel(action.action_type)}
                  </Pill>
                  <span className="ml-auto font-mono text-[10px] text-fg-faint">
                    R{action.round_no}
                  </span>
                </div>
                {action.summary && (
                  <p className="mt-1 text-[11px] leading-relaxed text-fg-muted">
                    {action.summary}
                  </p>
                )}
                <p
                  className="mt-1 truncate font-mono text-[9px] text-fg-faint"
                  title={action.provenance}
                >
                  {action.provenance}
                </p>
              </li>
            ))}
          </ul>
        </div>
      )}
    </details>
  );
}
