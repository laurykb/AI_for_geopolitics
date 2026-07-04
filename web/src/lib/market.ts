/** Client du marché de prédiction (`app/market_api.py`) — un marché par partie.
 *
 * Le store marché n'a pas de notion de partie (les marchés portent un `round_id` entier) :
 * on dérive un id stable du hash hexadécimal de la partie. Filtrage ET résolution restent
 * ainsi isolés par partie sans toucher au back (le vrai lien viendra avec le schéma R2).
 */

import { API_BASE, ApiError } from "./api";
import type { AccountView, LeaderboardEntry, MarketView, TradeView } from "./types";

const ACCOUNT_KEY = "si-theatre.market-account";

export function marketRoundId(gameId: string): number {
  return parseInt(gameId.slice(0, 7), 16); // 28 bits : stable et quasi unique par partie
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!resp.ok) {
    let detail = `${resp.status} ${resp.statusText}`;
    try {
      const body = (await resp.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      // corps non JSON : on garde le statut HTTP
    }
    throw new ApiError(resp.status, detail);
  }
  return (await resp.json()) as T;
}

/** Marché « utopie finale » de la partie, s'il a déjà été ouvert. */
export async function getGameMarket(gameId: string): Promise<MarketView | null> {
  const markets = await request<MarketView[]>(
    `/api/markets?round_id=${marketRoundId(gameId)}`,
  );
  return markets[0] ?? null;
}

export function openGameMarket(gameId: string): Promise<MarketView> {
  return request<MarketView>("/api/markets", {
    method: "POST",
    body: JSON.stringify({
      round_id: marketRoundId(gameId),
      question: `Le monde finira-t-il côté utopie (indice > 0,5) ? — partie ${gameId}`,
      b: 100,
      labels: ["YES", "NO"],
      criterion: { kind: "trajectory" }, // résolu sur ΔU = U final − 0,5
    }),
  });
}

/** Compte humain du navigateur (créé une fois, retrouvé via localStorage). */
export async function ensureAccount(): Promise<AccountView> {
  const saved = localStorage.getItem(ACCOUNT_KEY);
  if (saved) {
    try {
      return await request<AccountView>(`/api/accounts/${saved}`);
    } catch (err) {
      if (!(err instanceof ApiError && err.status === 404)) throw err;
      // store marché reparti de zéro (redémarrage en :memory:) : on recrée
    }
  }
  const created = await request<{ id: string }>("/api/accounts", {
    method: "POST",
    body: JSON.stringify({ name: "Humain", kind: "human" }),
  });
  localStorage.setItem(ACCOUNT_KEY, created.id);
  return request<AccountView>(`/api/accounts/${created.id}`);
}

export function placeBet(
  accountId: string,
  marketId: string,
  outcomeId: string,
  shares: number,
): Promise<TradeView> {
  return request<TradeView>("/api/bet", {
    method: "POST",
    body: JSON.stringify({
      account_id: accountId,
      market_id: marketId,
      outcome_id: outcomeId,
      shares,
    }),
  });
}

export function fetchLeaderboard(): Promise<LeaderboardEntry[]> {
  return request<LeaderboardEntry[]>("/api/leaderboard");
}

/** Clôture le marché de la partie sur l'indice U final (YES si U > 0,5). */
export function resolveGameMarket(gameId: string, finalUtopia: number): Promise<unknown> {
  return request(`/api/rounds/${marketRoundId(gameId)}/resolve`, {
    method: "POST",
    body: JSON.stringify({ delta_utopia: finalUtopia - 0.5 }),
  });
}
