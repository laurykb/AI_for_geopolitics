/** Trajectoire Utopie–Dystopie : arc U, cinq axes, étincelle d'historique. */

import { fmt } from "@/lib/format";
import { AXIS_LABELS, type TrajectoryState } from "@/lib/types";

import { Meter, Panel, PanelTitle } from "./ui";

function uColor(u: number): string {
  return u < 0.45 ? "var(--dystopia)" : u > 0.55 ? "var(--utopia)" : "var(--warn)";
}

/** Demi-arc gradué dystopie → utopie, aiguille sur U. SVG pur, sans dépendance. */
export function UtopiaDial({ utopia, size = 190 }: { utopia: number; size?: number }) {
  const u = Math.max(0, Math.min(1, utopia));
  const r = 74;
  const cx = 90;
  const cy = 86;
  const angle = Math.PI * (1 - u); // 0 → gauche (dystopie), 1 → droite (utopie)
  const nx = cx + (r - 12) * Math.cos(angle);
  const ny = cy - (r - 12) * Math.sin(angle);
  return (
    <svg
      viewBox="0 0 180 104"
      width={size}
      role="img"
      aria-label={`Indice utopie ${fmt(u)} sur 1`}
    >
      <defs>
        <linearGradient id="u-scale" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor="var(--dystopia)" />
          <stop offset="50%" stopColor="var(--warn)" />
          <stop offset="100%" stopColor="var(--utopia)" />
        </linearGradient>
      </defs>
      <path
        d={`M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${cx + r} ${cy}`}
        fill="none"
        stroke="url(#u-scale)"
        strokeWidth="7"
        strokeLinecap="round"
        opacity="0.85"
      />
      <line
        x1={cx}
        y1={cy}
        x2={nx}
        y2={ny}
        stroke="var(--foreground)"
        strokeWidth="2"
        strokeLinecap="round"
      />
      <circle cx={cx} cy={cy} r="3.5" fill="var(--foreground)" />
      <text x={cx - r} y={cy + 14} fontSize="8" fill="var(--foreground-faint)">
        Dystopie
      </text>
      <text x={cx + r} y={cy + 14} fontSize="8" fill="var(--foreground-faint)" textAnchor="end">
        Utopie
      </text>
      <text
        x={cx}
        y={cy - 18}
        fontSize="20"
        fontWeight="600"
        fill={uColor(u)}
        textAnchor="middle"
        fontFamily="var(--font-jetbrains)"
      >
        {fmt(u)}
      </text>
    </svg>
  );
}

/** Étincelle de l'historique de U (SVG). Trait neutre, dernier point coloré. */
export function USpark({
  values,
  width = 240,
  height = 48,
}: {
  values: number[];
  width?: number;
  height?: number;
}) {
  if (values.length === 0) return null;
  const pad = 4;
  const xs = (i: number) =>
    values.length === 1 ? width / 2 : pad + (i * (width - 2 * pad)) / (values.length - 1);
  const ys = (v: number) => height - pad - v * (height - 2 * pad);
  const path = values.map((v, i) => `${i === 0 ? "M" : "L"} ${xs(i)} ${ys(v)}`).join(" ");
  const last = values[values.length - 1];
  return (
    <svg viewBox={`0 0 ${width} ${height}`} width={width} height={height} aria-hidden>
      <line
        x1={pad}
        y1={ys(0.5)}
        x2={width - pad}
        y2={ys(0.5)}
        stroke="var(--border-strong)"
        strokeDasharray="3 4"
        strokeWidth="1"
      />
      <path d={path} fill="none" stroke="var(--indigo-soft)" strokeWidth="1.5" />
      <circle cx={xs(values.length - 1)} cy={ys(last)} r="3" fill={uColor(last)} />
    </svg>
  );
}

export function TrajectoryPanel({
  state,
  history,
}: {
  state: TrajectoryState;
  history: number[];
}) {
  return (
    <Panel>
      <PanelTitle
        kicker="Trajectoire du monde"
        title="Utopie – Dystopie"
        hint="Indice composite [0,1] : cinq axes pondérés (coordination, agentivité humaine, distribution du pouvoir, transparence, bien-être). Il observe le monde, il ne l'influence pas."
      />
      <div className="flex flex-col items-center gap-2">
        <UtopiaDial utopia={state.utopia} />
        {history.length > 1 && <USpark values={history} />}
      </div>
      <div className="mt-4 space-y-3">
        {Object.entries(state.axes).map(([axis, value]) => (
          <Meter
            key={axis}
            label={AXIS_LABELS[axis] ?? axis}
            value={value}
            invert
            tone="neutral"
          />
        ))}
      </div>
      {state.explanation && (
        <p className="mt-4 border-t border-edge pt-3 text-xs leading-relaxed text-fg-faint">
          {state.explanation}
        </p>
      )}
    </Panel>
  );
}
