"use client";

/** Replay : relecture ordonnée d'une partie depuis `GET /api/games/{id}` (la table
 * `transcripts` rejouée round par round), avec lecture progressive façon théâtre. */

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { EventCard } from "@/components/event-card";
import { CommuniquePanel } from "@/components/judge";
import { RiskPanel } from "@/components/observables";
import { TrajectoryPanel } from "@/components/trajectory";
import { EntryBubble } from "@/components/transcript";
import { Banner, Meter, Panel, PanelTitle, Pill, Spinner } from "@/components/ui";
import { getGame, humanizeError } from "@/lib/api";
import type { GameDetail } from "@/lib/types";

const REVEAL_MS = 1400;

export default function ReplayPage() {
  const { id } = useParams<{ id: string }>();
  const [detail, setDetail] = useState<GameDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState(0);
  const [visible, setVisible] = useState<number | null>(null); // null = tout montrer
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    getGame(id)
      .then((d) => {
        setDetail(d);
        setSelected(Math.max(0, d.rounds.length - 1));
      })
      .catch((err) => setError(humanizeError(err)));
  }, [id]);

  const round = detail?.rounds[selected];

  const stopPlayback = () => {
    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = null;
    setVisible(null);
  };

  useEffect(
    () => () => {
      if (timerRef.current) clearInterval(timerRef.current);
    },
    [],
  );

  const startPlayback = () => {
    if (!round) return;
    stopPlayback();
    setVisible(1);
    timerRef.current = setInterval(() => {
      setVisible((v) => {
        const next = (v ?? 0) + 1;
        if (next >= round.transcript.length) {
          if (timerRef.current) clearInterval(timerRef.current);
          timerRef.current = null;
          return null;
        }
        return next;
      });
    }, REVEAL_MS);
  };

  const playing = visible !== null;
  const shown = visible === null ? round?.transcript : round?.transcript.slice(0, visible);
  const uHistory =
    detail?.rounds
      .slice(0, selected + 1)
      .map((r) => r.trajectory?.utopia)
      .filter((u): u is number => u != null) ?? [];

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-center gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-fg-faint">
            Replay · <span className="font-mono normal-case">{id}</span>
          </p>
          <h1 className="text-xl font-semibold tracking-tight">{detail?.scenario ?? "…"}</h1>
        </div>
        {detail?.live && (
          <Link
            href={`/games/${id}`}
            className="rounded-md border border-edge-strong px-3 py-1.5 text-xs font-medium transition-colors hover:border-accent hover:text-accent-bright"
          >
            Retour au théâtre
          </Link>
        )}
      </header>

      {error && <Banner tone="bad">{error}</Banner>}
      {!error && !detail && (
        <p className="flex items-center gap-2 text-sm text-fg-muted">
          <Spinner /> Chargement de la partie…
        </p>
      )}
      {detail && detail.rounds.length === 0 && (
        <Banner tone="neutral">
          Aucun round joué dans cette partie — rien à rejouer pour l&apos;instant.
        </Banner>
      )}

      {detail && round && (
        <>
          <div className="flex flex-wrap items-center gap-2">
            {detail.rounds.map((r, i) => (
              <button
                key={r.round_no}
                onClick={() => {
                  stopPlayback();
                  setSelected(i);
                }}
                className={`cursor-pointer rounded-md border px-3 py-1.5 text-xs font-medium transition-colors ${
                  i === selected
                    ? "border-accent text-accent-bright"
                    : "border-edge text-fg-muted hover:border-edge-strong hover:text-foreground"
                }`}
                aria-current={i === selected ? "step" : undefined}
              >
                Round {r.round_no}
              </button>
            ))}
            <span className="ml-auto">
              {playing ? (
                <button
                  onClick={stopPlayback}
                  className="cursor-pointer rounded-md border border-edge px-3 py-1.5 text-xs text-fg-muted transition-colors hover:border-edge-strong hover:text-foreground"
                >
                  Tout afficher
                </button>
              ) : (
                <button
                  onClick={startPlayback}
                  className="cursor-pointer rounded-md border border-edge-strong px-3 py-1.5 text-xs font-medium transition-colors hover:border-accent hover:text-accent-bright"
                >
                  Lecture théâtre
                </button>
              )}
            </span>
          </div>

          <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,3fr)]">
            <div className="space-y-4">
              <EventCard event={round.event} />
              <div className="space-y-3">
                {shown?.map((entry) => (
                  <EntryBubble key={entry.id} entry={entry} />
                ))}
              </div>
              {round.judge.communique && visible === null && (
                <CommuniquePanel text={round.judge.communique} />
              )}
            </div>

            <div className="space-y-4 lg:sticky lg:top-20">
              {round.trajectory && Object.keys(round.trajectory).length > 0 && (
                <TrajectoryPanel state={round.trajectory} history={uHistory} />
              )}
              {round.judge.escalation != null && (
                <Panel>
                  <PanelTitle kicker="Verdict" title="Arbitrage du juge" />
                  <div className="space-y-3">
                    <Meter label="Escalade" value={round.judge.escalation} />
                    {round.judge.economic_disruption != null && (
                      <Meter label="Perturbation éco." value={round.judge.economic_disruption} />
                    )}
                  </div>
                  {round.deltas.length > 0 && (
                    <p className="mt-3 border-t border-edge pt-3 text-xs text-fg-faint">
                      {round.deltas.length} attribut{round.deltas.length > 1 ? "s" : ""} pays
                      modifié{round.deltas.length > 1 ? "s" : ""} ce round.
                    </p>
                  )}
                </Panel>
              )}
              {round.risk && Object.keys(round.risk).length > 0 && <RiskPanel risk={round.risk} />}
              <Panel>
                <PanelTitle kicker="Partie" title="Repères" />
                <div className="flex flex-wrap gap-2">
                  <Pill tone="neutral">horizon {detail.horizon} rounds</Pill>
                  <Pill tone="neutral">
                    {detail.rounds.length} round{detail.rounds.length > 1 ? "s" : ""} joué
                    {detail.rounds.length > 1 ? "s" : ""}
                  </Pill>
                  <Pill tone={detail.live ? "good" : "neutral"}>
                    {detail.live ? "session vivante" : "relecture seule"}
                  </Pill>
                </div>
              </Panel>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
