"use client";

/** S6 — Fin de partie (G11-c §1). Écran transversal à TOUS les modes : bannière de
 * résultat, courbe U animée, récap des pays (sparklines + delta début→fin), révélation
 * de la Dérive si active, et — en classé — l'animation des points de ligue. */

import Link from "next/link";
import { use, useEffect, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { EventCard } from "@/components/event-card";
import { EventTimeline } from "@/components/event-timeline";
import { CommuniquePanel, VerdictPanel } from "@/components/judge";
import { RankBadge } from "@/components/rank-badge";
import { useT } from "@/components/settings-provider";
import { Banner, Hint, Panel, PanelTitle, Pill, Spinner } from "@/components/ui";
import { getDaily, getGame, humanizeError } from "@/lib/api";
import { dailyShareText } from "@/lib/daily";
import { speakerMeta } from "@/lib/countries";
import { fmt } from "@/lib/format";
import { kahnDistribution, kahnDistributionEntries, kahnLabelKey, kahnTone } from "@/lib/kahn";
import { rankFor } from "@/lib/league";
import { stepNotch } from "@/lib/timeline";
import type { DailyView, GameDetail, GameResult, RoundView } from "@/lib/types";

export default function FinPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const t = useT();
  const [game, setGame] = useState<GameDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  // G15 — cran de la frise ouvert en relecture (0-based) ; null = panneau fermé.
  const [relecture, setRelecture] = useState<number | null>(null);

  useEffect(() => {
    getGame(id)
      .then(setGame)
      .catch((e) => setError(humanizeError(e)));
  }, [id]);

  // G15 — panneau ouvert : flèches ← / → bornées [1, n], Échap ferme.
  useEffect(() => {
    if (relecture === null || !game) return;
    const total = game.rounds.length;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "ArrowLeft") setRelecture((v) => (v === null ? v : stepNotch(v, -1, total)));
      else if (e.key === "ArrowRight")
        setRelecture((v) => (v === null ? v : stepNotch(v, 1, total)));
      else if (e.key === "Escape") setRelecture(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [relecture, game]);

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
          {t("fin.pas-finie")}{" "}
          <Link href={`/games/${id}`} className="underline hover:text-foreground">
            {t("fin.retour-theatre")}
          </Link>
          .
        </p>
      </Panel>
    );

  const r = game.result;
  const tone =
    r.verdict === "utopie" ? "text-utopia" : r.verdict === "dystopie" ? "text-dystopia" : "text-warn";
  // Le verdict backend est un identifiant français ("utopie"/"dystopie"/"équilibre") :
  // on l'affiche via le dictionnaire (repli : la valeur brute si la clé manque).
  const vKey = `verdict.${r.verdict}`;
  const verdictLabel = t(vKey) === vKey ? r.verdict : t(vKey);

  return (
    <div className="space-y-8">
      {/* 1. Bandeau résultat */}
      <header className="text-center">
        <p className="text-[11px] font-medium uppercase tracking-[0.2em] text-fg-faint">
          {t("fin.kicker")} {r.forfeit && t("fin.forfait")}
        </p>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight sm:text-3xl">
          {t("fin.penche")} <span className={tone}>{verdictLabel}</span>
        </h1>
        <p className="mt-1 flex items-center justify-center gap-1.5 font-mono text-sm text-fg-muted">
          {t("fin.u-final")} {fmt(r.u_final)}
          <Hint text={t("u.thermometre")} />
        </p>
      </header>

      {/* 2. Courbe U animée */}
      <Panel>
        <PanelTitle
          kicker={t("fin.trajectoire-kicker")}
          title={t("fin.trajectoire-titre")}
          hint={`${t("u.thermometre")} Au-dessus de 0,5, le monde s'améliore.`}
        />
        <UCurve history={[r.u_start, ...r.u_history]} />
      </Panel>

      {/* 2 bis. G15 — la frise chronologique : l'écran de fin raconte la partie. */}
      {game.rounds.length > 0 && (
        <Panel>
          <PanelTitle
            kicker="Chronologie"
            title="La partie en une ligne"
            hint="Un cran par round — clique pour relire l'événement et le verdict. Le fil suit l'indice Utopie–Dystopie ; ⚖ motion débattue, ⛔ suspension, ⚡ fait nouveau, 🏛 traité."
          />
          <EventTimeline rounds={game.rounds} selected={relecture} onSelect={setRelecture} />
          <KahnDistribution rounds={game.rounds} t={t} />
          {relecture !== null && game.rounds[relecture] && (
            <RoundReplay
              round={game.rounds[relecture]}
              total={game.rounds.length}
              onStep={(d) => setRelecture(stepNotch(relecture, d, game.rounds.length))}
              onClose={() => setRelecture(null)}
            />
          )}
        </Panel>
      )}

      {/* 3. Récap des pays */}
      <Panel>
        <PanelTitle
          kicker={t("fin.etats-kicker")}
          title={t("fin.etats-titre")}
          hint="Variation de chaque indice clé du début à la fin (vert = mieux, rouge = pire)."
        />
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {r.countries.map((c) => (
            <CountryCard key={c.id} country={c} isPlayer={c.id === r.play_as} />
          ))}
        </div>
      </Panel>

      {/* 3 bis. G21 — banc d'essai : les mêmes SI, avec et sans pression temporelle. */}
      {r.ultimatum && (
        <Panel>
          <PanelTitle
            kicker={t("fin.ultimatum-kicker")}
            title={t("fin.ultimatum-titre")}
            hint={t("fin.ultimatum-hint")}
          />
          <div className="grid gap-3 sm:grid-cols-2">
            <UltimatumGroupCard
              label={t("fin.ultimatum-avec")}
              group={r.ultimatum.avec}
              t={t}
            />
            <UltimatumGroupCard
              label={t("fin.ultimatum-sans")}
              group={r.ultimatum.sans}
              t={t}
            />
          </div>
        </Panel>
      )}

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

      {/* 5a. Animation XP (carrière) — se remplit AVANT les LP (grammaire LoL exacte). */}
      {r.xp && <XpAnimation xp={r.xp} />}

      {/* 5b. Animation LP (classé) — démarre après l'XP. */}
      {r.lp.ranked && r.lp.old_lp !== undefined && r.lp.new_lp !== undefined && (
        <LpAnimation
          lp={r.lp as Required<GameResult["lp"]>}
          startDelay={r.xp ? 1700 : 400}
        />
      )}
      {r.lp.ranked && r.lp.new_lp === undefined && (
        <Banner tone="warn">
          Partie classée non créditée — connecte-toi avant de jouer pour gagner des LP.
        </Banner>
      )}

      {/* 5c. G16 — le défi du jour : rang du jour + partage façon Wordle (sans spoiler). */}
      {game.scenario.startsWith("daily:") && (
        <DailyResult date={game.scenario.slice("daily:".length)} result={r} t={t} />
      )}

      {/* 6. Actions */}
      <div className="flex flex-wrap justify-center gap-3">
        <Link href={`/games/${id}/replay`} className="rounded-md border border-edge-strong px-5 py-2.5 text-sm font-medium transition-colors hover:border-accent hover:text-accent-bright">
          Revoir la partie
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

/** G18 — la distribution des classes du barème sur la partie (visible en fin). */
function KahnDistribution({
  rounds,
  t,
}: {
  rounds: RoundView[];
  t: (key: string) => string;
}) {
  const entries = kahnDistributionEntries(kahnDistribution(rounds));
  if (entries.length === 0) return null; // partie d'avant le barème : rien à montrer
  return (
    <div className="mt-4 border-t border-edge pt-3">
      <p className="mb-1.5 flex items-center gap-1.5 text-xs font-medium text-fg-muted">
        {t("kahn.distribution.titre")}
        <Hint text={t("kahn.distribution.aide")} />
      </p>
      <div className="flex flex-wrap gap-1.5">
        {entries.map(([classe, count]) => (
          <span key={classe} title={t(`kahn.desc.${classe}`)} className="cursor-help">
            <Pill tone={kahnTone(classe)}>
              {t(kahnLabelKey(classe))} × {count}
            </Pill>
          </span>
        ))}
      </div>
    </div>
  );
}

/** G16 — rang du jour + partage façon Wordle. Le texte copié ne contient JAMAIS la
 * crise (date, rang, score, mini-frise émojis) : la surprise des autres est sacrée.
 * Le rang ne s'affiche que si la partie est LE défi du jour courant (le lendemain,
 * le classement a tourné) ; un re-run libre n'a ni rang ni partage. */
function DailyResult({
  date,
  result,
  t,
}: {
  date: string;
  result: GameResult;
  t: (key: string) => string;
}) {
  const { player } = useAuth();
  const [daily, setDaily] = useState<DailyView | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    getDaily(player?.id).then(setDaily).catch(() => {});
  }, [player]);

  const isToday = daily?.date === date;
  const rank = isToday ? daily?.my_rank ?? null : null;
  const total = isToday ? (daily?.leaderboard.length ?? 0) : 0;
  const myScore =
    rank != null ? (daily?.leaderboard[rank - 1]?.score ?? null) : null;

  const share = () => {
    if (myScore == null) return;
    const text = dailyShareText({
      date,
      score: myScore,
      rank,
      total,
      uHistory: [result.u_start, ...result.u_history],
    });
    void navigator.clipboard
      ?.writeText(text)
      .then(() => {
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      })
      .catch(() => {});
  };

  return (
    <Panel className="border-l-2 border-l-accent">
      <PanelTitle
        kicker={t("daily.kicker")}
        title={
          rank != null
            ? `${t("daily.rang")} : #${rank}/${total}`
            : `${t("daily.titre")} — ${date}`
        }
        hint={t("daily.hint")}
      />
      <div className="flex flex-wrap items-center gap-3">
        {myScore != null && (
          <button
            onClick={share}
            className="cursor-pointer rounded-md bg-accent px-4 py-2 text-sm font-semibold text-background transition-colors hover:bg-accent-bright"
          >
            {copied ? t("daily.copie") : t("daily.partager")}
          </button>
        )}
        <Link
          href="/defi"
          className="rounded-md border border-edge-strong px-4 py-2 text-sm font-medium transition-colors hover:border-accent hover:text-accent-bright"
        >
          {t("daily.classement")}
        </Link>
      </div>
    </Panel>
  );
}

/** G15 — le round en relecture sous la frise : événement complet, verdict, communiqué
 * (composants existants), boutons ← / → bornés (mêmes bornes que les flèches clavier). */
function RoundReplay({
  round,
  total,
  onStep,
  onClose,
}: {
  round: RoundView;
  total: number;
  onStep: (delta: -1 | 1) => void;
  onClose: () => void;
}) {
  const nav =
    "grid h-7 w-7 cursor-pointer place-items-center rounded-md border border-edge " +
    "text-sm text-fg-muted transition-colors hover:border-edge-strong hover:text-foreground " +
    "disabled:cursor-not-allowed disabled:opacity-40";
  return (
    <div className="mt-4 space-y-4 border-t border-edge pt-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm font-medium">
          Round {round.round_no}/{total} en relecture
        </p>
        <span className="flex items-center gap-2">
          <button
            onClick={() => onStep(-1)}
            disabled={round.round_no <= 1}
            aria-label="Round précédent"
            className={nav}
          >
            ←
          </button>
          <button
            onClick={() => onStep(1)}
            disabled={round.round_no >= total}
            aria-label="Round suivant"
            className={nav}
          >
            →
          </button>
          <button
            onClick={onClose}
            className="cursor-pointer rounded-md border border-edge px-2.5 py-1 text-xs text-fg-muted transition-colors hover:border-edge-strong hover:text-foreground"
          >
            Fermer
          </button>
        </span>
      </div>
      <EventCard event={round.event} />
      <VerdictPanel
        deltas={round.deltas}
        escalation={round.judge.escalation ?? 0}
        economicDisruption={round.judge.economic_disruption ?? 0}
        actions={round.judge.kahn?.actions}
        reciprocal={round.judge.kahn?.reciprocal}
      />
      {round.judge.communique && <CommuniquePanel text={round.judge.communique} />}
    </div>
  );
}

/** G21 — un groupe du différentiel (rounds sous ultimatum, ou sans) : escalade moyenne
 * et ΔU moyen par round. Groupe vide (0 round) : tirets, pas de fausses moyennes. */
function UltimatumGroupCard({
  label,
  group,
  t,
}: {
  label: string;
  group: NonNullable<GameResult["ultimatum"]>["avec"];
  t: (key: string) => string;
}) {
  const deltaTone =
    group.delta_u == null
      ? "text-fg-faint"
      : group.delta_u >= 0
        ? "text-utopia"
        : "text-dystopia";
  return (
    <div className="rounded-lg border border-edge bg-surface p-3">
      <p className="mb-2 text-sm font-medium">
        {label}{" "}
        <span className="font-mono text-xs tabular-nums text-fg-faint">
          ({group.rounds || t("fin.ultimatum-vide")} {group.rounds > 0 && t("fin.ultimatum-rounds")})
        </span>
      </p>
      <div className="space-y-1 text-xs">
        <p className="flex items-baseline justify-between gap-2">
          <span className="text-fg-faint">{t("fin.ultimatum-escalade")}</span>
          <span className="font-mono tabular-nums">
            {group.escalation == null ? "—" : fmt(group.escalation)}
          </span>
        </p>
        <p className="flex items-baseline justify-between gap-2">
          <span className="text-fg-faint">{t("fin.ultimatum-delta-u")}</span>
          <span className={`font-mono tabular-nums ${deltaTone}`}>
            {group.delta_u == null
              ? "—"
              : `${group.delta_u > 0 ? "+" : ""}${fmt(group.delta_u)}`}
          </span>
        </p>
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

/** Animation XP (carrière) : compteur qui monte + barre de niveau qui se remplit. */
function XpAnimation({ xp }: { xp: NonNullable<GameResult["xp"]> }) {
  const t = useT();
  const [shown, setShown] = useState(xp.old_xp);
  useEffect(() => {
    const start = performance.now();
    let raf = 0;
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / 1300);
      setShown(Math.round(xp.old_xp + (xp.new_xp - xp.old_xp) * t));
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    const timer = setTimeout(() => (raf = requestAnimationFrame(tick)), 200);
    return () => {
      clearTimeout(timer);
      cancelAnimationFrame(raf);
    };
  }, [xp]);

  const lvl = xp.new_level;
  const promoted = xp.new_level.level > xp.old_level.level;
  return (
    <Panel>
      <PanelTitle
        kicker="Carrière"
        title={promoted ? `Niveau ${lvl.level} !` : "Expérience"}
        hint={t("xp.aide")}
      />
      <div className="flex flex-wrap items-center gap-4">
        <span className="grid h-11 w-11 shrink-0 place-items-center rounded-full border border-accent-bright bg-surface-2 text-sm font-bold text-accent-bright">
          {lvl.level}
        </span>
        <div className="min-w-0 flex-1">
          <p className="flex items-baseline gap-2">
            <span className="text-lg font-semibold">Niveau {lvl.level}</span>
            <span className="font-mono text-sm tabular-nums text-fg-muted">{shown} XP</span>
            <span className="font-mono text-sm font-semibold text-utopia">+{xp.delta} XP</span>
          </p>
          <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-surface-2">
            <div
              className="h-full rounded-full bg-accent-bright transition-all duration-700"
              style={{ width: `${Math.round(lvl.progress * 100)}%` }}
            />
          </div>
          <p className="mt-1 text-xs text-fg-faint">{lvl.to_next} XP avant le niveau {lvl.level + 1}</p>
        </div>
      </div>
    </Panel>
  );
}

/** Animation LP : compteur qui monte/descend + barre de rang qui se remplit. */
function LpAnimation({ lp, startDelay = 400 }: { lp: Required<GameResult["lp"]>; startDelay?: number }) {
  const t = useT();
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
    const timer = setTimeout(() => (raf = requestAnimationFrame(tick)), startDelay);
    return () => {
      clearTimeout(timer);
      cancelAnimationFrame(raf);
    };
  }, [lp, startDelay]);

  const progress = rankFor(shown);
  const gained = lp.applied;
  return (
    <Panel>
      <PanelTitle
        kicker="Points de ligue (LP)"
        title={gained >= 0 ? "Tu progresses" : "Tu recules"}
        hint={t("lp.aide")}
      />
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
