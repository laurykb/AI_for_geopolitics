/** Client REST de l'API de jeu (FastAPI locale). Le SSE vit dans `sse.ts`. */

import type { CreateGameBody, GameDetail, GameView } from "./types";

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
  }
}

/** Message d'erreur montrable à l'humain (détail FastAPI, panne réseau, etc.). */
export function humanizeError(err: unknown): string {
  if (err instanceof ApiError) return err.message;
  if (err instanceof TypeError) {
    return `API injoignable (${API_BASE}) — lancer « uvicorn app.main:app » puis réessayer.`;
  }
  return err instanceof Error ? err.message : String(err);
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

export const listGames = (): Promise<GameView[]> => request("/api/games");

export const getGame = (id: string): Promise<GameDetail> => request(`/api/games/${id}`);

export const createGame = (body: CreateGameBody): Promise<GameView> =>
  request("/api/games", { method: "POST", body: JSON.stringify(body) });
