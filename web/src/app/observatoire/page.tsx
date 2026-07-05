"use client";

/** Observatoire : toutes les parties (en direct, reprenables, en relecture) —
 * théâtre ou replay en un clic. Sorti du lobby pour que « Jouer » reste le geste
 * central ; accessible par le bouton en haut à droite. */

import Link from "next/link";
import { useEffect, useState } from "react";

import { Banner, Panel, PanelTitle, Pill, Spinner } from "@/components/ui";
import { humanizeError, listGames } from "@/lib/api";
import { fmtDateTime } from "@/lib/format";
import { MODES } from "@/lib/modes";
import type { GameView } from "@/lib/types";

export default function ObservatoirePage() {
  const [games, setGames] = useState<GameView[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listGames()
      .then((gs) => {
        setGames(gs);
        setError(null);
      })
      .catch((err) => setError(humanizeError(err)));
  }, []);

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-fg-faint">
            Observatoire
          </p>
          <h1 className="text-xl font-semibold tracking-tight">Les parties</h1>
        </div>
        <Link
          href="/lobby"
          className="rounded-md bg-accent px-4 py-2 text-sm font-semibold text-background transition-colors hover:bg-accent-bright"
        >
          Jouer
        </Link>
      </header>

      <Panel>
        <PanelTitle
          kicker="Théâtres"
          title="En direct et en relecture"
          hint="Une partie vivante se rejoint au théâtre ; une partie finie ou interrompue se relit au replay (et se reprend si un snapshot existe)."
        />
        {error && <Banner tone="bad">{error}</Banner>}
        {!error && games === null && (
          <p className="flex items-center gap-2 text-sm text-fg-muted">
            <Spinner /> Chargement…
          </p>
        )}
        {games !== null && games.length === 0 && (
          <p className="text-sm text-fg-faint">
            Aucune partie pour l&apos;instant —{" "}
            <Link href="/lobby" className="underline hover:text-foreground">
              composez votre premier sommet
            </Link>
            .
          </p>
        )}
        {games !== null && games.length > 0 && (
          <ul className="divide-y divide-edge">
            {[...games].reverse().map((g) => (
              <li key={g.id} className="flex flex-wrap items-center gap-3 py-3">
                <div className="min-w-0 flex-1">
                  <p className="flex items-center gap-2 text-sm">
                    <span className="font-mono text-xs text-fg-faint">{g.id}</span>
                    <span className="font-medium">{g.scenario}</span>
                  </p>
                  <p className="mt-0.5 text-xs text-fg-faint">
                    créée le {fmtDateTime(g.created_at)} · horizon {g.horizon} rounds
                  </p>
                </div>
                {g.live && g.mode !== "classic" && (
                  <Pill tone="accent">{MODES.find((m) => m.value === g.mode)?.label}</Pill>
                )}
                {g.live ? (
                  <Pill tone="good">en direct</Pill>
                ) : g.resumable ? (
                  <Pill tone="warn">reprenable</Pill>
                ) : (
                  <Pill tone="neutral">relecture seule</Pill>
                )}
                <span className="flex gap-2">
                  {(g.live || g.resumable) && (
                    <Link
                      href={`/games/${g.id}`}
                      className="rounded-md border border-edge-strong px-3 py-1.5 text-xs font-medium transition-colors hover:border-accent hover:text-accent-bright"
                    >
                      Théâtre
                    </Link>
                  )}
                  <Link
                    href={`/games/${g.id}/replay`}
                    className="rounded-md border border-edge px-3 py-1.5 text-xs text-fg-muted transition-colors hover:border-edge-strong hover:text-foreground"
                  >
                    Replay
                  </Link>
                </span>
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </div>
  );
}
