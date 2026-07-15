"use client";

/** CC-15c — la salle des observables à onglets (budget de surface du
 * PRINCIPE_SIMPLICITE : au plus 3 panneaux d'observables visibles).
 *
 * Le théâtre et le replay regroupent leurs observables en TabGroups :
 * « Renseignement » (ce que les IA disent vs ce qu'elles font — jauges
 * d'OBSERVATION ; les ACHATS restent dans le Dossier), « Le monde » (l'état
 * global), « La table » (les pays et la parole). Chaque nouvel observable
 * devient un ONGLET, jamais un panneau de plus. */

import { useState, type ReactNode } from "react";

import { Hint } from "./ui";

export type ObservatoryTab = {
  key: string; // clé stable de l'onglet (sélection)
  label: string; // libellé court, déjà traduit
  content: ReactNode; // null / undefined = onglet absent ce round
};

export function TabGroup({
  label,
  hint,
  tabs,
  empty,
  dataTour,
}: {
  label: string;
  hint?: string;
  tabs: ObservatoryTab[];
  /** Affiché quand aucun onglet n'a de contenu — garde le groupe (et son ancre
   * de visite guidée) visible avec un état vide actionnable. Omis : groupe masqué. */
  empty?: ReactNode;
  dataTour?: string;
}) {
  const available = tabs.filter((t) => t.content != null);
  const [selected, setSelected] = useState<string | null>(null);
  if (available.length === 0 && empty == null) return null;
  const active = available.find((t) => t.key === selected) ?? available[0];

  return (
    <section aria-label={label} data-tour={dataTour} className="space-y-2">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 px-1">
        <span className="flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-[0.14em] text-fg-faint">
          {label}
          {hint && <Hint text={hint} />}
        </span>
        {available.length > 1 && (
          <div role="tablist" aria-label={label} className="flex flex-wrap gap-1">
            {available.map((t) => (
              <button
                key={t.key}
                role="tab"
                aria-selected={t.key === active.key}
                onClick={() => setSelected(t.key)}
                className={`cursor-pointer rounded-md border px-2 py-1 text-[11px] font-medium transition-colors ${
                  t.key === active.key
                    ? "border-accent bg-surface-2 text-accent-bright"
                    : "border-edge text-fg-muted hover:border-edge-strong hover:text-foreground"
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>
        )}
      </div>
      <div role="tabpanel" aria-label={active ? active.label : label}>
        {active ? active.content : empty}
      </div>
    </section>
  );
}
