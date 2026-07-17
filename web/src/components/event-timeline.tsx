"use client";

/** La frise chronologique (G15) — sœur narrative du scrubber StageBand.
 *
 * Un cran par round : pastille (n° du round) posée SUR la courbe U simplifiée (le fil
 * EST la trajectoire), teintée par le delta U du round, badges des moments spéciaux
 * (⚖ motion, ⛔ suspension, ⚡ fait nouveau, 🏛 traité — glyphes fixés par la spec).
 * Le mapping est pur dans `lib/timeline.ts` ; `onSelect(index)` est 0-based, même
 * sémantique que le scrubber. Navigable au clavier (← / → bornées) via l'<ol>.
 */

import { useMemo } from "react";

import {
  buildTimeline,
  stepNotch,
  type TimelineBadge,
  type TimelineRound,
  type TimelineTone,
} from "@/lib/timeline";

const BADGES: Record<TimelineBadge, { glyph: string; label: string }> = {
  motion: { glyph: "⚖", label: "vote d'exclusion" },
  suspension: { glyph: "⛔", label: "pays exclu" },
  flash: { glyph: "⚡", label: "coup de théâtre" },
  treaty: { glyph: "🏛", label: "traité signé" },
};

const TONE_CLASS: Record<TimelineTone, string> = {
  utopia: "border-utopia text-utopia",
  dystopia: "border-dystopia text-dystopia",
  flat: "border-edge-strong text-fg-muted",
};

const STRIP_PX = 56; // hauteur du fil (h-14) — la pastille se place sur la courbe
const DOT_PX = 28; // h-7

/** Position verticale (0..1 → bande 15 %..85 % du fil, comme la polyline). */
const yOf = (u: number) => (1 - u) * 0.7 + 0.15;

export function EventTimeline({
  rounds,
  selected,
  onSelect,
}: {
  rounds: TimelineRound[];
  selected: number | null; // cran ouvert (0-based) ; null = aucun
  onSelect: (index: number) => void;
}) {
  const notches = useMemo(() => buildTimeline(rounds), [rounds]);
  if (notches.length === 0) return null;

  const points = notches
    .map((n, i) => `${((i + 0.5) / notches.length) * 100},${yOf(n.u) * 100}`)
    .join(" ");

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
    e.preventDefault();
    onSelect(stepNotch(selected ?? 0, e.key === "ArrowLeft" ? -1 : 1, notches.length));
  };

  return (
    <div className="overflow-x-auto pb-1">
      <ol
        aria-label="Frise chronologique des rounds"
        onKeyDown={onKeyDown}
        className="relative flex min-w-max"
      >
        {/* Le fil : la courbe U simplifiée + la ligne neutre 0,5 en pointillés. */}
        <svg
          aria-hidden
          viewBox="0 0 100 100"
          preserveAspectRatio="none"
          className="absolute inset-x-0 top-0 h-14 w-full"
        >
          <line
            x1="0"
            y1="50"
            x2="100"
            y2="50"
            className="stroke-edge"
            strokeWidth="0.6"
            strokeDasharray="1.5 2"
          />
          <polyline
            points={points}
            fill="none"
            className="stroke-accent/70"
            strokeWidth="1.2"
          />
        </svg>

        {notches.map((n) => (
          <li key={n.index} className="relative z-10 w-16 shrink-0 sm:w-24">
            <button
              onClick={() => onSelect(n.index)}
              aria-current={selected === n.index ? "step" : undefined}
              aria-label={`Round ${n.roundNo}${n.title ? ` — ${n.title}` : " — événement choisi par le jeu"}`}
              title={n.title || "Personne n'a inventé d'événement ce round : le jeu a choisi tout seul."}
              className="group flex w-full cursor-pointer flex-col items-center"
            >
              <span className="relative block h-14 w-full">
                <span
                  className={`absolute left-1/2 grid h-7 w-7 -translate-x-1/2 place-items-center rounded-full border-2 bg-surface font-mono text-[11px] tabular-nums transition-all group-hover:scale-110 ${TONE_CLASS[n.tone]} ${
                    selected === n.index ? "ring-2 ring-accent-bright ring-offset-2 ring-offset-background" : ""
                  }`}
                  style={{ top: yOf(n.u) * STRIP_PX - DOT_PX / 2 }}
                >
                  {n.roundNo}
                </span>
              </span>
              {/* Badges des moments spéciaux (hauteur réservée : zéro layout shift). */}
              <span className="flex h-5 items-center gap-0.5 text-[12px] leading-none">
                {n.badges.map((b) => (
                  <span key={b} role="img" aria-label={BADGES[b].label} title={BADGES[b].label}>
                    {BADGES[b].glyph}
                  </span>
                ))}
              </span>
              {/* Titre : masqué sur mobile (pastilles seules, le titre vit dans le panneau). */}
              <span
                className={`hidden w-full truncate px-1 text-center text-[10px] sm:block ${
                  selected === n.index ? "text-foreground" : "text-fg-faint"
                }`}
              >
                {n.title || "auto"}
                {n.human && " · inventé"}
              </span>
            </button>
          </li>
        ))}
      </ol>
    </div>
  );
}
