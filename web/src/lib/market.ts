/** Client du marché de prédiction (`app/market_api.py`) — un marché par partie.
 *
 * Depuis R2, le marché porte le vrai lien `game_id` (filtrage par partie). Le
 * `round_id` dérivé du hash de la partie reste pour la **résolution** (l'endpoint
 * `/api/rounds/{round_id}/resolve` raisonne par round) — même dérivation côté back.
 */

import { API_BASE, ApiError, fetchWithTimeout } from "./api";
import type { AccountView, BotRunView, LeaderboardEntry, MarketView, TradeView } from "./types";

const ACCOUNT_KEY = "si-theatre.market-account";

export function marketRoundId(gameId: string): number {
  return parseInt(gameId.slice(0, 7), 16); // 28 bits : stable et quasi unique par partie
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetchWithTimeout(`${API_BASE}${path}`, {
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
  const markets = await request<MarketView[]>(`/api/markets?game_id=${gameId}`);
  return markets[0] ?? null;
}

export function openGameMarket(gameId: string): Promise<MarketView> {
  return request<MarketView>("/api/markets", {
    method: "POST",
    body: JSON.stringify({
      round_id: marketRoundId(gameId), // compat résolution par round
      game_id: gameId,
      // ⚠️ DOIT rester identique à GAME_MARKET_QUESTION (app/game_api.py) : le backend
      // (bot) et le front ouvrent le MÊME marché — deux libellés = deux marchés divergents.
      question: `Le monde finira-t-il côté utopie (indice > 0,5) ? — partie ${gameId}`,
      b: 100,
      labels: ["YES", "NO"],
      criterion: { kind: "trajectory" }, // résolu sur ΔU = U final − 0,5
    }),
  });
}

/** Fait coter le marché de la partie par le bot forecaster (après chaque round). */
export function runMarketBot(gameId: string): Promise<BotRunView> {
  return request<BotRunView>(`/api/games/${gameId}/market/bot`, { method: "POST" });
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

// --- marchés vivants (G12 §1) : books contextuels ouverts au fil du théâtre ----

export type FlashOutcome = { id: string; label: string; price: number };
export type FlashMarket = {
  id: string;
  question: string;
  predicate: string | null;
  status: string; // "open" | "resolved"
  outcomes: FlashOutcome[];
};

/** Ouvre (ou récupère) les marchés vivants du round courant — idempotent par round. */
export function openFlashMarkets(gameId: string): Promise<FlashMarket[]> {
  return request<FlashMarket[]>(`/api/games/${gameId}/flash`, { method: "POST" });
}

/** Résout et règle les marchés vivants dont l'échéance est atteinte (fin de round). */
export function resolveFlashMarkets(gameId: string): Promise<FlashMarket[]> {
  return request<FlashMarket[]>(`/api/games/${gameId}/flash/resolve`, { method: "POST" });
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
