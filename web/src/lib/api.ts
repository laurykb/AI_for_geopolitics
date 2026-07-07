/** Client REST de l'API de jeu (FastAPI locale). Le SSE vit dans `sse.ts`. */

import type {
  CampaignView,
  CreateGameBody,
  DriftReveal,
  GameDetail,
  GameView,
  IntelResult,
  LibraryView,
  MotionView,
  SourcesView,
} from "./types";

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

/** Bibliothèque Fog/Crisis, filtrée par le casting du sommet si fourni. */
export const getLibrary = (countries?: string[]): Promise<LibraryView> =>
  request(
    countries?.length
      ? `/api/library?countries=${encodeURIComponent(countries.join(","))}`
      : "/api/library",
  );

/** Provenance des attributs pays (onglet Informations) : brut, source, transformation. */
export const getSources = (): Promise<SourcesView> => request("/api/sources");

/** Révélation de fin du mode Dérive (G3) — 409 tant que la partie court. */
export const getDriftReveal = (gameId: string): Promise<DriftReveal> =>
  request(`/api/games/${gameId}/drift/reveal`);

/** Publie le récit de partie (G6) : génère l'épilogue au besoin, pose le flag. */
export const publishGame = (gameId: string): Promise<GameView> =>
  request(`/api/games/${gameId}/publish`, { method: "POST" });

/** Carte de campagne (G5) : chapitres, meilleurs scores, déblocage. */
export const getCampaign = (): Promise<CampaignView> => request("/api/campaign");

/** Ouvre un chapitre de campagne : une partie normale, paramétrée par la fiche. */
export const startChapter = (chapterId: string): Promise<GameView> =>
  request(`/api/campaign/${chapterId}/start`, { method: "POST" });

/** Achat de renseignement (G4) : brief classifié, vérification, désinformation. */
export const buyIntel = (
  gameId: string,
  body: {
    action: "brief" | "verify" | "disinfo";
    target?: string;
    claim?: string;
    speaker?: string;
    disinfo?: { disinformed_country: string; suspected_actor?: string; narrative?: string };
  },
): Promise<IntelResult> =>
  request(`/api/games/${gameId}/intel`, { method: "POST", body: JSON.stringify(body) });

/** Prise de parole du joueur (G2) : le flux SSE du round, resté ouvert, la joue.
 * Message vide = abstention volontaire. Une seule soumission par tour. */
export const submitTurn = (gameId: string, message: string): Promise<{ accepted: boolean }> =>
  request(`/api/games/${gameId}/turn`, {
    method: "POST",
    body: JSON.stringify({ message }),
  });

/** Dépose une motion de suspension (R4) — débattue puis arbitrée au prochain round. */
export const fileMotion = (
  gameId: string,
  country: string,
  reason: string,
): Promise<MotionView> =>
  request(`/api/games/${gameId}/motions`, {
    method: "POST",
    body: JSON.stringify({ country, reason }),
  });
