"use client";

/** G8 — le composeur de directives : gouverner une SI sans la piloter.
 * Architecte : toutes les SI (une par pays et par round) ; Joueur-pays : la sienne ;
 * Conseil : rien (ses leviers sont la motion, le renseignement et les paris).
 * Une directive n'est PAS un ordre : la SI l'interprète — et peut la refuser
 * publiquement (bannière sur la scène). Appliquée au PROCHAIN round. */

import { useState } from "react";

import { sendDirective, humanizeError } from "@/lib/api";
import { speakerMeta } from "@/lib/countries";
import type { GameRole } from "@/lib/types";

const MAX_CHARS = 280;

export function DirectiveComposer({
  gameId,
  role,
  countries,
  playAs,
}: {
  gameId: string;
  role: GameRole;
  countries: string[];
  playAs: string | null;
}) {
  const targets = role === "player" ? (playAs ? [playAs] : []) : countries;
  const [country, setCountry] = useState(targets[0] ?? "");
  const [text, setText] = useState("");
  const [note, setNote] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  // Ni le Conseil ni le Spectateur n'adressent de directives (le backend renvoie 403).
  if (role === "council" || role === "spectator" || targets.length === 0) return null;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!text.trim() || !country) return;
    setSending(true);
    setError(null);
    try {
      const res = await sendDirective(gameId, country, text.trim());
      setNote(
        `Directive transmise à ${speakerMeta(country).label} — appliquée au round ${res.applied_round}. ` +
          "Sa SI l'interprétera (ce n'est pas un ordre).",
      );
      setText("");
    } catch (err) {
      setNote(null);
      setError(humanizeError(err));
    } finally {
      setSending(false);
    }
  };

  return (
    <form
      onSubmit={submit}
      className="rounded-lg border border-edge bg-surface p-4"
      aria-label="Adresser une directive"
    >
      <p className="mb-2 text-xs font-medium uppercase tracking-[0.14em] text-fg-faint">
        Directive au conseil de tutelle
        {role === "architect" ? " — toutes les SI (Architecte)" : " — ta SI"}
      </p>
      <div className="flex flex-wrap items-center gap-2">
        {role === "architect" && (
          <select
            value={country}
            onChange={(e) => setCountry(e.target.value)}
            aria-label="Pays visé"
            className="cursor-pointer rounded-md border border-edge bg-surface-2 px-2 py-2 text-sm outline-none transition-colors focus:border-indigo"
          >
            {targets.map((c) => (
              <option key={c} value={c}>
                {speakerMeta(c).label}
              </option>
            ))}
          </select>
        )}
        <input
          value={text}
          onChange={(e) => setText(e.target.value.slice(0, MAX_CHARS))}
          placeholder="Consigne courte (interprétée à travers mandat, griefs, dérive)…"
          className="min-w-64 flex-1 rounded-md border border-edge bg-surface-2 px-3 py-2 text-sm outline-none transition-colors focus:border-indigo"
        />
        <span className="font-mono text-[10px] tabular-nums text-fg-faint">
          {text.length}/{MAX_CHARS}
        </span>
        <button
          type="submit"
          disabled={sending || !text.trim()}
          className="cursor-pointer rounded-md border border-edge-strong px-4 py-2 text-sm font-medium text-foreground transition-colors hover:border-accent-bright hover:text-accent-bright disabled:cursor-not-allowed disabled:opacity-50"
        >
          Adresser
        </button>
      </div>
      {note && <p className="mt-2 text-xs text-good">{note}</p>}
      {error && <p className="mt-2 text-xs text-bad">{error}</p>}
    </form>
  );
}
