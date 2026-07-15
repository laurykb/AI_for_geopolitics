"use client";

/** Marché de prédiction (argent fictif) : un marché par partie — « le monde finira-t-il
 * côté utopie ? » — coté en LMSR, résolu sur l'indice U final. Le marché observe les
 * super-intelligences, il ne les influence pas. */

import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { GameNav } from "@/components/game-nav";
import { Banner, Panel, PanelTitle, Pill, Spinner } from "@/components/ui";
import { UTimeline } from "@/components/u-timeline";
import { getGame, humanizeError } from "@/lib/api";
import { fmt, pct } from "@/lib/format";
import {
  ensureAccount,
  fetchLeaderboard,
  getGameMarket,
  openGameMarket,
  placeBet,
  resolveGameMarket,
} from "@/lib/market";
import type { AccountView, GameDetail, LeaderboardEntry, MarketView } from "@/lib/types";

export default function MarchePage() {
  const { id } = useParams<{ id: string }>();
  const [detail, setDetail] = useState<GameDetail | null>(null);
  const [market, setMarket] = useState<MarketView | null>(null);
  const [account, setAccount] = useState<AccountView | null>(null);
  const [board, setBoard] = useState<LeaderboardEntry[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [shares, setShares] = useState(5);
  const [busy, setBusy] = useState(false);
  const [confirmClose, setConfirmClose] = useState(false);

  const refresh = useCallback(() => {
    Promise.all([getGame(id), getGameMarket(id), ensureAccount(), fetchLeaderboard()])
      .then(([d, m, a, l]) => {
        setDetail(d);
        setMarket(m);
        setAccount(a);
        setBoard(l);
        setError(null);
      })
      .catch((err) => setError(humanizeError(err)));
  }, [id]);

  useEffect(refresh, [refresh]);

  const uHistory =
    detail?.rounds.map((r) => r.trajectory?.utopia).filter((u): u is number => u != null) ?? [];
  const lastU = uHistory.at(-1) ?? 0.5;
  const horizonReached = detail !== null && detail.rounds.length >= detail.horizon;

  const act = async (action: () => Promise<unknown>, done?: string) => {
    setBusy(true);
    setNotice(null);
    try {
      await action();
      if (done) setNotice(done);
      refresh();
    } catch (err) {
      setNotice(humanizeError(err));
    } finally {
      setBusy(false);
    }
  };

  const bet = (outcomeId: string, label: string) =>
    act(async () => {
      if (!account || !market) return;
      const trade = await placeBet(account.id, market.id, outcomeId, shares);
      const cost = typeof trade.cost === "number" ? ` pour ${fmt(trade.cost)} crédits` : "";
      setNotice(`Pari placé : ${fmt(shares)} parts ${label}${cost}.`);
    });

  const close = () =>
    act(
      () => resolveGameMarket(id, lastU),
      `Marché clôturé sur U = ${fmt(lastU)} (${lastU > 0.5 ? "utopie — YES" : "dystopie — NO"}).`,
    );

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-center gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-fg-faint">
            Marché · <span className="font-mono normal-case">{id}</span>
          </p>
          <h1 className="text-xl font-semibold tracking-tight">{detail?.scenario ?? "…"}</h1>
        </div>
        <GameNav id={id} />
      </header>

      {error && <Banner tone="bad">{error}</Banner>}
      {!error && !detail && (
        <p className="flex items-center gap-2 text-sm text-fg-muted">
          <Spinner /> Chargement du marché…
        </p>
      )}

      {detail && (
        <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,3fr)]">
          <div className="space-y-4" data-tour="cotes">
            <Panel className="border-l-2 border-l-accent">
              <PanelTitle
                kicker="Marché de la partie"
                title="Le monde finira-t-il côté utopie ?"
                hint="Un seul marché par partie, coté en LMSR (argent fictif). YES = l'indice U final dépasse 0,5 à l'horizon. Le marché observe, il n'influence pas les super-intelligences."
                right={
                  market ? (
                    market.status === "resolved" ? (
                      <Pill tone={market.resolved_outcome?.includes("YES") ? "good" : "bad"}>
                        résolu
                      </Pill>
                    ) : (
                      <Pill tone="accent">ouvert</Pill>
                    )
                  ) : undefined
                }
              />
              {!market && (
                <div className="space-y-3">
                  <p className="text-sm text-fg-muted">
                    Le marché de cette partie n&apos;est pas encore ouvert.
                  </p>
                  <button
                    onClick={() => act(() => openGameMarket(id), "Marché ouvert — cotes 50/50.")}
                    disabled={busy}
                    className="cursor-pointer rounded-md bg-accent px-4 py-2 text-sm font-semibold text-background transition-colors hover:bg-accent-bright disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    Ouvrir le marché
                  </button>
                </div>
              )}
              {market && (
                <>
                  <div className="grid grid-cols-2 gap-4">
                    {market.outcomes.map((o) => {
                      const yes = o.label.toUpperCase().includes("YES");
                      const winner =
                        market.status === "resolved" && market.resolved_outcome === o.id;
                      return (
                        <div
                          key={o.id}
                          className={`rounded-lg border p-4 ${winner ? "border-accent" : "border-edge"} bg-surface-2`}
                        >
                          <p className="mb-1 flex items-center justify-between text-xs text-fg-muted">
                            <span>{yes ? "YES — utopie" : "NO — dystopie"}</span>
                            {winner && <Pill tone="accent">gagnant</Pill>}
                          </p>
                          <p
                            className="font-mono text-2xl font-semibold tabular-nums"
                            style={{ color: yes ? "var(--utopia)" : "var(--dystopia)" }}
                          >
                            {pct(o.price)}
                          </p>
                          {market.status === "open" && (
                            <button
                              onClick={() => bet(o.id, o.label)}
                              disabled={busy || !account}
                              className="mt-3 w-full cursor-pointer rounded-md border border-edge-strong px-3 py-1.5 text-xs font-medium transition-colors hover:border-accent hover:text-accent-bright disabled:cursor-not-allowed disabled:opacity-50"
                            >
                              Parier {fmt(shares)} parts
                            </button>
                          )}
                        </div>
                      );
                    })}
                  </div>
                  {market.status === "open" && (
                    <div className="mt-4 flex flex-wrap items-center gap-4 border-t border-edge pt-4">
                      <label className="flex items-center gap-2 text-xs text-fg-muted">
                        Parts
                        <input
                          type="number"
                          min={1}
                          max={100}
                          value={shares}
                          onChange={(e) => setShares(Number(e.target.value))}
                          className="w-20 rounded-md border border-edge bg-surface-2 px-2 py-1.5 font-mono text-sm outline-none transition-colors focus:border-indigo"
                        />
                      </label>
                      <span className="text-xs text-fg-faint">
                        {fmt(market.volume)} crédits déjà pariés
                      </span>
                      <span className="ml-auto">
                        {confirmClose ? (
                          <span className="flex items-center gap-2">
                            <span className="text-xs text-warn">
                              Clôturer sur U = {fmt(lastU)} ?
                            </span>
                            <button
                              onClick={() => {
                                setConfirmClose(false);
                                void close();
                              }}
                              disabled={busy}
                              className="cursor-pointer rounded-md bg-accent px-3 py-1.5 text-xs font-semibold text-background hover:bg-accent-bright"
                            >
                              Confirmer
                            </button>
                            <button
                              onClick={() => setConfirmClose(false)}
                              className="cursor-pointer rounded-md border border-edge px-3 py-1.5 text-xs text-fg-muted hover:text-foreground"
                            >
                              Annuler
                            </button>
                          </span>
                        ) : (
                          <button
                            onClick={() => setConfirmClose(true)}
                            disabled={busy || uHistory.length === 0}
                            title={
                              horizonReached
                                ? "Horizon atteint — résoudre sur l'indice final"
                                : "Résoudre maintenant sur le dernier indice connu"
                            }
                            className="cursor-pointer rounded-md border border-edge-strong px-3 py-1.5 text-xs font-medium transition-colors hover:border-accent hover:text-accent-bright disabled:cursor-not-allowed disabled:opacity-50"
                          >
                            {horizonReached ? "Clôturer (horizon atteint)" : "Clôturer"}
                          </button>
                        )}
                      </span>
                    </div>
                  )}
                </>
              )}
              {notice && <p className="mt-3 text-xs text-fg-muted">{notice}</p>}
            </Panel>

            <Panel>
              <PanelTitle
                kicker="Trajectoire"
                title="Indice U par round"
                hint="La donnée que le marché essaie de prédire : au-dessus de 0,5 le monde penche utopie, en dessous dystopie."
              />
              {uHistory.length === 0 ? (
                <p className="text-sm text-fg-faint">
                  Aucun round joué — la timeline apparaîtra après le premier round.
                </p>
              ) : (
                <UTimeline values={uHistory} />
              )}
            </Panel>
          </div>

          <div className="space-y-4 lg:sticky lg:top-20">
            {account && (
              <Panel>
                <PanelTitle
                  kicker="Portefeuille"
                  title={account.name}
                  hint="Crédits fictifs. P&L = solde − solde initial (+ gains des marchés résolus)."
                />
                <div className="mb-2 flex items-baseline justify-between">
                  <span className="text-xs text-fg-muted">Solde</span>
                  <span className="font-mono text-lg font-semibold tabular-nums">
                    {fmt(account.balance)}
                  </span>
                </div>
                <div className="flex items-baseline justify-between">
                  <span className="text-xs text-fg-muted">P&L</span>
                  <span
                    className={`font-mono text-sm font-semibold tabular-nums ${account.pnl >= 0 ? "text-good" : "text-bad"}`}
                  >
                    {account.pnl >= 0 ? "+" : ""}
                    {fmt(account.pnl)}
                  </span>
                </div>
                {account.positions.length > 0 && (
                  <ul className="mt-3 space-y-1 border-t border-edge pt-3 text-xs text-fg-muted">
                    {account.positions.map((p) => (
                      <li key={p.outcome_id} className="flex justify-between">
                        <span>{p.label.toUpperCase().includes("YES") ? "YES — utopie" : "NO — dystopie"}</span>
                        <span className="font-mono tabular-nums">{fmt(p.shares)} parts</span>
                      </li>
                    ))}
                  </ul>
                )}
              </Panel>
            )}

            <Panel>
              <PanelTitle
                kicker="Classement"
                title="Leaderboard"
                hint="P&L en crédits fictifs ; Brier = calibration des probabilités (plus bas = mieux)."
              />
              {board.length === 0 ? (
                <p className="text-sm text-fg-faint">Personne n&apos;a encore parié.</p>
              ) : (
                <ul className="divide-y divide-edge text-sm">
                  {board.map((entry, i) => (
                    <li key={entry.account_id} className="flex items-center gap-3 py-2">
                      <span className="w-5 font-mono text-xs text-fg-faint">{i + 1}</span>
                      <span className="flex-1 truncate">{entry.name}</span>
                      {entry.kind !== "human" && <Pill tone="neutral">bot</Pill>}
                      <span
                        className={`font-mono text-xs tabular-nums ${entry.pnl >= 0 ? "text-good" : "text-bad"}`}
                      >
                        {entry.pnl >= 0 ? "+" : ""}
                        {fmt(entry.pnl)}
                      </span>
                      {entry.brier != null && (
                        <span
                          className="font-mono text-[10px] tabular-nums text-fg-faint"
                          title="Score de Brier"
                        >
                          B {fmt(entry.brier)}
                        </span>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </Panel>
          </div>
        </div>
      )}
    </div>
  );
}
