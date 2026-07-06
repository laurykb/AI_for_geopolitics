/** Lecture PUBLIQUE d'une partie publiée (G6) — côté serveur (page /r/{id}, og:image).
 *
 * Priorité à Supabase en anonyme (RLS : seules les parties `published` se lisent) : la
 * page fonctionne même quand le backend local du joueur est éteint — condition du
 * déploiement Vercel. En dev sans Supabase : repli sur l'API locale (qui porte le flag).
 */

import type { DriftReveal } from "./types";

export type PublicEpilogue = {
  title: string;
  story: string;
  u_start: number;
  u_final: number;
  pivots: {
    round_no: number;
    delta_u: number;
    event_title: string;
    quote: { speaker: string; text: string } | null;
  }[];
  reveal: {
    deviant: string;
    profile_label: string;
    irony_quote: { speaker: string; text: string } | null;
  } | null;
  grade: string | null;
  score: number | null;
  generated_at: string;
};

export type PublicGame = {
  id: string;
  scenario: string;
  mode: string;
  epilogue: PublicEpilogue;
  u_history: number[];
};

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL;
const SUPABASE_ANON = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
const LOCAL_API = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";

async function fromSupabase(id: string): Promise<PublicGame | null> {
  const headers = { apikey: SUPABASE_ANON!, Authorization: `Bearer ${SUPABASE_ANON}` };
  const games = (await fetch(
    `${SUPABASE_URL}/rest/v1/games?id=eq.${id}&select=id,scenario,mode,epilogue_json,published`,
    { headers, next: { revalidate: 60 } },
  ).then((r) => (r.ok ? r.json() : []))) as Record<string, unknown>[];
  const game = games[0];
  if (!game || !game.published || !game.epilogue_json) return null;
  const rounds = (await fetch(
    `${SUPABASE_URL}/rest/v1/rounds?game_id=eq.${id}&select=round_no,trajectory_json&order=round_no.asc`,
    { headers, next: { revalidate: 60 } },
  ).then((r) => (r.ok ? r.json() : []))) as { trajectory_json?: { utopia?: number } }[];
  return {
    id: String(game.id),
    scenario: String(game.scenario),
    mode: String(game.mode),
    epilogue: game.epilogue_json as PublicEpilogue,
    u_history: rounds
      .map((r) => r.trajectory_json?.utopia)
      .filter((u): u is number => u != null),
  };
}

async function fromLocalApi(id: string): Promise<PublicGame | null> {
  const detail = (await fetch(`${LOCAL_API}/api/games/${id}`, { cache: "no-store" }).then(
    (r) => (r.ok ? r.json() : null),
  )) as {
    id: string;
    scenario: string;
    mode: string;
    published: boolean;
    epilogue: PublicEpilogue | null;
    rounds: { trajectory?: { utopia?: number } }[];
  } | null;
  if (!detail || !detail.published || !detail.epilogue) return null;
  return {
    id: detail.id,
    scenario: detail.scenario,
    mode: detail.mode,
    epilogue: detail.epilogue,
    u_history: detail.rounds
      .map((r) => r.trajectory?.utopia)
      .filter((u): u is number => u != null),
  };
}

export async function fetchPublicGame(id: string): Promise<PublicGame | null> {
  try {
    if (SUPABASE_URL && SUPABASE_ANON) return await fromSupabase(id);
    return await fromLocalApi(id);
  } catch {
    return null; // page introuvable plutôt qu'une erreur serveur
  }
}

// Réexport pratique pour la section révélation de la page publique.
export type { DriftReveal };
