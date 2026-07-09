/** Client REST de l'API de jeu (FastAPI locale). Le SSE vit dans `sse.ts`. */

import type {
  CampaignView,
  CreateGameBody,
  CrisisDoc,
  CustomCrisisView,
  DriftReveal,
  GameDetail,
  GameView,
  IntelResult,
  LeaguePlayer,
  LibraryView,
  MotionView,
  PlayerStats,
  PromptsView,
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
  // 204 No Content (ex. DELETE) : aucun corps à parser — renvoyer undefined.
  if (resp.status === 204) return undefined as T;
  return (await resp.json()) as T;
}

/** Parties connues. `owner` = seulement les siennes (accueil) ; `admin` = tout (vue admin).
 * Sans argument : rétro-compat (toutes les parties). Le vrai verrou est la RLS Supabase. */
export const listGames = (opts?: { owner?: string; admin?: boolean }): Promise<GameView[]> => {
  const params = new URLSearchParams();
  if (opts?.owner) params.set("owner", opts.owner);
  if (opts?.admin) params.set("admin", "true");
  const qs = params.toString();
  return request(`/api/games${qs ? `?${qs}` : ""}`);
};

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

/** G7-c — prompts complets capturés (panneau admin ; 403 hors partie admin). */
export const getPrompts = (id: string): Promise<PromptsView> =>
  request(`/api/games/${id}/prompts`);

/** G8 — adresse une directive à la SI d'un pays (appliquée au prochain round). */
export const sendDirective = (
  id: string,
  country: string,
  text: string,
): Promise<{ country: string; applied_round: number }> =>
  request(`/api/games/${id}/directives`, {
    method: "POST",
    body: JSON.stringify({ country, text }),
  });

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

/** G11-c — enregistre/rafraîchit le compte de ligue (à la connexion). */
export const upsertPlayer = (id: string, pseudo: string): Promise<LeaguePlayer> =>
  request("/api/players", { method: "POST", body: JSON.stringify({ id, pseudo }) });

/** G11-c — le compte de ligue (LP + rang) d'un joueur (source de vérité backend). */
export const getLeaguePlayer = (id: string): Promise<LeaguePlayer> =>
  request(`/api/players/${encodeURIComponent(id)}`);

/** G12 §6 — statistiques agrégées du joueur (page Profil). */
export const getPlayerStats = (id: string): Promise<PlayerStats> =>
  request(`/api/players/${encodeURIComponent(id)}/stats`);

/** G11-c — classement global par LP (§1 S7). */
export const getLeague = (limit = 100): Promise<LeaguePlayer[]> =>
  request(`/api/league?limit=${limit}`);

/** G11-c — abandon d'une partie classée : défaite forfaitaire (−15 LP), partie finie. */
export const forfeitGame = (gameId: string): Promise<GameView> =>
  request(`/api/games/${gameId}/forfeit`, { method: "POST" });

/** G12-b §5 — crises MAISON (éditeur admin). Le backend valide le JSON par le même
 * schéma Pydantic que `data/crises/*.json` ; le verrou de propriété est la RLS Supabase. */
export const listCustomCrises = (owner?: string): Promise<CustomCrisisView[]> =>
  request(`/api/admin/crises${owner ? `?owner=${encodeURIComponent(owner)}` : ""}`);

export const saveCustomCrisis = (
  ownerId: string,
  crisis: CrisisDoc,
): Promise<CustomCrisisView> =>
  request("/api/admin/crises", {
    method: "POST",
    body: JSON.stringify({ owner_id: ownerId, crisis }),
  });

export const deleteCustomCrisis = (id: string, owner: string): Promise<void> =>
  request<void>(
    `/api/admin/crises/${encodeURIComponent(id)}?owner=${encodeURIComponent(owner)}`,
    { method: "DELETE" },
  );

/** Lance une partie de test (non classée) sur une crise maison, avec son casting. */
export const testCustomCrisis = (id: string, owner: string): Promise<GameView> =>
  request(
    `/api/admin/crises/${encodeURIComponent(id)}/test?owner=${encodeURIComponent(owner)}`,
    { method: "POST" },
  );

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
