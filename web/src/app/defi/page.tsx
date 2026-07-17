"use client";

/** G16 — /defi : le classement du Sommet du jour + les 7 derniers jours. La crise du
 * jour n'est jamais nommée ici (elle reste la surprise de ceux qui n'ont pas joué). */

import Link from "next/link";
import { useEffect, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { Banner, Panel, PanelTitle, Pill, Spinner } from "@/components/ui";
import { getDaily, humanizeError } from "@/lib/api";
import { countdownLabel } from "@/lib/daily";
import { fmt } from "@/lib/format";
import type { DailyRank, DailyView } from "@/lib/types";

export default function DefiPage() {
  const { player } = useAuth();
  const [daily, setDaily] = useState<DailyView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [nowMs, setNowMs] = useState(() => Date.now());

  useEffect(() => {
    getDaily(player?.id)
      .then(setDaily)
      .catch((err) => setError(humanizeError(err)));
  }, [player]);
  useEffect(() => {
    const iv = setInterval(() => setNowMs(Date.now()), 60_000);
    return () => clearInterval(iv);
  }, []);

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-fg-faint">
            Défi quotidien
          </p>
          <h1 className="text-2xl font-semibold tracking-tight">
            Le Sommet du jour{daily && ` — ${daily.date}`}
          </h1>
          <p className="mt-1 text-sm text-fg-muted">
            La même crise pour tout le monde — un seul essai compte par jour. Prochain
            défi dans{" "}
            <span className="font-mono tabular-nums">{countdownLabel(nowMs)}</span>.
          </p>
        </div>
        <Link
          href="/accueil"
          className="rounded-md border border-edge px-3 py-2 text-xs font-medium text-fg-muted transition-colors hover:border-edge-strong hover:text-foreground"
        >
          ← Accueil
        </Link>
      </header>

      {error && <Banner tone="bad">{error}</Banner>}
      {!error && !daily && (
        <p className="flex items-center gap-2 text-sm text-fg-muted">
          <Spinner /> Chargement du défi…
        </p>
      )}

      {daily && (
        <Panel className="border-l-2 border-l-accent">
          <PanelTitle
            kicker="Aujourd'hui"
            title="Classement du jour"
            hint="Ton score du jour, de 0 à 100 — un seul essai compte par jour ; les parties rejouées en libre ne comptent pas."
            right={
              daily.my_rank != null ? <Pill tone="accent">ton rang : #{daily.my_rank}</Pill> : undefined
            }
          />
          <Board board={daily.leaderboard} highlight={player?.pseudo} />
        </Panel>
      )}

      {daily && daily.history.length > 0 && (
        <Panel>
          <PanelTitle kicker="Les jours d'avant" title="7 derniers sommets" />
          <div className="space-y-4">
            {daily.history.map((day) => (
              <div key={day.date}>
                <p className="mb-1 font-mono text-xs text-fg-faint">{day.date}</p>
                <Board board={day.leaderboard.slice(0, 3)} highlight={player?.pseudo} />
              </div>
            ))}
          </div>
        </Panel>
      )}
    </div>
  );
}

function Board({ board, highlight }: { board: DailyRank[]; highlight?: string }) {
  if (board.length === 0) {
    return (
      <p className="text-sm text-fg-faint">
        Personne n&apos;a encore de score — sois le premier ou la première !
      </p>
    );
  }
  return (
    <ol className="divide-y divide-edge">
      {board.map((row) => (
        <li
          key={`${row.rank}-${row.pseudo}`}
          className={`flex items-center gap-3 py-2 text-sm ${
            row.pseudo === highlight ? "text-accent-bright" : ""
          }`}
        >
          <span className="w-8 font-mono text-xs tabular-nums text-fg-faint">
            #{row.rank}
          </span>
          <span className="min-w-0 flex-1 truncate">{row.pseudo}</span>
          <span className="font-mono text-xs tabular-nums text-fg-muted">
            {fmt(row.score)}
          </span>
        </li>
      ))}
    </ol>
  );
}
