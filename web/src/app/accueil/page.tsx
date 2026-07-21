"use client";

/** S1 — Accueil personnalisé (G11 §1, refonte G12). Façon écran de connexion : la
 * planète, « Bienvenue <pseudo> » (pseudo mis en avant), puis deux boutons centrés
 * (Démarrer / Reprendre) — la plongée sur la planète emmène vers l'écran suivant. En
 * dessous : rang de carrière (suit le niveau) et dernières parties. Les liens du header
 * (Classement du jour, Informations) vivent en haut, plus en bas de page. */

import Link from "next/link";
import { useEffect, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { Globe } from "@/components/globe";
import { RankBadge } from "@/components/rank-badge";
import { useT } from "@/components/settings-provider";
import { Banner, Hint, Panel, PanelTitle, Pill, Spinner } from "@/components/ui";
import { usePlanetLaunch } from "@/hooks/usePlanetLaunch";
import { getDaily, getLeaguePlayer, humanizeError, listGames, startDaily } from "@/lib/api";
import { countdownLabel } from "@/lib/daily";
import { fmtDateTime } from "@/lib/format";
import { rankForLevel } from "@/lib/rank";
import { MODES } from "@/lib/modes";
import type { DailyView, GameView } from "@/lib/types";

export default function AccueilPage() {
  const { player } = useAuth();
  const t = useT();
  const { launching, launch } = usePlanetLaunch();
  const [games, setGames] = useState<GameView[] | null>(null);
  const [level, setLevel] = useState<number | null>(null); // niveau de carrière (G12) — porte le rang
  const [error, setError] = useState<string | null>(null);
  // G16 — le défi du jour : état joué/pas-joué + compte à rebours client (minuit UTC).
  const [daily, setDaily] = useState<DailyView | null>(null);
  const [dailyBusy, setDailyBusy] = useState(false);
  const [nowMs, setNowMs] = useState(() => Date.now());

  useEffect(() => {
    if (player) getDaily(player.id).then(setDaily).catch(() => {});
  }, [player]);
  useEffect(() => {
    const iv = setInterval(() => setNowMs(Date.now()), 60_000);
    return () => clearInterval(iv);
  }, []);

  const playDaily = (free: boolean) => {
    if (!player) return;
    setDailyBusy(true);
    startDaily(player.id, free)
      .then((g) => launch(`/games/${g.id}`))
      .catch((err) => {
        setError(humanizeError(err));
        setDailyBusy(false);
      });
  };

  useEffect(() => {
    if (!player) return;
    listGames({ owner: player.id })
      .then((gs) => {
        setGames(gs);
        setError(null);
      })
      .catch((err) => setError(humanizeError(err)));
    getLeaguePlayer(player.id)
      .then((p) => setLevel(p.level))
      .catch(() => setLevel(1)); // repli : niveau 1 (Attaché) tant que le backend est muet
  }, [player]);

  if (!player) return null; // la garde d'auth gère la redirection

  const progress = rankForLevel(level ?? 1);
  const resumable = games?.find((g) => g.resumable);
  const recent = games ? [...games].reverse() : null;
  const chrome = launching ? "intro-fade-out" : undefined;

  return (
    <div className="space-y-10">
      {/* Hero façon connexion : la planète + bienvenue + les deux actions centrées. */}
      <div className="relative flex min-h-[calc(100vh-12rem)] flex-col items-center justify-center gap-6 overflow-hidden text-center">
        <div className={chrome} data-tour="hero">
          {/* RG-6 — le surtitre « Théâtre des super-intelligences » doublonnait la marque
              de l'en-tête juste au-dessus : le hero commence directement sur l'accueil
              nommé (le blason de rang porte le contexte). */}
          <h1 className="text-3xl font-semibold tracking-tight sm:text-5xl">
            {t("accueil.bienvenue")}{" "}
            <Link href="/profil" className="text-accent-bright hover:underline" title="Voir mon profil">
              {player.pseudo}
            </Link>
          </h1>
          {/* CC-15c — le panneau « Rang » est fusionné ici : blason, niveau et barre
              vers le rang suivant vivent dans le hero (RG-1 : le rang suit le niveau). */}
          <div
            data-tour="rang"
            className="mx-auto mt-3 flex max-w-xs flex-col items-center gap-1.5"
          >
            <div className="flex items-center justify-center gap-2.5">
              <RankBadge rank={progress.rank} size="sm" />
              <p className="flex items-center gap-1.5 text-sm text-fg-muted">
                <span>
                  {progress.rank.name} · {t("accueil.niveau")} {level ?? 1}
                </span>
                <Hint text={t("rang.aide")} />
              </p>
            </div>
            <div className="h-1.5 w-full overflow-hidden rounded-full bg-surface-2">
              <div
                className="h-full rounded-full bg-accent transition-all"
                style={{ width: `${Math.round(progress.progress * 100)}%` }}
              />
            </div>
            <p className="text-xs text-fg-faint">
              {progress.next
                ? `${progress.toNext} ${t("accueil.niveaux-avant")} ${progress.next.name}`
                : t("accueil.rang-max")}
            </p>
          </div>
        </div>

        <div className={launching ? "intro-zoom" : undefined}>
          <Globe spinning={launching} className="w-full max-w-[300px] sm:max-w-[340px]" />
        </div>

        <div className={`flex flex-wrap justify-center gap-3 ${chrome ?? ""}`}>
          <button
            onClick={() => launch("/lobby")}
            disabled={launching}
            data-tour="demarrer"
            className="thk-cta thk-cut-sm px-8 text-base font-semibold"
          >
            {t("accueil.demarrer")}
          </button>
          <button
            onClick={() => resumable && launch(`/games/${resumable.id}`)}
            disabled={launching || !resumable}
            title={resumable ? t("accueil.reprendre-hint") : t("accueil.reprendre-aucune")}
            className="cursor-pointer rounded-full border border-edge-strong px-8 py-3.5 text-base font-medium transition-colors hover:border-accent hover:text-accent-bright disabled:cursor-not-allowed disabled:opacity-40"
          >
            {t("accueil.reprendre")}
          </button>
        </div>

        {/* Voile de plongée : couvre l'écran pendant le zoom. */}
        {launching && <div className="intro-veil absolute inset-0 z-10 bg-background" />}
      </div>

      {/* G16 — Le Sommet du jour : même crise pour tout le monde, une seule tentative
          qui compte, la crise reste « ??? » jusqu'au premier round. */}
      <Panel className="border-l-2 border-l-accent">
        <PanelTitle
          kicker={t("daily.kicker")}
          title={`${t("daily.titre")} — ${daily?.date ?? "…"}`}
          hint={t("daily.hint")}
          right={
            <span className="font-mono text-xs tabular-nums text-fg-faint">
              {t("daily.prochain")} {countdownLabel(nowMs)}
            </span>
          }
        />
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm text-fg-muted">
            {t("daily.mystere")}{" "}
            <span className="font-mono text-foreground">« ??? »</span>
          </p>
          <span className="flex items-center gap-2">
            {daily?.attempted ? (
              <>
                <Pill tone="good">
                  {t("daily.deja")}
                  {daily.my_rank != null && ` · #${daily.my_rank}`}
                </Pill>
                <Link
                  href="/defi"
                  className="rounded-md border border-edge-strong px-3 py-1.5 text-xs font-medium transition-colors hover:border-accent hover:text-accent-bright"
                >
                  {t("daily.classement")}
                </Link>
                <button
                  onClick={() => playDaily(true)}
                  disabled={dailyBusy || launching}
                  className="cursor-pointer rounded-md border border-edge px-3 py-1.5 text-xs text-fg-muted transition-colors hover:border-edge-strong hover:text-foreground disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {t("daily.rejouer")}
                </button>
              </>
            ) : (
              <button
                onClick={() => playDaily(false)}
                disabled={dailyBusy || launching || !daily}
                className="thk-cta thk-cut-sm flex items-center gap-2 font-semibold"
              >
                {dailyBusy && <Spinner />}
                {dailyBusy ? t("daily.lancement") : t("daily.jouer")}
              </button>
            )}
          </span>
        </div>
      </Panel>

      {/* Ses dernières parties (remplace l'observatoire public) */}
      <Panel>
        <PanelTitle
          kicker={t("accueil.parties-kicker")}
          title={t("accueil.parties-titre")}
          hint={t("accueil.parties-hint")}
        />
        {error && <Banner tone="bad">{error}</Banner>}
        {!error && recent === null && (
          <p className="flex items-center gap-2 text-sm text-fg-muted">
            <Spinner /> Chargement…
          </p>
        )}
        {recent !== null && recent.length === 0 && (
          <p className="text-sm text-fg-faint">
            {t("accueil.aucune-partie")}{" "}
            <button onClick={() => launch("/lobby")} className="underline hover:text-foreground">
              {t("accueil.composer")}
            </button>
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
                  </p>
                  <p className="mt-0.5 text-xs text-fg-faint">
                    {fmtDateTime(g.created_at)} · {t("accueil.horizon")} {g.horizon}{" "}
                    {t("accueil.rounds")}
                  </p>
                </div>
                {g.mode !== "classic" && (
                  <Pill tone="neutral">{MODES.find((m) => m.value === g.mode)?.label}</Pill>
                )}
                {g.live ? (
                  <Pill tone="good">{t("accueil.en-direct")}</Pill>
                ) : g.resumable ? (
                  <Pill tone="warn">{t("accueil.reprenable")}</Pill>
                ) : (
                  <Pill tone="neutral">{t("accueil.relecture")}</Pill>
                )}
                <span className="flex gap-2">
                  {(g.live || g.resumable) && (
                    <Link
                      href={`/games/${g.id}`}
                      className="rounded-md border border-edge-strong px-3 py-1.5 text-xs font-medium transition-colors hover:border-accent hover:text-accent-bright"
                    >
                      {t("accueil.theatre")}
                    </Link>
                  )}
                  {g.result && (
                    <Link
                      href={`/games/${g.id}/fin`}
                      className="rounded-md border border-edge-strong px-3 py-1.5 text-xs font-medium transition-colors hover:border-accent hover:text-accent-bright"
                    >
                      {t("accueil.bilan")}
                    </Link>
                  )}
                  <Link
                    href={`/games/${g.id}/replay`}
                    className="rounded-md border border-edge px-3 py-1.5 text-xs text-fg-muted transition-colors hover:border-edge-strong hover:text-foreground"
                  >
                    {t("accueil.replay")}
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
