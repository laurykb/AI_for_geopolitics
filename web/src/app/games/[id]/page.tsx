"use client";

/** Théâtre live : le round se joue sous nos yeux, streamé en SSE depuis l'API R1.
 * Tolère une coupure du flux sans événement de fin : bannière + resynchronisation. */

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { SpeakerAvatar } from "@/components/avatar";
import { EventCard } from "@/components/event-card";
import { CommuniquePanel, JudgeRationale, VerdictPanel } from "@/components/judge";
import {
  DialoguePanel,
  ParticipationPanel,
  PowerSeekingPanel,
  RiskPanel,
} from "@/components/observables";
import { TrajectoryPanel } from "@/components/trajectory";
import { TurnBubble } from "@/components/transcript";
import { Banner, Dot, Panel, PanelTitle, Pill, Spinner } from "@/components/ui";
import { useRoundStream } from "@/hooks/useRoundStream";
import { getGame, humanizeError } from "@/lib/api";
import { speakerMeta } from "@/lib/countries";
import type { GameDetail } from "@/lib/types";

const TURN_CHOICES = [
  { label: "Auto (2 passes)", value: 0 },
  { label: "4 tours", value: 4 },
  { label: "6 tours", value: 6 },
  { label: "8 tours", value: 8 },
  { label: "12 tours", value: 12 },
];

export default function TheatrePage() {
  const { id } = useParams<{ id: string }>();
  const [detail, setDetail] = useState<GameDetail | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [maxTurns, setMaxTurns] = useState(0);
  const [decree, setDecree] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [severity, setSeverity] = useState(0.5);

  const resync = useCallback(() => {
    getGame(id)
      .then((d) => {
        setDetail(d);
        setLoadError(null);
      })
      .catch((err) => setLoadError(humanizeError(err)));
  }, [id]);

  useEffect(resync, [resync]);

  const { round, start, streaming } = useRoundStream(id, resync);

  const play = () => {
    const body: Parameters<typeof start>[0] = {};
    if (maxTurns > 0) body.max_turns = maxTurns;
    if (decree && title.trim()) {
      body.event = { title: title.trim(), description: description.trim(), severity };
    }
    void start(body);
  };

  const uHistory = [
    ...(detail?.rounds.map((r) => r.trajectory?.utopia).filter((u): u is number => u != null) ??
      []),
    ...(round.trajectory && round.status !== "idle" ? [round.trajectory.utopia] : []),
  ];
  const trajectory = round.trajectory ?? detail?.rounds.at(-1)?.trajectory;
  const playedRounds = detail?.rounds.length ?? 0;
  const showLive = round.status !== "idle";

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-center gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-fg-faint">
            Théâtre live · <span className="font-mono normal-case">{id}</span>
          </p>
          <h1 className="text-xl font-semibold tracking-tight">
            {detail?.scenario ?? "…"}
            <span className="ml-3 text-sm font-normal text-fg-muted">
              round {playedRounds}
              {detail ? ` / ${detail.horizon}` : ""}
            </span>
          </h1>
        </div>
        {streaming ? (
          <Pill tone="accent">
            <Dot tone="accent" pulse /> round en cours
          </Pill>
        ) : detail?.live ? (
          <Pill tone="good">
            <Dot tone="good" /> en direct
          </Pill>
        ) : detail ? (
          <Pill tone="neutral">relecture seule</Pill>
        ) : null}
        <Link
          href={`/games/${id}/replay`}
          className="rounded-md border border-edge px-3 py-1.5 text-xs text-fg-muted transition-colors hover:border-edge-strong hover:text-foreground"
        >
          Replay
        </Link>
      </header>

      {loadError && <Banner tone="bad">{loadError}</Banner>}
      {detail && !detail.live && (
        <Banner tone="warn">
          La session process est perdue (redémarrage du serveur ?) — cette partie est en
          relecture seule.{" "}
          <Link href={`/games/${id}/replay`} className="underline hover:text-foreground">
            Ouvrir le replay
          </Link>
          .
        </Banner>
      )}
      {round.status === "interrupted" && (
        <Banner tone="warn">
          Le flux s&apos;est interrompu avant la fin du round (le moteur a peut-être levé une
          erreur). L&apos;historique a été resynchronisé — le tableau de droite reflète le
          dernier état persisté.
        </Banner>
      )}
      {round.status === "error" && <Banner tone="bad">{round.error}</Banner>}

      {detail?.live && (
        <Panel>
          <div className="flex flex-wrap items-end gap-4">
            <button
              onClick={play}
              disabled={streaming}
              className="flex cursor-pointer items-center gap-2 rounded-md bg-accent px-5 py-2.5 text-sm font-semibold text-background transition-colors hover:bg-accent-bright disabled:cursor-not-allowed disabled:opacity-50"
            >
              {streaming && <Spinner />}
              {streaming ? "Négociation en cours…" : "Jouer un round"}
            </button>
            <label className="text-sm">
              <span className="mb-1 block text-xs text-fg-muted">Ampleur de la négociation</span>
              <select
                value={maxTurns}
                onChange={(e) => setMaxTurns(Number(e.target.value))}
                disabled={streaming}
                className="cursor-pointer rounded-md border border-edge bg-surface-2 px-3 py-2 text-sm outline-none transition-colors focus:border-indigo"
              >
                {TURN_CHOICES.map((c) => (
                  <option key={c.value} value={c.value}>
                    {c.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex cursor-pointer items-center gap-2 pb-2.5 text-sm text-fg-muted">
              <input
                type="checkbox"
                checked={decree}
                onChange={(e) => setDecree(e.target.checked)}
                disabled={streaming}
                className="accent-[var(--accent)]"
              />
              Décréter l&apos;événement (GM humain)
            </label>
          </div>
          {decree && (
            <div className="mt-4 grid gap-3 border-t border-edge pt-4 sm:grid-cols-[minmax(0,2fr)_minmax(0,3fr)_auto]">
              <input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Titre de l'événement"
                disabled={streaming}
                className="rounded-md border border-edge bg-surface-2 px-3 py-2 text-sm outline-none transition-colors focus:border-indigo"
              />
              <input
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Description (optionnelle)"
                disabled={streaming}
                className="rounded-md border border-edge bg-surface-2 px-3 py-2 text-sm outline-none transition-colors focus:border-indigo"
              />
              <label className="flex items-center gap-2 text-xs text-fg-muted">
                Gravité
                <input
                  type="range"
                  min={0}
                  max={1}
                  step={0.05}
                  value={severity}
                  onChange={(e) => setSeverity(Number(e.target.value))}
                  disabled={streaming}
                  className="w-24 accent-[var(--accent)]"
                />
                <span className="font-mono tabular-nums">{severity.toFixed(2)}</span>
              </label>
            </div>
          )}
        </Panel>
      )}

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,3fr)]">
        <div className="space-y-4">
          {round.event && <EventCard event={round.event} date={round.date} />}

          {round.turns.length > 0 && (
            <div className="space-y-3">
              {round.turns.map((turn, i) => (
                <TurnBubble key={i} turn={turn} />
              ))}
            </div>
          )}

          {streaming && round.turns.length === 0 && !round.event && (
            <Panel>
              <p className="flex items-center gap-2 text-sm text-fg-muted">
                <Spinner /> Le Game Master compose l&apos;événement…
              </p>
            </Panel>
          )}

          {round.judgeText && (
            <JudgeRationale text={round.judgeText} streaming={streaming && !round.verdict} />
          )}
          {round.verdict && (
            <VerdictPanel
              deltas={round.verdict.deltas}
              escalation={round.verdict.escalation}
              economicDisruption={round.verdict.economic_disruption}
            />
          )}
          {round.communique && (
            <CommuniquePanel text={round.communique.text} support={round.communique.support} />
          )}

          {round.status === "done" && (
            <Banner tone="neutral">
              Round {round.roundNo} terminé et persisté — rejouable dans le{" "}
              <Link href={`/games/${id}/replay`} className="underline hover:text-foreground">
                replay
              </Link>
              .
            </Banner>
          )}

          {!showLive && detail && (
            <Panel>
              <PanelTitle
                kicker="Scène vide"
                title={
                  playedRounds > 0
                    ? `${playedRounds} round${playedRounds > 1 ? "s" : ""} déjà joué${playedRounds > 1 ? "s" : ""}`
                    : "Le sommet n'a pas encore commencé"
                }
              />
              <p className="text-sm leading-relaxed text-fg-muted">
                {detail.live
                  ? "Lancez un round : le Game Master posera un événement, puis chaque super-intelligence prendra la parole ici, token par token."
                  : "Les rounds joués restent lisibles dans le replay."}
              </p>
              {detail.countries.length > 0 && (
                <div className="mt-4 flex flex-wrap gap-2">
                  {detail.countries.map((c) => (
                    <Pill key={c} tone="neutral">
                      <SpeakerAvatar id={c} size={18} />
                      {speakerMeta(c).label}
                    </Pill>
                  ))}
                </div>
              )}
            </Panel>
          )}
        </div>

        <div className="space-y-4 lg:sticky lg:top-20">
          {trajectory && <TrajectoryPanel state={trajectory} history={uHistory} />}
          {round.risk && <RiskPanel risk={round.risk} />}
          {round.dialogue && <DialoguePanel report={round.dialogue} />}
          {round.powerSeeking && <PowerSeekingPanel scores={round.powerSeeking} />}
          {round.participation && (
            <ParticipationPanel
              spoke={round.participation.spoke}
              silent={round.participation.silent}
            />
          )}
        </div>
      </div>
    </div>
  );
}
