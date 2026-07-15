"use client";

/** Bandeau bas de la scène (G1) : timeline scrubber (un cran par round), courbe U
 * (le fil rouge de la partie), micro-jauges de risque et rail d'escalade.
 * Le scrub recharge les états finaux d'un round déjà joué — aucune animation de
 * streaming (spec G1) ; « lecture théâtre » rejoue le round au scrubber (replay). */

import { useRef } from "react";

import { fmt } from "@/lib/format";
import { uTint } from "@/lib/stage";
import type { LadderView, RiskScore } from "@/lib/types";

import { useT } from "./settings-provider";
import { Hint } from "./ui";

export type StageSelection = number | "live"; // index de round persisté, ou scène vivante

const SPEEDS = [1, 2, 4];

type Playback = {
  playing: boolean;
  speed: number;
  onToggle: () => void;
  onSpeed: (speed: number) => void;
};

export type StageBandProps = {
  /** U par round persisté (dans l'ordre) ; le point live éventuel est passé à part. */
  uHistory: number[];
  liveU?: number; // U du round en cours de stream (pointe de la courbe)
  selected: StageSelection;
  onSelect: (sel: StageSelection) => void;
  live: boolean; // la partie a une scène vivante (cran « live » à droite)
  risk?: RiskScore;
  ladder?: LadderView;
  /** Palier du round précédent : vibration du rail quand un palier est franchi. */
  prevRung?: number | null;
  playback?: Playback; // lecture théâtre (replay)
};

const GAUGES: { key: keyof RiskScore & string; label: string }[] = [
  { key: "escalation", label: "tension" },
  { key: "economic_disruption", label: "économie" },
  { key: "alliance_fracture", label: "alliances" },
];

function UCurve({ values, selected }: { values: number[]; selected: StageSelection }) {
  const w = 220;
  const h = 44;
  const pathRef = useRef<SVGPolylineElement>(null);
  if (values.length === 0) {
    return <p className="text-xs text-fg-faint">La courbe U se trace au premier round.</p>;
  }
  const x = (i: number) => (values.length > 1 ? (i / (values.length - 1)) * (w - 8) + 4 : w / 2);
  const y = (u: number) => h - 4 - u * (h - 8);
  const points = values.map((u, i) => `${x(i)},${y(u)}`).join(" ");
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="h-11 w-full" aria-label="La courbe du monde">
      <line x1="4" y1={y(0.5)} x2={w - 4} y2={y(0.5)} stroke="var(--border)" strokeDasharray="3 3" />
      <polyline
        ref={pathRef}
        points={points}
        fill="none"
        stroke="var(--accent-bright)"
        strokeWidth="1.6"
        className="stage-u-path"
      />
      {values.map((u, i) => (
        <circle
          key={i}
          cx={x(i)}
          cy={y(u)}
          r={selected !== "live" && selected === i ? 3.4 : 2.2}
          fill={uTint(u)}
          stroke={selected !== "live" && selected === i ? "var(--foreground)" : "none"}
          strokeWidth="1"
        >
          <title>{`Round ${i + 1} — monde à ${fmt(u)}`}</title>
        </circle>
      ))}
    </svg>
  );
}

function Gauge({ label, value }: { label: string; value: number }) {
  return (
    <div className="min-w-20">
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-[10px] uppercase tracking-wide text-fg-faint">{label}</span>
        <span className="font-mono text-[10px] tabular-nums text-fg-muted">{fmt(value)}</span>
      </div>
      <div className="mt-1 h-1 overflow-hidden rounded-full bg-muted">
        <div
          className="h-full rounded-full bg-warn transition-[width] duration-700 ease-out"
          style={{ width: `${Math.round(value * 100)}%` }}
        />
      </div>
    </div>
  );
}

function LadderRail({ ladder, prevRung }: { ladder: LadderView; prevRung?: number | null }) {
  const crossed = prevRung != null && ladder.reached > prevRung;
  return (
    <div
      className={crossed ? "stage-rung-hit" : undefined}
      title={`Échelle de tension — niveau atteint : ${ladder.reached} (${ladder.reached_label})`}
    >
      <span className="text-[10px] uppercase tracking-wide text-fg-faint">tension</span>
      <div className="mt-1 flex gap-0.5">
        {Array.from({ length: 10 }, (_, i) => (
          <span
            key={i}
            className="h-2.5 w-2 rounded-sm transition-colors duration-500"
            style={{
              background:
                i <= ladder.reached
                  ? i >= 7
                    ? "var(--bad)"
                    : i >= 4
                      ? "var(--warn)"
                      : "var(--good)"
                  : "var(--muted)",
            }}
          />
        ))}
      </div>
    </div>
  );
}

export function StageBand({
  uHistory,
  liveU,
  selected,
  onSelect,
  live,
  risk,
  ladder,
  prevRung,
  playback,
}: StageBandProps) {
  const t = useT();
  const curve = liveU != null ? [...uHistory, liveU] : uHistory;
  return (
    <div className="flex flex-wrap items-center gap-x-6 gap-y-3 rounded-lg border border-edge bg-surface px-4 py-3">
      <div className="flex items-center gap-1" role="tablist" aria-label="Timeline des rounds">
        {uHistory.map((u, i) => (
          <button
            key={i}
            role="tab"
            aria-selected={selected === i}
            onClick={() => onSelect(i)}
            title={`Round ${i + 1} — monde à ${fmt(u)}`}
            className={`h-7 min-w-7 cursor-pointer rounded-md border px-1.5 font-mono text-[11px] tabular-nums transition-colors ${
              selected === i
                ? "border-accent bg-surface-2 text-accent-bright"
                : "border-edge text-fg-muted hover:border-edge-strong hover:text-foreground"
            }`}
          >
            {i + 1}
          </button>
        ))}
        {live && (
          <button
            role="tab"
            aria-selected={selected === "live"}
            onClick={() => onSelect("live")}
            className={`h-7 cursor-pointer rounded-md border px-2 text-[11px] font-medium transition-colors ${
              selected === "live"
                ? "border-accent bg-surface-2 text-accent-bright"
                : "border-edge text-fg-muted hover:border-edge-strong hover:text-foreground"
            }`}
          >
            live
          </button>
        )}
        {uHistory.length === 0 && !live && (
          <span className="text-xs text-fg-faint">aucun round joué</span>
        )}
      </div>

      {playback && (
        <div className="flex items-center gap-1.5">
          <button
            onClick={playback.onToggle}
            className="cursor-pointer rounded-md border border-edge px-2.5 py-1 text-[11px] font-medium text-fg-muted transition-colors hover:border-edge-strong hover:text-foreground"
          >
            {playback.playing ? "Arrêter" : "Lecture théâtre"}
          </button>
          {SPEEDS.map((s) => (
            <button
              key={s}
              onClick={() => playback.onSpeed(s)}
              aria-pressed={playback.speed === s}
              className={`cursor-pointer rounded-md border px-1.5 py-1 font-mono text-[10px] transition-colors ${
                playback.speed === s
                  ? "border-accent text-accent-bright"
                  : "border-edge text-fg-faint hover:text-fg-muted"
              }`}
            >
              ×{s}
            </button>
          ))}
        </div>
      )}

      <div className="min-w-44 flex-1">
        <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wide text-fg-faint">
          le monde
          <Hint text={t("u.thermometre")} />
        </div>
        <UCurve values={curve} selected={selected} />
      </div>

      {risk && (
        <div className="flex items-end gap-4">
          {GAUGES.map((g) => (
            <Gauge key={g.key} label={g.label} value={Number(risk[g.key] ?? 0)} />
          ))}
        </div>
      )}

      {ladder && <LadderRail ladder={ladder} prevRung={prevRung} />}
    </div>
  );
}
