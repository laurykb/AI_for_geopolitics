"use client";

/** Marchés vivants (G12 §1) — la pop-up de paris posée SUR la carte du monde : à chaque
 * événement les paris s'ouvrent (« 📈 Tu peux parier ! »), le joueur parie inline
 * (OUI/NON avec les cotes), et le Spectateur suit tout en accéléré. */

import { useState } from "react";

import { useT } from "@/components/settings-provider";
import { Hint } from "@/components/ui";
import { humanizeError } from "@/lib/api";
import { ensureAccount, placeBet, type FlashMarket } from "@/lib/market";

const STAKE = 5; // parts par pari (argent fictif)

export function FlashMarketsPopup({
  markets,
  onBet,
  dismissible = true,
}: {
  markets: FlashMarket[];
  onBet: () => void;
  dismissible?: boolean; // le Spectateur ne peut pas masquer sa seule interface de jeu
}) {
  const t = useT();
  const [busy, setBusy] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [dismissed, setDismissed] = useState(false);

  const open = markets.filter((m) => m.status === "open");
  if (dismissed || open.length === 0) return null;

  // Libellé d'issue lisible : OUI/NON traduits quand l'API parle YES/NO.
  const outcomeLabel = (label: string) =>
    label.toUpperCase().includes("YES")
      ? t("flash.oui")
      : label.toUpperCase().includes("NO")
        ? t("flash.non")
        : label;

  const bet = async (marketId: string, outcomeId: string, label: string) => {
    setBusy(outcomeId);
    setNote(null);
    try {
      const account = await ensureAccount();
      await placeBet(account.id, marketId, outcomeId, STAKE);
      setNote(t("flash.pari-place").replace("{label}", label));
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
        <span className="flex items-center gap-1.5 text-xs font-semibold text-accent-bright">
          {t("flash.titre")}
          <Hint text={t("flash.mise-aide")} />
        </span>
        {dismissible && (
          <button
            onClick={() => setDismissed(true)}
            aria-label={t("flash.masquer")}
            className="text-xs text-fg-faint transition-colors hover:text-foreground"
          >
            ✕
          </button>
        )}
      </div>
      <div className="space-y-2">
        {open.map((m) => (
          <div key={m.id} className="rounded-md border border-edge bg-surface-2 p-2">
            <p className="mb-1.5 text-xs leading-snug text-fg-muted">{m.question}</p>
            <div className="flex gap-1.5">
              {m.outcomes.map((o) => (
                <button
                  key={o.id}
                  onClick={() => bet(m.id, o.id, outcomeLabel(o.label))}
                  disabled={busy !== null}
                  className="flex-1 rounded border border-edge-strong px-2 py-1 text-xs font-medium transition-colors hover:border-accent hover:text-accent-bright disabled:opacity-50"
                >
                  {outcomeLabel(o.label)} · {Math.round(o.price * 100)} %
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
