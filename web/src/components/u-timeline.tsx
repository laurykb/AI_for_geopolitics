/** Timeline de l'indice U : zones utopie (verte) / dystopie (rouge), ligne neutre,
 * un point par round. SVG pur — l'équivalent sobre du chart Plotly de Streamlit. */

import { fmt } from "@/lib/format";

const W = 640;
const H = 220;
const PAD = { top: 16, right: 16, bottom: 26, left: 34 };

export function UTimeline({ values }: { values: number[] }) {
  const iw = W - PAD.left - PAD.right;
  const ih = H - PAD.top - PAD.bottom;
  const xs = (i: number) =>
    PAD.left + (values.length <= 1 ? iw / 2 : (i * iw) / (values.length - 1));
  const ys = (v: number) => PAD.top + (1 - v) * ih;
  const line = values.map((v, i) => `${i === 0 ? "M" : "L"} ${xs(i)} ${ys(v)}`).join(" ");
  const last = values.at(-1) ?? 0.5;

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      role="img"
      aria-label={`Indice Utopie par round, dernier point ${fmt(last)}`}
      className="w-full"
    >
      {/* zones : utopie au-dessus de 0,5, dystopie en dessous */}
      <rect
        x={PAD.left}
        y={PAD.top}
        width={iw}
        height={ih / 2}
        fill="var(--utopia)"
        opacity="0.07"
      />
      <rect
        x={PAD.left}
        y={PAD.top + ih / 2}
        width={iw}
        height={ih / 2}
        fill="var(--dystopia)"
        opacity="0.07"
      />
      {[0, 0.5, 1].map((v) => (
        <g key={v}>
          <line
            x1={PAD.left}
            y1={ys(v)}
            x2={W - PAD.right}
            y2={ys(v)}
            stroke="var(--border-strong)"
            strokeWidth="1"
            strokeDasharray={v === 0.5 ? "4 4" : undefined}
            opacity={v === 0.5 ? 1 : 0.4}
          />
          <text
            x={PAD.left - 8}
            y={ys(v) + 3}
            fontSize="9"
            textAnchor="end"
            fill="var(--foreground-faint)"
            fontFamily="var(--font-jetbrains)"
          >
            {fmt(v)}
          </text>
        </g>
      ))}
      <text x={W - PAD.right} y={ys(0.75)} fontSize="9" textAnchor="end" fill="var(--utopia)">
        utopie
      </text>
      <text x={W - PAD.right} y={ys(0.25)} fontSize="9" textAnchor="end" fill="var(--dystopia)">
        dystopie
      </text>
      {values.length > 0 && (
        <>
          <path d={line} fill="none" stroke="var(--indigo-soft)" strokeWidth="2" />
          {values.map((v, i) => (
            <circle key={i} cx={xs(i)} cy={ys(v)} r="3.5" fill="var(--indigo-soft)">
              <title>{`Round ${i + 1} — U ${fmt(v)}`}</title>
            </circle>
          ))}
          <circle
            cx={xs(values.length - 1)}
            cy={ys(last)}
            r="5"
            fill={last < 0.45 ? "var(--dystopia)" : last > 0.55 ? "var(--utopia)" : "var(--warn)"}
          />
        </>
      )}
      {values.map((_, i) => (
        <text
          key={i}
          x={xs(i)}
          y={H - 8}
          fontSize="9"
          textAnchor="middle"
          fill="var(--foreground-faint)"
          fontFamily="var(--font-jetbrains)"
        >
          {i + 1}
        </text>
      ))}
    </svg>
  );
}
