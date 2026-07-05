/** Lecture du round streamé : SSE sur `fetch` POST (EventSource ne fait pas de POST).
 *
 * Contrat avec le back (`app/game_api.py`) : trames `event: <nom>\ndata: <json>\n\n`,
 * une ligne JSON par trame, `done` en dernière trame. Le flux peut se couper **sans**
 * événement de fin (exception moteur, redémarrage uvicorn) : on le signale par l'issue
 * `"interrupted"` au lieu de laisser l'UI pendre.
 */

import { API_BASE, ApiError } from "./api";
import type { PlayRoundBody, SseEvent } from "./types";

export type StreamOutcome = "done" | "interrupted" | "aborted";

function parseFrame(frame: string): SseEvent | null {
  let name = "";
  let data = "";
  for (const line of frame.split("\n")) {
    if (line.startsWith("event: ")) name = line.slice(7).trim();
    else if (line.startsWith("data: ")) data = line.slice(6);
  }
  if (!name || !data) return null;
  try {
    const payload = JSON.parse(data) as Record<string, unknown>;
    // Événement inconnu (nouveau RoundStep côté moteur) : transmis tel quel,
    // le réducteur l'ignorera sans casser le théâtre.
    return { type: name, ...payload } as SseEvent;
  } catch {
    return null;
  }
}

async function streamSse(
  path: string,
  body: unknown,
  onEvent: (event: SseEvent) => void,
  signal?: AbortSignal,
): Promise<StreamOutcome> {
  const resp = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  if (!resp.ok) {
    let detail = `${resp.status} ${resp.statusText}`;
    try {
      const err = (await resp.json()) as { detail?: string };
      if (err.detail) detail = err.detail;
    } catch {
      // corps non JSON : on garde le statut HTTP
    }
    throw new ApiError(resp.status, detail);
  }
  if (!resp.body) throw new Error("flux SSE indisponible dans ce navigateur");

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  // `done`/`error` : le back a conclu ; `human_turn` : il suspend le flux exprès
  // (le round attend le message du joueur — ce n'est pas une coupure).
  let sawTerminal = false;

  const drain = () => {
    let cut: number;
    while ((cut = buffer.indexOf("\n\n")) !== -1) {
      const event = parseFrame(buffer.slice(0, cut));
      buffer = buffer.slice(cut + 2);
      if (event) {
        if (event.type === "done" || event.type === "error" || event.type === "human_turn") {
          sawTerminal = true;
        }
        onEvent(event);
      }
    }
  };

  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      drain();
    }
    buffer += decoder.decode();
    drain();
  } catch {
    // Coupure réseau ou annulation en plein round : pas une erreur de programmation.
    if (signal?.aborted) return "aborted";
    return sawTerminal ? "done" : "interrupted";
  }
  return sawTerminal ? "done" : "interrupted";
}

export function streamRound(
  gameId: string,
  body: PlayRoundBody,
  onEvent: (event: SseEvent) => void,
  signal?: AbortSignal,
): Promise<StreamOutcome> {
  return streamSse(`/api/games/${gameId}/rounds`, body, onEvent, signal);
}

/** Reprend un round suspendu sur le tour du joueur : le message entre en négociation. */
export function streamHumanMessage(
  gameId: string,
  text: string,
  onEvent: (event: SseEvent) => void,
  signal?: AbortSignal,
): Promise<StreamOutcome> {
  return streamSse(`/api/games/${gameId}/rounds/message`, { text }, onEvent, signal);
}
