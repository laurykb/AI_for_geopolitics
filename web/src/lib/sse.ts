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

export async function streamRound(
  gameId: string,
  body: PlayRoundBody,
  onEvent: (event: SseEvent) => void,
  signal?: AbortSignal,
): Promise<StreamOutcome> {
  const resp = await fetch(`${API_BASE}/api/games/${gameId}/rounds`, {
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
  let sawDone = false;

  const drain = () => {
    let cut: number;
    while ((cut = buffer.indexOf("\n\n")) !== -1) {
      const event = parseFrame(buffer.slice(0, cut));
      buffer = buffer.slice(cut + 2);
      if (event) {
        if (event.type === "done") sawDone = true;
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
    return sawDone ? "done" : "interrupted";
  }
  return sawDone ? "done" : "interrupted";
}
