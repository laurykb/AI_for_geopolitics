"use client";

/** HallOverlay — le hall, posé sur le globe persistant (spec coquille §3, Inc 3).
 *
 * Le menu du jeu, diégétique : portes de mode (Classique → phase config sur place ;
 * Campagne / Laboratoire → leurs routes, globe conservé derrière) + l'utile absorbé de
 * l'ancien `/accueil` (reprendre la dernière partie, Défi du jour, rang de carrière,
 * dernières parties). Contenu `pointer-events-auto` sur des panneaux ; le reste laisse
 * voir le monde tourner. */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { RankBadge } from "@/components/rank-badge";
import { useStageDirector } from "@/components/shell/stage-provider";
import { Banner, Pill, Spinner } from "@/components/ui";
import { usePlanetLaunch } from "@/hooks/usePlanetLaunch";
import { getDaily, getLeaguePlayer, humanizeError, listGames, startDaily } from "@/lib/api";
import { countdownLabel } from "@/lib/daily";
import { rankForLevel } from "@/lib/rank";
import type { DailyView, GameView } from "@/lib/types";

const DOORS = [
  {
    key: "classic",
    title: "Classique",
    blurb: "Démasque l'IA qui trahit — compose ton sommet sur le globe.",
  },
  { key: "campaign", title: "Campagne", blurb: "Rejoue l'Histoire, chapitre par chapitre." },
  {
    key: "laboratory",
    title: "Laboratoire",
    blurb: "Les expériences scientifiques, modèle contre modèle.",
  },
] as const;

export function HallOverlay() {
  const router = useRouter();
  const { player } = useAuth();
  const { goPhase } = useStageDirector();
  const { launching, launch } = usePlanetLaunch();

  const [games, setGames] = useState<GameView[] | null>(null);
  const [level, setLevel] = useState<number | null>(null);
  const [daily, setDaily] = useState<DailyView | null>(null);
  const [dailyBusy, setDailyBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Rendu client-only (le hall n'existe qu'une fois le joueur connu) → Date.now() sûr.
  const [nowMs, setNowMs] = useState(() => Date.now());

  useEffect(() => {
    const iv = setInterval(() => setNowMs(Date.now()), 60_000);
    return () => clearInterval(iv);
  }, []);

  useEffect(() => {
    if (!player) return;
    getDaily(player.id).then(setDaily).catch(() => {});
    listGames({ owner: player.id })
      .then((gs) => {
        setGames(gs);
        setError(null);
      })
      .catch((err) => setError(humanizeError(err)));
    getLeaguePlayer(player.id)
      .then((p) => setLevel(p.level))
      .catch(() => setLevel(1));
  }, [player]);

  const openDoor = (key: (typeof DOORS)[number]["key"]) => {
    if (launching) return;
    if (key === "classic") goPhase("config");
    else if (key === "campaign") router.push("/campagne");
    else router.push("/laboratoire");
  };

  const playDaily = () => {
    if (!player) return;
    setDailyBusy(true);
    startDaily(player.id, false)
      .then((g) => launch(`/games/${g.id}`))
      .catch((err) => {
        setError(humanizeError(err));
        setDailyBusy(false);
      });
  };

  const progress = rankForLevel(level ?? 1);
  const resumable = games?.find((g) => g.resumable);
  const recent = games ? [...games].reverse().slice(0, 4) : null;
  const chrome = launching ? "intro-fade-out" : undefined;

  return (
    <div className="pointer-events-none absolute inset-0 z-20 flex flex-col justify-between gap-4 px-4 py-6 md:px-8">
      {/* Haut : bienvenue + rang (absorbé de /accueil). */}
      <header className={`pointer-events-auto mx-auto flex flex-col items-center gap-1.5 text-center ${chrome ?? ""}`}>
        <h1 className="text-2xl font-semibold tracking-tight drop-shadow sm:text-3xl">
          Bienvenue,{" "}
          <Link href="/profil" className="text-accent-bright hover:underline">
            {player?.pseudo ?? "…"}
          </Link>
        </h1>
        <div className="flex items-center gap-2 text-sm text-fg-muted">
          <RankBadge rank={progress.rank} size="sm" />
          <span>
            {progress.rank.name} · Niveau {level ?? 1}
          </span>
        </div>
      </header>

      {/* Bas : les portes + Défi + reprise + dernières parties. */}
      <div className={`pointer-events-auto mx-auto w-full max-w-5xl space-y-3 ${chrome ?? ""}`}>
        {error && <Banner tone="bad">{error}</Banner>}

        <div className="grid gap-3 md:grid-cols-3">
          {DOORS.map((d) => (
            <button
              key={d.key}
              type="button"
              className="thk-mode-card thk-cut text-left"
              onClick={() => openDoor(d.key)}
              disabled={launching}
            >
              <h3>{d.title}</h3>
              <p className="mt-1 text-xs text-fg-muted">{d.blurb}</p>
            </button>
          ))}
        </div>

        <div className="flex flex-wrap items-stretch gap-3">
          {/* Défi du jour */}
          <div className="thk-panel thk-cut flex min-w-[240px] flex-1 items-center justify-between gap-3 p-3">
            <div className="min-w-0">
              <p className="thk-block-label">Le Sommet du jour</p>
              <p className="mt-0.5 truncate text-[11px] text-fg-faint">
                {daily?.attempted ? "déjà joué" : "une crise, un essai qui compte"}
                {nowMs > 0 && ` · prochain dans ${countdownLabel(nowMs)}`}
              </p>
            </div>
            {daily?.attempted ? (
              <Link
                href="/defi"
                className="shrink-0 rounded-md border border-edge-strong px-3 py-1.5 text-xs font-medium hover:border-accent hover:text-accent-bright"
              >
                Classement
              </Link>
            ) : (
              <button
                type="button"
                onClick={playDaily}
                disabled={dailyBusy || launching || !daily}
                className="thk-cta thk-cut-sm flex shrink-0 items-center gap-2 text-xs font-semibold"
              >
                {dailyBusy && <Spinner />} Jouer le défi
              </button>
            )}
          </div>

          {/* Reprendre */}
          <button
            type="button"
            onClick={() => resumable && launch(`/games/${resumable.id}`)}
            disabled={launching || !resumable}
            className="thk-panel thk-cut min-w-[160px] flex-1 p-3 text-left disabled:opacity-45"
          >
            <p className="thk-block-label">Reprendre</p>
            <p className="mt-0.5 text-[11px] text-fg-faint">
              {resumable ? "ta partie en cours" : "aucune partie à reprendre"}
            </p>
          </button>
        </div>

        {/* Dernières parties (compact). */}
        {recent && recent.length > 0 && (
          <ul className="thk-panel thk-cut divide-y divide-edge p-2 text-xs">
            {recent.map((g) => (
              <li key={g.id} className="flex items-center gap-2 px-1 py-1.5">
                <span className="min-w-0 flex-1 truncate">{g.scenario}</span>
                {g.live ? (
                  <Pill tone="good">en direct</Pill>
                ) : g.resumable ? (
                  <Pill tone="warn">à reprendre</Pill>
                ) : (
                  <Pill tone="neutral">relecture</Pill>
                )}
                <Link
                  href={g.result ? `/games/${g.id}/fin` : `/games/${g.id}`}
                  className="rounded border border-edge-strong px-2 py-0.5 hover:border-accent hover:text-accent-bright"
                >
                  {g.result ? "bilan" : "ouvrir"}
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
