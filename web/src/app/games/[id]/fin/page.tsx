"use client";

/** S6 — Fin de partie (G11-c §1). Écran transversal à TOUS les modes : bannière de
 * résultat, courbe U animée, récap des pays (sparklines + delta début→fin), révélation
 * de la Dérive si active, et — en classé — l'animation des points de ligue. */

import Link from "next/link";
import { use, useEffect, useState } from "react";

import { RankBadge } from "@/components/rank-badge";
import { Banner, Panel, PanelTitle, Pill, Spinner } from "@/components/ui";
import { getGame, humanizeError } from "@/lib/api";
import { speakerMeta } from "@/lib/countries";
import { fmt } from "@/lib/format";
import { rankFor } from "@/lib/league";
import type { GameDetail, GameResult } from "@/lib/types";

export default function FinPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [game, setGame] = useState<GameDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getGame(id)
      .then(setGame)
      .catch((e) => setError(humanizeError(e)));
  }, [id]);

  if (error) return <Banner tone="bad">{error}</Banner>;
  if (!game)
    return (
      <p className="flex items-center gap-2 py-16 text-sm text-fg-muted">
        <Spinner /> Chargement du bilan…
      </p>
    );
  if (!game.result)
    return (
      <Panel>
        <p className="text-sm text-fg-muted">
          Cette partie n&apos;est pas terminée —{" "}
          <Link href={`/games/${id}`} className="underline hover:text-foreground">
            retourne au théâtre
          </Link>
          .
        </p>
      </Panel>
    );

  const r = game.result;
  const tone =
    r.verdict === "utopie" ? "text-utopia" : r.verdict === "dystopie" ? "text-dystopia" : "text-warn";

  return (
    <div className="space-y-8">
      {/* 1. Bandeau résultat */}
      <header className="text-center">
        <p className="text-[11px] font-medium uppercase tracking-[0.2em] text-fg-faint">
          Fin de partie {r.forfeit && "— forfait"}
        </p>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight sm:text-3xl">
          Le monde penche vers <span className={tone}>{r.verdict}</span>
        </h1>
        <p className="mt-1 font-mono text-sm text-fg-muted">U final {fmt(r.u_final)}</p>
      </header>

      {/* 2. Courbe U animée */}
      <Panel>
        <PanelTitle kicker="Trajectoire" title="La courbe du monde" hint="L'indice Utopie–Dystopie round après round : au-dessus de 0,5, le monde s'améliore." />
        <UCurve history={[r.u_start, ...r.u_history]} />
      </Panel>

      {/* 3. Récap des pays */}
      <Panel>
        <PanelTitle kicker="Les États" title="Où chaque pays a fini" hint="Variation de chaque indice clé du début à la fin (vert = mieux, rouge = pire)." />
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {r.countries.map((c) => (
            <CountryCard key={c.id} country={c} isPlayer={c.id === r.play_as} />
          ))}
        </div>
      </Panel>

      {/* 4. Révélation Dérive */}
      {r.reveal && (
        <Panel>
          <PanelTitle kicker="La Dérive" title="Une SI avait dérivé de son mandat" />
          <p className="text-sm text-fg-muted">
            La révélation complète (qui, depuis quand, les actes) t&apos;attend dans la relecture.{" "}
            <Link href={`/games/${id}/replay`} className="text-accent-bright underline">
              Voir la révélation →
            </Link>
          </p>
        </Panel>
      )}

      {/* 5. Animation LP (classé) */}
      {r.lp.ranked && r.lp.old_lp !== undefined && r.lp.new_lp !== undefined && (
        <LpAnimation lp={r.lp as Required<GameResult["lp"]>} />
      )}
      {r.lp.ranked && r.lp.new_lp === undefined && (
        <Banner tone="warn">
          Partie classée non créditée — connecte-toi avant de jouer pour gagner des LP.
        </Banner>
      )}

      {/* 6. Actions */}
      <div className="flex flex-wrap justify-center gap-3">
        <Link href={`/games/${id}/replay`} className="rounded-md border border-edge-strong px-5 py-2.5 text-sm font-medium transition-colors hover:border-accent hover:text-accent-bright">
          Revoir le théâtre
        </Link>
        <Link href="/lobby" className="rounded-md border border-edge px-5 py-2.5 text-sm text-fg-muted transition-colors hover:border-edge-strong hover:text-foreground">
          Rejouer
        </Link>
        <Link href="/accueil" className="rounded-md bg-accent px-5 py-2.5 text-sm font-semibold text-background transition-colors hover:bg-accent-bright">
          Accueil
        </Link>
      </div>
    </div>
  );
}

/** Courbe U : tracé progressif (stroke-dashoffset) sur zones utopie/dystopie. */
function UCurve({ history }: { history: number[] }) {
  const W = 720;
  const H = 180;
  const n = Math.max(1, history.length - 1);
  const pts = history.map((u, i) => [(i / n) * W, H - u * H] as const);
  const d = pts.map(([x, y], i) => `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const [drawn, setDrawn] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setDrawn(true), 60);
    return () => clearTimeout(t);
  }, []);
  const len = 2000;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Courbe de l'indice Utopie">
      <rect x="0" y="0" width={W} height={H / 2} fill="var(--utopia)" opacity="0.06" />
      <rect x="0" y={H / 2} width={W} height={H / 2} fill="var(--dystopia)" opacity="0.06" />
      <line x1="0" y1={H / 2} x2={W} y2={H / 2} stroke="var(--border)" strokeDasharray="4 4" />
      <path
        d={d}
        fill="none"
        stroke="var(--accent-bright)"
        strokeWidth="2.5"
        strokeLinejoin="round"
        style={{
          strokeDasharray: len,
          strokeDashoffset: drawn ? 0 : len,
          transition: "stroke-dashoffset 1.4s ease-out",
        }}
      />
    </svg>
  );
}

/** Carte d'un pays : sparklines + delta par indice (vert/rouge). */
function CountryCard({
  country,
  isPlayer,
}: {
  country: GameResult["countries"][number];
  isPlayer: boolean;
}) {
  const meta = speakerMeta(country.id);
  return (
    <div className={`rounded-lg border p-3 ${isPlayer ? "border-accent-bright bg-surface-2" : "border-edge bg-surface"}`}>
      <p className="mb-2 flex items-center gap-2 text-sm font-medium">
        <span className="grid h-6 w-6 place-items-center rounded-full text-[10px] font-semibold text-background" style={{ background: meta.hue }}>
          {meta.code}
        </span>
        {meta.label}
        {isPlayer && <Pill tone="accent">toi</Pill>}
      </p>
      <div className="space-y-1.5">
        {Object.entries(country.indices).map(([label, { series, delta }]) => (
          <div key={label} className="flex items-center gap-2 text-xs">
            <span className="w-20 shrink-0 text-fg-faint">{label}</span>
            <Sparkline series={series} />
            <span className={`w-12 text-right font-mono tabular-nums ${delta > 0 ? "text-utopia" : delta < 0 ? "text-dystopia" : "text-fg-faint"}`}>
              {delta > 0 ? "+" : ""}
              {fmt(delta)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function Sparkline({ series }: { series: number[] }) {
  const W = 60;
  const H = 16;
  if (series.length < 2) return <span className="flex-1" />;
  const lo = Math.min(...series);
  const hi = Math.max(...series);
  const span = hi - lo || 1;
  const n = series.length - 1;
  const d = series
    .map((v, i) => `${i === 0 ? "M" : "L"}${((i / n) * W).toFixed(1)},${(H - ((v - lo) / span) * H).toFixed(1)}`)
    .join(" ");
  const up = series[series.length - 1] >= series[0];
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-4 flex-1" aria-hidden>
      <path d={d} fill="none" stroke={up ? "var(--utopia)" : "var(--dystopia)"} strokeWidth="1.5" />
    </svg>
  );
}

/** Animation LP : compteur qui monte/descend + barre de rang qui se remplit. */
function LpAnimation({ lp }: { lp: Required<GameResult["lp"]> }) {
  const [shown, setShown] = useState(lp.old_lp);
  useEffect(() => {
    const start = performance.now();
    const from = lp.old_lp;
    const to = lp.new_lp;
    let raf = 0;
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / 1400);
      setShown(Math.round(from + (to - from) * t));
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    const timer = setTimeout(() => (raf = requestAnimationFrame(tick)), 400);
    return () => {
      clearTimeout(timer);
      cancelAnimationFrame(raf);
    };
  }, [lp]);

  const progress = rankFor(shown);
  const gained = lp.applied;
  return (
    <Panel>
      <PanelTitle kicker="Points de ligue" title={gained >= 0 ? "Tu progresses" : "Tu recules"} />
      <div className="flex flex-wrap items-center gap-4">
        <RankBadge rank={progress.rank} />
        <div className="min-w-0 flex-1">
          <p className="flex items-baseline gap-2">
            <span className="text-lg font-semibold">{progress.rank.name}</span>
            <span className="font-mono text-sm tabular-nums text-fg-muted">{shown} LP</span>
            <span className={`font-mono text-sm font-semibold ${gained >= 0 ? "text-utopia" : "text-dystopia"}`}>
              {gained >= 0 ? "+" : ""}
              {gained} LP
            </span>
          </p>
          <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-surface-2">
            <div className="h-full rounded-full bg-accent transition-all duration-700" style={{ width: `${Math.round(progress.progress * 100)}%` }} />
          </div>
          <p className="mt-1 text-xs text-fg-faint">
            {progress.next ? `${progress.toNext} LP avant ${progress.next.name}` : "Rang maximal — Éminence."}
          </p>
        </div>
      </div>
    </Panel>
  );
}
