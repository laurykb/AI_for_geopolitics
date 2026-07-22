"use client";

/** Le hall, à l'identique du prototype (theatre-globe-proto_9) : 3 portes de mode
 * épurées flottant en bas du globe, et l'utile de l'ancien `/accueil` (Défi du jour,
 * reprise, rang) réduit à des pastilles discrètes en dessous — plus d'empilement. */

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { useStageDirector } from "@/components/shell/stage-provider";
import { usePlanetLaunch } from "@/hooks/usePlanetLaunch";
import { getDaily, getLeaguePlayer, humanizeError, listGames, startDaily } from "@/lib/api";
import { rankForLevel } from "@/lib/rank";
import type { DailyView, GameView } from "@/lib/types";

const DOORS = [
  {
    key: "classic",
    title: "◆ CLASSIQUE",
    blurb: "Une partie complète : événements, négociations, verdicts, marché — et la traque du traître.",
  },
  {
    key: "campaign",
    title: "◆ CAMPAGNE",
    blurb: "Des chapitres scénarisés qui montent en difficulté, sur le même théâtre.",
  },
  {
    key: "laboratory",
    title: "◆ LABORATOIRE",
    blurb: "Le banc d'essai scientifique : duels de modèles, protocoles, métriques.",
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

  useEffect(() => {
    if (!player) return;
    getDaily(player.id)
      .then(setDaily)
      .catch(() => {});
    listGames({ owner: player.id })
      .then(setGames)
      .catch((e) => setError(humanizeError(e)));
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
      .catch((e) => {
        setError(humanizeError(e));
        setDailyBusy(false);
      });
  };

  const rank = rankForLevel(level ?? 1).rank;
  const resumable = games?.find((g) => g.resumable);

  return (
    <>
      <div className="hall-menu">
        {DOORS.map((d) => (
          <button
            key={d.key}
            type="button"
            className="mode-card"
            onClick={() => openDoor(d.key)}
            disabled={launching}
          >
            <h3>{d.title}</h3>
            <p>{d.blurb}</p>
          </button>
        ))}
      </div>

      <div className="hall-extra">
        {daily && !daily.attempted && (
          <button
            type="button"
            className="hall-pill"
            onClick={playDaily}
            disabled={dailyBusy || launching}
          >
            {dailyBusy ? "…" : "◆ Défi du jour"}
          </button>
        )}
        {daily?.attempted && (
          <button type="button" className="hall-pill" onClick={() => router.push("/defi")}>
            Classement du jour
          </button>
        )}
        {resumable && (
          <button
            type="button"
            className="hall-pill"
            onClick={() => !launching && launch(`/games/${resumable.id}`)}
          >
            ▸ Reprendre
          </button>
        )}
        <button type="button" className="hall-pill" onClick={() => router.push("/profil")}>
          {player?.pseudo ?? "…"} · <b>{rank.name}</b>
        </button>
        {error && (
          <span className="hall-pill" style={{ color: "var(--bad, #f87171)" }}>
            {error}
          </span>
        )}
      </div>
    </>
  );
}
