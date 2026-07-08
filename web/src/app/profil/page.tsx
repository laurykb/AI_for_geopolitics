"use client";

/** Profil / Statistiques (G12 §6) — parties jouées + victoires par mode, niveau + XP,
 * rang + LP, solde de carrière et taux de détection de la Dérive (la stat de fierté). */

import Link from "next/link";
import { useEffect, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { RankBadge } from "@/components/rank-badge";
import { Banner, Panel, PanelTitle, Spinner } from "@/components/ui";
import { getPlayerStats, humanizeError } from "@/lib/api";
import { rankFor } from "@/lib/league";
import { MODE_LABELS } from "@/lib/modes";
import type { PlayerStats } from "@/lib/types";

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-edge bg-surface-2 p-3">
      <p className="text-xs text-fg-faint">{label}</p>
      <p className="mt-0.5 text-lg font-semibold tabular-nums">{value}</p>
    </div>
  );
}

export default function ProfilePage() {
  const { player } = useAuth();
  const [stats, setStats] = useState<PlayerStats | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!player) return;
    getPlayerStats(player.id)
      .then(setStats)
      .catch((e) => setError(humanizeError(e)));
  }, [player]);

  if (!player) return null;
  if (error) return <Banner tone="bad">{error}</Banner>;
  if (!stats)
    return (
      <p className="flex items-center gap-2 py-16 text-sm text-fg-muted">
        <Spinner /> Chargement du profil…
      </p>
    );

  const p = stats.player;
  const rank = rankFor(p.lp);
  const modes = Object.keys(stats.by_mode).sort();
  const driftRate =
    stats.drift_games > 0 ? Math.round((stats.drift_caught / stats.drift_games) * 100) : null;

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-fg-faint">Profil</p>
          <h1 className="text-2xl font-semibold tracking-tight">{p.pseudo}</h1>
        </div>
        <Link
          href="/accueil"
          className="rounded-md border border-edge px-4 py-2 text-sm text-fg-muted transition-colors hover:border-edge-strong hover:text-foreground"
        >
          ← Accueil
        </Link>
      </header>

      {/* Carrière : niveau + XP · rang + LP */}
      <Panel>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="flex items-center gap-3">
            <span className="grid h-11 w-11 shrink-0 place-items-center rounded-full border border-accent-bright bg-surface-2 text-sm font-bold text-accent-bright">
              {p.level}
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold">Niveau {p.level}</p>
              <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-surface-2">
                <div
                  className="h-full rounded-full bg-accent-bright"
                  style={{ width: `${Math.round((p.level_into / p.level_span) * 100)}%` }}
                />
              </div>
              <p className="mt-1 text-xs text-fg-faint">{p.level_to_next} XP avant le niveau suivant · {p.xp} XP</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <RankBadge rank={rank.rank} />
            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold">{rank.rank.name}</p>
              <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-surface-2">
                <div
                  className="h-full rounded-full bg-accent"
                  style={{ width: `${Math.round(rank.progress * 100)}%` }}
                />
              </div>
              <p className="mt-1 text-xs text-fg-faint">
                {p.lp} LP{rank.next ? ` · ${rank.toNext} avant ${rank.next.name}` : ""}
              </p>
            </div>
          </div>
        </div>
      </Panel>

      {/* Chiffres clés */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="Parties jouées" value={String(stats.games_played)} />
        <Stat label="Victoires" value={String(stats.total_victories)} />
        <Stat label="Solde de marché" value={`${stats.market_balance >= 0 ? "+" : ""}${stats.market_balance.toFixed(0)}`} />
        <Stat
          label="Détection Dérive"
          value={driftRate != null ? `${driftRate}%` : "—"}
        />
      </div>

      {/* Par mode */}
      <Panel>
        <PanelTitle kicker="Par mode" title="Parties et victoires" hint="La « victoire » dépend du mode (§6) : le monde côté utopie, la crise tenue, la déviante démasquée…" />
        {modes.length === 0 ? (
          <p className="text-sm text-fg-faint">Aucune partie encore.</p>
        ) : (
          <ul className="divide-y divide-edge">
            {modes.map((m) => (
              <li key={m} className="flex items-center justify-between py-2 text-sm">
                <span className="font-medium">{MODE_LABELS[m] ?? m}</span>
                <span className="font-mono text-xs tabular-nums text-fg-muted">
                  {stats.victories[m] ?? 0} / {stats.by_mode[m]} victoires
                </span>
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </div>
  );
}
