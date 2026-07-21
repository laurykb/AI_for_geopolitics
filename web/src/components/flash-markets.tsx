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
  const [selected, setSelected] = useState<Record<string, string>>({});
  const [placed, setPlaced] = useState<Record<string, { label: string; cost?: number }>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
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

  const choose = (marketId: string, outcomeId: string) => {
    setSelected((current) => ({ ...current, [marketId]: outcomeId }));
    setErrors((current) => {
      const next = { ...current };
      delete next[marketId];
      return next;
    });
  };

  const bet = async (market: FlashMarket) => {
    const outcome = market.outcomes.find((item) => item.id === selected[market.id]);
    if (!outcome) return;
    const label = outcomeLabel(outcome.label);
    setBusy(market.id);
    setErrors((current) => {
      const next = { ...current };
      delete next[market.id];
      return next;
    });
    try {
      const account = await ensureAccount();
      const trade = await placeBet(account.id, market.id, outcome.id, STAKE);
      setPlaced((current) => ({
        ...current,
        [market.id]: {
          label,
          cost: typeof trade.cost === "number" ? trade.cost : undefined,
        },
      }));
      onBet(); // rafraîchit les cotes
    } catch (e) {
      setErrors((current) => ({ ...current, [market.id]: humanizeError(e) }));
    } finally {
      setBusy(null);
    }
  };

  return (
    <div data-tour="betting" className="pointer-events-auto absolute inset-x-3 top-3 z-20 max-h-[calc(100%-1.5rem)] overflow-y-auto overscroll-contain rounded-lg border border-accent-bright/50 bg-surface/95 p-3 shadow-[0_12px_32px_-12px_rgba(0,0,0,0.7)] backdrop-blur sm:left-auto sm:w-80">
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
        {open.map((m) => {
          const selectedOutcome = m.outcomes.find((item) => item.id === selected[m.id]);
          const confirmed = placed[m.id];
          return (
            <div key={m.id} className="rounded-md border border-edge bg-surface-2 p-2.5">
              <p className="mb-2 break-words text-xs leading-snug text-fg-muted">{m.question}</p>
              {confirmed ? (
                <div
                  role="status"
                  className="rounded-md border border-good/40 bg-good/10 px-2.5 py-2 text-xs text-good"
                >
                  <span className="block font-semibold">✓ {t("flash.pari-confirme")}</span>
                  <span className="mt-0.5 block text-fg-muted">
                    {confirmed.label} · {STAKE} {t("flash.parts")}
                    {confirmed.cost !== undefined
                      ? ` · ${t("flash.cout").replace("{cost}", confirmed.cost.toFixed(1))}`
                      : ""}
                  </span>
                </div>
              ) : (
                <>
                  <div className="grid grid-cols-2 gap-1.5">
                    {m.outcomes.map((o) => {
                      const active = selected[m.id] === o.id;
                      return (
                        <button
                          key={o.id}
                          type="button"
                          aria-pressed={active}
                          onClick={() => choose(m.id, o.id)}
                          disabled={busy !== null}
                          className={`min-w-0 rounded border px-2 py-1.5 text-xs font-medium transition-colors disabled:opacity-50 ${
                            active
                              ? "border-accent-bright bg-accent/15 text-accent-bright"
                              : "border-edge-strong hover:border-accent hover:text-accent-bright"
                          }`}
                        >
                          <span className="block truncate">{outcomeLabel(o.label)}</span>
                          <span className="block font-mono text-[11px] tabular-nums text-fg-faint">
                            {Math.round(o.price * 100)} %
                          </span>
                        </button>
                      );
                    })}
                  </div>
                  <div className="mt-2 flex flex-wrap items-center gap-2 border-t border-edge pt-2">
                    <p className="min-w-0 flex-1 text-[11px] leading-snug text-fg-faint">
                      {selectedOutcome
                        ? t("flash.choix")
                            .replace("{label}", outcomeLabel(selectedOutcome.label))
                            .replace("{stake}", String(STAKE))
                        : t("flash.choisir")}
                    </p>
                    <button
                      type="button"
                      onClick={() => void bet(m)}
                      disabled={!selectedOutcome || busy !== null}
                      className="cursor-pointer rounded-md bg-accent px-3 py-1.5 text-xs font-semibold text-background transition-colors hover:bg-accent-bright disabled:cursor-not-allowed disabled:opacity-40"
                    >
                      {busy === m.id ? t("flash.validation") : t("flash.valider")}
                    </button>
                  </div>
                </>
              )}
              {errors[m.id] && (
                <p role="alert" className="mt-2 text-[11px] leading-snug text-bad">
                  {errors[m.id]}
                </p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
