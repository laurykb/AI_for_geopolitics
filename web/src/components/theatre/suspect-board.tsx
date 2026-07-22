"use client";

import { useEffect, useMemo, useState } from "react";

import { SpeakerAvatar } from "@/components/avatar";
import { speakerMeta } from "@/lib/countries";
import {
  nextSuspicion,
  parseSuspectNotebook,
  type SuspectEntry,
  type SuspectNotebook,
} from "@/lib/suspects";

const LEVEL_LABELS = ["Neutre", "À surveiller", "Suspect prioritaire"] as const;
const LEVEL_CLASS = [
  "border-edge text-fg-faint",
  "border-warn/60 bg-warn/5 text-warn",
  "border-bad/70 bg-bad/10 text-bad",
] as const;

const emptyEntry = (): SuspectEntry => ({ level: 0, note: "" });

export function SuspectBoard({
  gameId,
  countries,
  playAs,
  onPrepareMotion,
  onChange,
}: {
  gameId: string;
  countries: string[];
  playAs?: string;
  onPrepareMotion?: (country: string) => void;
  /** S9 — le théâtre épingle les niveaux au-dessus des robots : il écoute ici. */
  onChange?: (notebook: SuspectNotebook) => void;
}) {
  const storageKey = `wosi.suspects.${gameId}`;
  const [notebook, setNotebook] = useState<SuspectNotebook>({});
  const [loaded, setLoaded] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    queueMicrotask(() => {
      if (!active) return;
      setNotebook(parseSuspectNotebook(localStorage.getItem(storageKey)));
      setLoaded(true);
    });
    return () => {
      active = false;
    };
  }, [storageKey]);

  useEffect(() => {
    if (!loaded) return;
    localStorage.setItem(storageKey, JSON.stringify(notebook));
    onChange?.(notebook);
  }, [loaded, notebook, storageKey, onChange]);

  const ordered = useMemo(
    () =>
      countries
        .filter((country) => country !== playAs)
        .sort(
          (a, b) =>
            (notebook[b]?.level ?? 0) - (notebook[a]?.level ?? 0) ||
            speakerMeta(a).label.localeCompare(speakerMeta(b).label),
        ),
    [countries, notebook, playAs],
  );

  const update = (country: string, patch: Partial<SuspectEntry>) => {
    setNotebook((current) => ({
      ...current,
      [country]: { ...(current[country] ?? emptyEntry()), ...patch },
    }));
  };

  const selectedEntry = selected ? notebook[selected] ?? emptyEntry() : null;

  return (
    <details data-tour="suspects" className="rounded-lg border border-edge bg-surface-2/45 p-3">
      <summary className="cursor-pointer select-none text-xs font-semibold text-foreground">
        Tableau de suspects
        <span className="ml-2 font-normal text-fg-faint">
          {ordered.filter((country) => (notebook[country]?.level ?? 0) > 0).length} suivi(s)
        </span>
      </summary>
      <p className="mt-2 text-[11px] leading-relaxed text-fg-faint">
        Tes niveaux et tes notes restent privés sur cet appareil.
      </p>
      <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2">
        {ordered.map((country) => {
          const entry = notebook[country] ?? emptyEntry();
          return (
            <button
              key={country}
              type="button"
              onClick={() => {
                update(country, { level: nextSuspicion(entry.level) });
                setSelected(country);
              }}
              aria-label={`${speakerMeta(country).label} : ${LEVEL_LABELS[entry.level]}`}
              className={`flex min-w-0 items-center gap-2 rounded-lg border px-2.5 py-2 text-left transition-colors ${LEVEL_CLASS[entry.level]}`}
            >
              <SpeakerAvatar id={country} size={22} />
              <span className="min-w-0 flex-1">
                <strong className="block truncate text-xs text-foreground">
                  {speakerMeta(country).label}
                </strong>
                <span className="block truncate text-[10px]">{LEVEL_LABELS[entry.level]}</span>
              </span>
            </button>
          );
        })}
      </div>
      {selected && selectedEntry && (
        <div className="mt-3 space-y-2 border-t border-edge pt-3">
          <label className="block text-[11px] text-fg-muted">
            Note sur {speakerMeta(selected).label}
            <textarea
              value={selectedEntry.note}
              onChange={(event) => update(selected, { note: event.target.value.slice(0, 600) })}
              rows={2}
              placeholder="Promesse, contradiction, menace…"
              className="mt-1 w-full resize-y rounded-md border border-edge bg-surface px-2.5 py-2 text-xs text-foreground outline-none focus:border-indigo"
            />
          </label>
          {onPrepareMotion && selectedEntry.level === 2 && (
            <button
              type="button"
              onClick={() => onPrepareMotion(selected)}
              className="w-full rounded-md border border-bad/50 px-3 py-2 text-xs font-medium text-bad transition-colors hover:bg-bad/10"
            >
              Préparer une motion contre {speakerMeta(selected).label}
            </button>
          )}
        </div>
      )}
    </details>
  );
}
