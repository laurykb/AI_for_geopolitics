"use client";

import type { MarketView } from "@/lib/types";

/** Carte d'un marché de la partie (parité proto_9) : question, barre de cote « OUI % »,
 * pot en jeu, et un bouton de mise EXPLICITE par issue (« Miser 10 ₲ · YES/NO »). Le
 * portefeuille vit une seule fois AU-DESSUS de la liste — jamais dans la carte. */
export function MarketCard({
  market,
  busy,
  onBet,
  enjeuLabel,
}: {
  market: MarketView;
  busy: boolean;
  onBet: (outcomeId: string) => void;
  enjeuLabel: string;
}) {
  const yes = market.outcomes.find((o) => o.label.toUpperCase().includes("YES"));
  const yesPct = Math.round((yes?.price ?? 0.5) * 100);
  const closed = market.status !== "open";

  return (
    <div className="thk-cut-sm space-y-2 border border-edge bg-surface-2/40 p-3">
      <p className="text-xs text-foreground">{market.question}</p>

      {/* Barre de cote OUI (parité proto : .track / .fill vert utopie). */}
      <div className="flex items-center gap-2">
        <span className="w-16 shrink-0 font-mono text-[10px] font-semibold uppercase tracking-[0.08em] text-fg-faint tabular-nums">
          OUI {yesPct}%
        </span>
        <span
          className="relative h-1.5 flex-1 overflow-hidden rounded-full bg-muted"
          aria-hidden
        >
          <span
            className="absolute inset-y-0 left-0 rounded-full transition-[width] duration-500"
            style={{ width: `${yesPct}%`, background: "var(--utopia)" }}
          />
        </span>
      </div>

      <div className="flex gap-2">
        {market.outcomes.map((o) => (
          <button
            key={o.id}
            type="button"
            disabled={busy || closed}
            onClick={() => onBet(o.id)}
            className="thk-ghost flex-1 disabled:cursor-not-allowed disabled:opacity-40"
          >
            Miser 10 ₲ · {o.label}
          </button>
        ))}
      </div>

      <p className="text-[11px] text-fg-faint">
        💰 {Math.round(market.volume)} ₲ {enjeuLabel}
      </p>
    </div>
  );
}
