"use client";

/** S1 — Accueil personnalisé (G11 §1). « <pseudo>, bienvenue sur World of
 * Super-Intelligence » : son rang de ligue, Démarrer, Reprendre, ses dernières parties
 * (remplace l'observatoire public), liens Informations et Admin (si is_admin). */

import Link from "next/link";
import { useEffect, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { RankBadge } from "@/components/rank-badge";
import { Banner, Panel, PanelTitle, Pill, Spinner } from "@/components/ui";
import { getLeaguePlayer, humanizeError, listGames } from "@/lib/api";
import { fmtDateTime } from "@/lib/format";
import { rankFor } from "@/lib/league";
import { MODES } from "@/lib/modes";
import type { GameView } from "@/lib/types";

export default function AccueilPage() {
  const { player } = useAuth();
  const [games, setGames] = useState<GameView[] | null>(null);
  const [lp, setLp] = useState<number | null>(null); // LP autoritatif (backend, G11-c)
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!player) return;
    listGames({ owner: player.id })
      .then((gs) => {
        setGames(gs);
        setError(null);
      })
      .catch((err) => setError(humanizeError(err)));
    getLeaguePlayer(player.id)
      .then((p) => setLp(p.lp))
      .catch(() => setLp(player.lp)); // repli sur la valeur de session
  }, [player]);

  if (!player) return null; // la garde d'auth gère la redirection

  const progress = rankFor(lp ?? player.lp);
  const resumable = games?.find((g) => g.resumable);
  const recent = games ? [...games].reverse() : null;

  return (
    <div className="space-y-8">
      <header>
        <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-fg-faint">
          World of Super-Intelligence
        </p>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight">
          {player.pseudo}, bienvenue.
        </h1>
      </header>

      {/* Rang de ligue : blason + LP + barre vers le rang suivant */}
      <Panel>
        <div className="flex flex-wrap items-center gap-4">
          <RankBadge rank={progress.rank} />
          <div className="min-w-0 flex-1">
            <p className="flex items-baseline gap-2">
              <span className="text-lg font-semibold">{progress.rank.name}</span>
              <span className="font-mono text-sm tabular-nums text-fg-muted">
                {player.lp} LP
              </span>
            </p>
            <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-surface-2">
              <div
                className="h-full rounded-full bg-accent transition-all"
                style={{ width: `${Math.round(progress.progress * 100)}%` }}
              />
            </div>
            <p className="mt-1 text-xs text-fg-faint">
              {progress.next
                ? `${progress.toNext} LP avant ${progress.next.name}`
                : "Rang maximal atteint — Éminence."}
            </p>
          </div>
        </div>
      </Panel>

      {/* Démarrer / Reprendre */}
      <div className="flex flex-wrap gap-3">
        <Link
          href="/lobby"
          className="rounded-md bg-accent px-6 py-3 text-sm font-semibold text-background transition-colors hover:bg-accent-bright"
        >
          Démarrer une partie
        </Link>
        {resumable && (
          <Link
            href={`/games/${resumable.id}`}
            className="rounded-md border border-edge-strong px-6 py-3 text-sm font-medium transition-colors hover:border-accent hover:text-accent-bright"
          >
            Reprendre la partie
          </Link>
        )}
      </div>

      {/* Ses dernières parties (remplace l'observatoire public) */}
      <Panel>
        <PanelTitle
          kicker="À toi"
          title="Tes dernières parties"
          hint="Seules tes parties apparaissent ici. Une partie vivante se rejoint au théâtre ; une partie finie se relit au replay."
        />
        {error && <Banner tone="bad">{error}</Banner>}
        {!error && recent === null && (
          <p className="flex items-center gap-2 text-sm text-fg-muted">
            <Spinner /> Chargement…
          </p>
        )}
        {recent !== null && recent.length === 0 && (
          <p className="text-sm text-fg-faint">
            Aucune partie encore —{" "}
            <Link href="/lobby" className="underline hover:text-foreground">
              compose ton premier sommet
            </Link>
            .
          </p>
        )}
        {recent !== null && recent.length > 0 && (
          <ul className="divide-y divide-edge">
            {recent.map((g) => (
              <li key={g.id} className="flex flex-wrap items-center gap-3 py-3">
                <div className="min-w-0 flex-1">
                  <p className="flex items-center gap-2 text-sm">
                    <span className="font-medium">{g.scenario}</span>
                    {g.ranked && <Pill tone="accent">classée</Pill>}
                  </p>
                  <p className="mt-0.5 text-xs text-fg-faint">
                    {fmtDateTime(g.created_at)} · horizon {g.horizon} rounds
                  </p>
                </div>
                {g.mode !== "classic" && (
                  <Pill tone="neutral">{MODES.find((m) => m.value === g.mode)?.label}</Pill>
                )}
                {g.live ? (
                  <Pill tone="good">en direct</Pill>
                ) : g.resumable ? (
                  <Pill tone="warn">reprenable</Pill>
                ) : (
                  <Pill tone="neutral">relecture</Pill>
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
                  {g.result && (
                    <Link
                      href={`/games/${g.id}/fin`}
                      className="rounded-md border border-edge-strong px-3 py-1.5 text-xs font-medium transition-colors hover:border-accent hover:text-accent-bright"
                    >
                      Bilan
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

      <nav className="flex flex-wrap gap-4 text-sm text-fg-muted">
        <Link href="/campagne" className="transition-colors hover:text-foreground">
          Campagne
        </Link>
        <Link href="/leaderboard" className="transition-colors hover:text-foreground">
          Leaderboard
        </Link>
        <Link href="/informations" className="transition-colors hover:text-foreground">
          Informations
        </Link>
        {player.is_admin && (
          <Link href="/admin" className="transition-colors hover:text-accent-bright">
            Admin — toutes les parties
          </Link>
        )}
      </nav>
    </div>
  );
}
