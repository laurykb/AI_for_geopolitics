"use client";

/** S7 — Leaderboard (G11-c §1). Classement global par LP (pseudo, blason, LP, rang) ;
 * le rang du joueur connecté est épinglé. Vue publique : jamais l'historique des autres. */

import Link from "next/link";
import { useEffect, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { RankBadge } from "@/components/rank-badge";
import { Banner, Panel, PanelTitle, Spinner } from "@/components/ui";
import { getLeague, humanizeError } from "@/lib/api";
import { rankFor } from "@/lib/league";
import type { LeaguePlayer } from "@/lib/types";

export default function LeaderboardPage() {
  const { player } = useAuth();
  const [board, setBoard] = useState<LeaguePlayer[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getLeague()
      .then((b) => {
        setBoard(b);
        setError(null);
      })
      .catch((e) => setError(humanizeError(e)));
  }, []);

  const myRank = board?.findIndex((p) => p.id === player?.id) ?? -1;

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-fg-faint">Ligue</p>
          <h1 className="text-xl font-semibold tracking-tight">Classement</h1>
        </div>
        <Link href="/accueil" className="rounded-md border border-edge px-4 py-2 text-sm text-fg-muted transition-colors hover:border-edge-strong hover:text-foreground">
          ← Accueil
        </Link>
      </header>

      {myRank >= 0 && board && (
        <Panel>
          <PanelTitle kicker="Ton rang" title={`#${myRank + 1} — ${board[myRank].pseudo}`} />
          <Row player={board[myRank]} position={myRank + 1} me />
        </Panel>
      )}

      <Panel>
        <PanelTitle kicker="Classement" title="Les meilleurs joueurs" hint="Classé aux points de ligue (LP) : seules les parties classées où tu joues un pays comptent." />
        {error && <Banner tone="bad">{error}</Banner>}
        {!error && board === null && (
          <p className="flex items-center gap-2 text-sm text-fg-muted">
            <Spinner /> Chargement…
          </p>
        )}
        {board !== null && board.length === 0 && (
          <p className="text-sm text-fg-faint">Personne au classement — sois le premier à finir une partie classée.</p>
        )}
        {board !== null && board.length > 0 && (
          <ol className="divide-y divide-edge">
            {board.map((p, i) => (
              <Row key={p.id} player={p} position={i + 1} me={p.id === player?.id} />
            ))}
          </ol>
        )}
      </Panel>
    </div>
  );
}

function Row({ player, position, me }: { player: LeaguePlayer; position: number; me?: boolean }) {
  const progress = rankFor(player.lp);
  return (
    <li className={`flex items-center gap-3 py-2.5 ${me ? "text-accent-bright" : ""}`}>
      <span className="w-8 text-right font-mono text-sm tabular-nums text-fg-faint">#{position}</span>
      <RankBadge rank={progress.rank} size="sm" />
      <span className="min-w-0 flex-1 truncate font-medium">{player.pseudo}</span>
      <span className="text-xs text-fg-faint">{progress.rank.name}</span>
      <span className="w-16 text-right font-mono text-sm tabular-nums">{player.lp} LP</span>
    </li>
  );
}
