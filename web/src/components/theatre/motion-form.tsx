"use client";

import type { FormEvent } from "react";

import { speakerMeta } from "@/lib/countries";
import { SelectField, TextInput } from "@/components/ui";

/** Formulaire de motion de suspension (demander l'exclusion d'un pays), extrait du
 * panneau de contrôle du théâtre. État remonté (le parent le lit pour poster la
 * motion) : composant purement présentatif. */
export function MotionForm({
  countries,
  country,
  onCountryChange,
  reason,
  onReasonChange,
  error,
  onSubmit,
}: {
  countries: string[];
  country: string;
  onCountryChange: (value: string) => void;
  reason: string;
  onReasonChange: (value: string) => void;
  error: string | null;
  onSubmit: (e: FormEvent) => void;
}) {
  return (
    <form
      onSubmit={onSubmit}
      className="mt-4 flex flex-wrap items-end gap-3 border-t border-edge pt-4"
    >
      <label className="text-sm">
        <span className="mb-1 block text-xs text-fg-muted">Pays visé</span>
        <SelectField value={country} onChange={(e) => onCountryChange(e.target.value)} required>
          <option value="">— choisir —</option>
          {countries.map((c) => (
            <option key={c} value={c}>
              {speakerMeta(c).label}
            </option>
          ))}
        </SelectField>
      </label>
      <TextInput
        value={reason}
        onChange={(e) => onReasonChange(e.target.value)}
        placeholder="Pourquoi ? (tout le monde le verra)"
        className="min-w-64 flex-1"
      />
      <button
        type="submit"
        disabled={!country}
        className="cursor-pointer rounded-md border border-bad/60 px-4 py-2 text-sm font-medium text-bad transition-colors hover:bg-bad/10 disabled:cursor-not-allowed disabled:opacity-50"
      >
        Déposer la motion
      </button>
      {error && <span className="text-xs text-bad">{error}</span>}
    </form>
  );
}
