/** Blason de rang (G11 §2) — un écu sobre dont l'éclat monte avec le palier (0→6).
 * Pas d'emoji : une forme héraldique discrète, cohérente avec le langage de design. */

import type { Rank } from "@/lib/league";

const SIZE: Record<"sm" | "md", number> = { sm: 28, md: 44 };

export function RankBadge({ rank, size = "md" }: { rank: Rank; size?: "sm" | "md" }) {
  const px = SIZE[size];
  // L'opacité du remplissage croît avec le palier : Attaché terne → Éminence éclatante.
  const fill = 0.16 + (rank.tier / 6) * 0.7;
  const crown = rank.tier >= 5; // les deux plus hauts rangs gagnent une couronne discrète
  return (
    <svg
      width={px}
      height={px}
      viewBox="0 0 44 44"
      role="img"
      aria-label={`Blason ${rank.name}`}
      className="shrink-0"
    >
      <path
        d="M22 3 L38 8 V22 C38 32 31 38 22 41 C13 38 6 32 6 22 V8 Z"
        fill="var(--accent)"
        fillOpacity={fill}
        stroke="var(--accent-bright)"
        strokeOpacity={0.5 + (rank.tier / 6) * 0.5}
        strokeWidth="1.5"
      />
      {crown && (
        <path
          d="M15 15 l3 4 l4 -5 l4 5 l3 -4 v5 h-14 Z"
          fill="var(--accent-bright)"
          fillOpacity={0.9}
        />
      )}
      <text
        x="22"
        y={crown ? "31" : "27"}
        textAnchor="middle"
        fontSize="13"
        fontWeight="700"
        fill="var(--background)"
      >
        {rank.tier}
      </text>
    </svg>
  );
}
