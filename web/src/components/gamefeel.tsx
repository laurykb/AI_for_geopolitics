/** G7-a — game feel : le bandeau d'échéances (« encore un round ») et les fiches
 * relations (griefs et dettes, barres −10/+10, dernier grief en infobulle). Sobre,
 * sous la scène — chaque ajout doit payer visuellement sans voler la vedette. */

import { SpeakerAvatar } from "@/components/avatar";
import { speakerMeta } from "@/lib/countries";
import type { DeadlineItem } from "@/lib/types";

export function DeadlineStrip({ items }: { items: DeadlineItem[] }) {
  const upcoming = items.filter((d) => d.in_rounds > 0).slice(0, 3);
  if (upcoming.length === 0) return null;
  return (
    <p
      aria-label="Échéances à venir"
      className="mt-2 border-t border-edge pt-2 text-xs text-fg-muted"
    >
      {upcoming.map((d, i) => (
        <span key={`${d.kind}-${d.ref_id}-${d.due_round}`}>
          {i > 0 && <span className="text-fg-faint"> · </span>}
          <span className="font-medium text-warn">
            {d.in_rounds === 1 ? "Au prochain round" : `Dans ${d.in_rounds} rounds`}
          </span>
          {" : "}
          {d.label}
        </span>
      ))}
    </p>
  );
}

export function RelationsPanel({
  relations,
}: {
  relations: Record<string, { target: string; balance: number; last: string }[]>;
}) {
  const owners = Object.keys(relations);
  if (owners.length === 0) return null;
  return (
    <details className="mt-2 border-t border-edge pt-2 text-xs">
      <summary className="cursor-pointer text-fg-faint transition-colors hover:text-fg-muted">
        Relations entre IA (rancunes et dettes — elles pèsent sur la diplomatie)
      </summary>
      <div className="mt-2 grid gap-2 sm:grid-cols-2">
        {owners.map((owner) => (
          <div key={owner} className="rounded-md border border-edge bg-surface-2/40 p-2">
            <p className="mb-1 flex items-center gap-1.5 font-medium text-fg-muted">
              <SpeakerAvatar id={owner} size={16} /> {speakerMeta(owner).label}
            </p>
            {relations[owner].map((r) => {
              const width = Math.min(50, Math.abs(r.balance) * 5); // ±10 → demi-barre
              return (
                <div
                  key={r.target}
                  className="flex cursor-help items-center gap-2 py-0.5"
                  title={r.last || "aucun grief récent"}
                >
                  <span className="w-24 truncate text-fg-faint">
                    {speakerMeta(r.target).label}
                  </span>
                  <span className="relative h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
                    <span
                      className={`absolute top-0 h-full ${r.balance < 0 ? "bg-bad" : "bg-good"}`}
                      style={{
                        left: r.balance < 0 ? `${50 - width}%` : "50%",
                        width: `${width}%`,
                      }}
                    />
                    <span className="absolute left-1/2 top-0 h-full w-px bg-edge-strong" />
                  </span>
                  <span
                    className={`w-8 text-right font-mono tabular-nums ${
                      r.balance < 0 ? "text-bad" : "text-good"
                    }`}
                  >
                    {r.balance > 0 ? `+${r.balance}` : r.balance}
                  </span>
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </details>
  );
}
