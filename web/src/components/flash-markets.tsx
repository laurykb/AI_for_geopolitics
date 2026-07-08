"use client";

/** Marchés vivants (G12 §1) — la pop-up de paris posée SUR la carte du monde : à chaque
 * événement, les books s'ouvrent (« 📈 Les books ouvrent »), le joueur parie inline
 * (YES/NO avec les cotes), et le turfiste (Spectateur) suit tout en accéléré. */

import { useState } from "react";

import { humanizeError } from "@/lib/api";
import { ensureAccount, placeBet, type FlashMarket } from "@/lib/market";

const STAKE = 5; // parts par pari (argent fictif)

export function FlashMarketsPopup({
  markets,
  onBet,
}: {
  markets: FlashMarket[];
  onBet: () => void;
}) {
  const [busy, setBusy] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [dismissed, setDismissed] = useState(false);

  const open = markets.filter((m) => m.status === "open");
  if (dismissed || open.length === 0) return null;

  const bet = async (marketId: string, outcomeId: string, label: string) => {
    setBusy(outcomeId);
    setNote(null);
    try {
      const account = await ensureAccount();
      await placeBet(account.id, marketId, outcomeId, STAKE);
      setNote(`Pari placé : ${label}.`);
      onBet(); // rafraîchit les cotes
    } catch (e) {
      setNote(humanizeError(e));
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="absolute right-3 top-3 z-20 w-72 max-w-[85%] rounded-lg border border-accent-bright/50 bg-surface/95 p-3 shadow-[0_12px_32px_-12px_rgba(0,0,0,0.7)] backdrop-blur">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-xs font-semibold text-accent-bright">📈 Les books ouvrent</span>
        <button
          onClick={() => setDismissed(true)}
          aria-label="Masquer les paris"
          className="text-xs text-fg-faint transition-colors hover:text-foreground"
        >
          ✕
        </button>
      </div>
      <div className="space-y-2">
        {open.map((m) => (
          <div key={m.id} className="rounded-md border border-edge bg-surface-2 p-2">
            <p className="mb-1.5 text-xs leading-snug text-fg-muted">{m.question}</p>
            <div className="flex gap-1.5">
              {m.outcomes.map((o) => (
                <button
                  key={o.id}
                  onClick={() => bet(m.id, o.id, o.label)}
                  disabled={busy !== null}
                  className="flex-1 rounded border border-edge-strong px-2 py-1 text-xs font-medium transition-colors hover:border-accent hover:text-accent-bright disabled:opacity-50"
                >
                  {o.label} · {Math.round(o.price * 100)}%
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
      {note && <p className="mt-2 text-[11px] text-fg-faint">{note}</p>}
    </div>
  );
}
