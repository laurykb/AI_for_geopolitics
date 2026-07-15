"use client";

/** Vue Admin (G11 §1 S1 / §5) — l'ex-observatoire, réservé aux comptes `is_admin` :
 * TOUTES les parties (les siennes et celles des autres, y compris héritées sans
 * propriétaire). Un non-admin est renvoyé à l'accueil. */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { Banner, Panel, PanelTitle, Pill, Spinner } from "@/components/ui";
import { humanizeError, listGames } from "@/lib/api";
import { adminDenied } from "@/lib/auth";
import { fmtDateTime } from "@/lib/format";
import { MODES } from "@/lib/modes";
import type { GameView } from "@/lib/types";

export default function AdminPage() {
  const { player, loading } = useAuth();
  const router = useRouter();
  const [games, setGames] = useState<GameView[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Garde de rôle : il faut être admin — le visiteur sans session est renvoyé
  // aussi (sinon il resterait bloqué sur le spinner de vérification).
  useEffect(() => {
    if (adminDenied(loading, player)) router.replace("/accueil");
  }, [loading, player, router]);

  useEffect(() => {
    if (!player?.is_admin) return;
    listGames({ admin: true })
      .then((gs) => {
        setGames(gs);
        setError(null);
      })
      .catch((err) => setError(humanizeError(err)));
  }, [player]);

  if (!player?.is_admin) {
    return (
      <p className="flex items-center gap-2 py-16 text-sm text-fg-muted">
        <Spinner /> Vérification des droits…
      </p>
    );
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-fg-faint">
            Admin
          </p>
          <h1 className="text-xl font-semibold tracking-tight">Toutes les parties</h1>
        </div>
        <Link
          href="/admin/crises"
          className="rounded-md border border-edge-strong px-4 py-2 text-sm font-medium transition-colors hover:border-accent hover:text-accent-bright"
        >
          + Composer une crise
        </Link>
        <Link
          href="/accueil"
          className="rounded-md border border-edge px-4 py-2 text-sm text-fg-muted transition-colors hover:border-edge-strong hover:text-foreground"
        >
          ← Accueil
        </Link>
      </header>

      <Panel>
        <PanelTitle
          kicker="Supervision"
          title="En direct et en relecture"
          hint="Vue admin : toutes les parties, quel que soit le propriétaire — y compris les parties héritées d'avant l'authentification (sans propriétaire)."
        />
        {error && <Banner tone="bad">{error}</Banner>}
        {!error && games === null && (
          <p className="flex items-center gap-2 text-sm text-fg-muted">
            <Spinner /> Chargement…
          </p>
        )}
        {games !== null && games.length === 0 && (
          <p className="text-sm text-fg-faint">Aucune partie pour l&apos;instant.</p>
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
                    créée le {fmtDateTime(g.created_at)} · horizon {g.horizon} rounds ·{" "}
                    {g.owner_id ? (
                      <span className="font-mono">{g.owner_id}</span>
                    ) : (
                      <span className="italic">sans propriétaire</span>
                    )}
                  </p>
                </div>
                {g.mode !== "classic" && (
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
