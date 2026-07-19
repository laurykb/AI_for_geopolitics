"use client";

import type { ReactNode } from "react";

import { SpeakerAvatar } from "@/components/avatar";
import { Dot, Spinner } from "@/components/ui";
import { speakerMeta } from "@/lib/countries";
import { canStartRound, phaseLabel, type GamePhase } from "@/lib/game-phase";

const phaseCopy = (phase: GamePhase) => {
  switch (phase) {
    case "ready":
      return "Lance le sommet quand tu es prêt.";
    case "round_running":
      return "Écoute les positions et repère les contradictions.";
    case "awaiting_player":
      return "Ta délégation a la parole.";
    case "awaiting_vote":
      return "Le sommet attend le bulletin de ton pays.";
    case "resolving":
      return "Le serveur consolide le verdict et les conséquences.";
    case "round_complete":
      return "Lis le bilan du round avant de continuer.";
    case "game_complete":
      return "Le sommet est clos. Ton bilan est prêt.";
    case "replay_only":
      return "Cette partie reste disponible en relecture.";
    case "disconnected":
      return "L'état enregistré est conservé. Une resynchronisation est possible.";
    case "error":
      return "Le round n'a pas pu aller à son terme.";
    case "loading":
      return "Récupération de l'état du sommet…";
  }
};

export function ActionDock({
  phase,
  playedRounds,
  horizon,
  speaking,
  primaryLabel,
  primaryBusy = false,
  primaryDisabled = false,
  onPrimary,
  children,
}: {
  phase: GamePhase;
  playedRounds: number;
  horizon: number;
  speaking?: string;
  primaryLabel?: string;
  primaryBusy?: boolean;
  primaryDisabled?: boolean;
  onPrimary?: () => void;
  children?: ReactNode;
}) {
  const progress = horizon > 0 ? Math.min(100, (playedRounds / horizon) * 100) : 0;
  const urgent = phase === "awaiting_player" || phase === "awaiting_vote";
  const active = phase === "round_running" || phase === "resolving";

  return (
    <section
      data-tour="action-dock"
      aria-label="Actions disponibles"
      className={`rounded-xl border bg-surface p-4 shadow-[0_20px_60px_-36px_rgba(0,0,0,0.95)] ${
        urgent ? "border-warn/70" : "border-edge"
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-fg-faint">
            Prochaine action
          </p>
          <h2 className="mt-1 flex items-center gap-2 text-sm font-semibold text-foreground">
            <Dot
              tone={urgent ? "warn" : active ? "accent" : phase === "error" ? "bad" : "good"}
              pulse={urgent || active}
            />
            {phaseLabel(phase)}
          </h2>
        </div>
        <span className="font-mono text-xs tabular-nums text-fg-faint">
          {playedRounds}/{horizon}
        </span>
      </div>

      <div className="mt-3 h-1 overflow-hidden rounded-full bg-muted" aria-hidden="true">
        <div
          className="h-full rounded-full bg-accent transition-[width] duration-500"
          style={{ width: `${progress}%` }}
        />
      </div>

      {speaking && (
        <div className="mt-3 flex items-center gap-2 rounded-lg border border-edge bg-surface-2/70 px-3 py-2">
          <SpeakerAvatar id={speaking} size={24} />
          <div className="min-w-0">
            <p className="text-[10px] uppercase tracking-[0.12em] text-fg-faint">À la tribune</p>
            <p className="truncate text-sm font-medium">{speakerMeta(speaking).label}</p>
          </div>
        </div>
      )}

      <p className="mt-3 text-xs leading-relaxed text-fg-muted">{phaseCopy(phase)}</p>

      {primaryLabel && onPrimary && canStartRound(phase) && phase !== "round_complete" && (
        <button
          data-tour="jouer"
          onClick={onPrimary}
          disabled={primaryDisabled}
          className="mt-4 flex w-full cursor-pointer items-center justify-center gap-2 rounded-lg bg-accent px-4 py-3 text-sm font-semibold text-background transition-colors hover:bg-accent-bright disabled:cursor-not-allowed disabled:opacity-50"
        >
          {primaryBusy && <Spinner />}
          {primaryLabel}
        </button>
      )}

      {children && <div className="mt-4 space-y-3 border-t border-edge pt-4">{children}</div>}
    </section>
  );
}

