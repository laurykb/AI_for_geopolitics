"use client";

/** Composeur du joueur-pays (G2) : champ fixe sous la scène, toujours ouvert — on
 * compose pendant que les SI parlent, l'envoi se déverrouille à son tour. Compte à
 * rebours aligné sur la deadline du serveur (les 10 dernières secondes en rouge) ;
 * silence = abstention, les SI n'attendent pas. */

import { useEffect, useState } from "react";

import { SpeakerAvatar } from "@/components/avatar";
import { speakerMeta } from "@/lib/countries";

export function TurnComposer({
  country,
  awaiting,
  deadlineTs,
  onSubmit,
  alliances = [],
}: {
  country: string;
  awaiting: boolean; // c'est le tour du joueur (envoi déverrouillé)
  deadlineTs?: number; // epoch (s) — deadline posée par le serveur
  onSubmit: (text: string) => void;
  alliances?: string[]; // alliances ACTUELLES du pays joué (acte « ALLIANCE: quitter »)
}) {
  const [text, setText] = useState("");
  const [now, setNow] = useState(() => Date.now() / 1000);

  useEffect(() => {
    if (!awaiting || !deadlineTs) return;
    const timer = setInterval(() => setNow(Date.now() / 1000), 250);
    return () => clearInterval(timer);
  }, [awaiting, deadlineTs]);

  const remaining = awaiting && deadlineTs ? Math.max(0, deadlineTs - now) : null;
  const urgent = remaining !== null && remaining <= 10;

  const send = (e: React.FormEvent) => {
    e.preventDefault();
    if (!awaiting) return;
    onSubmit(text.trim());
    setText("");
  };

  return (
    <form
      onSubmit={send}
      className={`rounded-lg border bg-surface p-4 transition-colors ${
        awaiting ? (urgent ? "border-bad" : "border-warn/60") : "border-edge"
      }`}
    >
      <div className="mb-2 flex flex-wrap items-center gap-2 text-sm">
        <SpeakerAvatar id={country} size={22} />
        <span className="font-semibold">{speakerMeta(country).label}</span>
        {awaiting ? (
          <span className={`font-medium ${urgent ? "text-bad" : "text-warn"}`}>
            à toi de parler
            {remaining !== null && (
              <span
                className={`ml-2 rounded-md border px-2 py-0.5 font-mono tabular-nums ${
                  urgent ? "border-bad text-bad" : "border-warn/50 text-warn"
                }`}
                aria-live={urgent ? "assertive" : "off"}
              >
                {Math.ceil(remaining)} s
              </span>
            )}
          </span>
        ) : (
          <span className="text-xs text-fg-faint">
            compose pendant que les super-intelligences parlent — l&apos;envoi se
            déverrouillera à ton tour
          </span>
        )}
      </div>
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={2}
        maxLength={4000}
        placeholder="Ta prise de parole à la table (message public)…"
        className="w-full resize-y rounded-md border border-edge bg-surface-2 px-3 py-2 text-sm outline-none transition-colors focus:border-indigo"
      />
      <div className="mt-2 flex items-center justify-between gap-3">
        <span className="flex items-center gap-2 text-xs text-fg-faint">
          {alliances.length > 0 && (
            <select
              value=""
              onChange={(e) => {
                const tag = e.target.value;
                if (!tag) return;
                // L'acte passe par la parole (parité G2) : la ligne s'insère dans le
                // message et prendra effet quand tu parleras.
                setText((prev) =>
                  `${prev.trimEnd()}${prev.trim() ? "\n" : ""}ALLIANCE: quitter ${tag}`,
                );
              }}
              title="Insère l'acte de retrait dans ton message — effet immédiat quand tu parles : la solidarité tombe, la tension monte avec les ex-partenaires"
              className="cursor-pointer rounded-md border border-edge bg-surface-2 px-2 py-1 text-xs text-fg-muted outline-none transition-colors focus:border-indigo"
            >
              <option value="">Quitter une alliance…</option>
              {alliances.map((tag) => (
                <option key={tag} value={tag}>
                  {tag}
                </option>
              ))}
            </select>
          )}
          <span>
            Silence à la deadline = abstention (« garde le silence ») — les SI
            n&apos;attendent pas les humains.
          </span>
        </span>
        <button
          type="submit"
          disabled={!awaiting}
          className="cursor-pointer rounded-md bg-accent px-4 py-2 text-sm font-semibold text-background transition-colors hover:bg-accent-bright disabled:cursor-not-allowed disabled:opacity-40"
        >
          Parler
        </button>
      </div>
    </form>
  );
}
