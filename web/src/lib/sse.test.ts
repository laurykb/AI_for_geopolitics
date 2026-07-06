/** Tests du parseur SSE (`streamRound`) : trames partielles, `error`, coupure sans
 * `done`, événement inconnu, `human_turn`, annulation, erreur HTTP. Env node — le
 * fetch global est remplacé par des réponses fabriquées (aucun réseau). */

import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "./api";
import { streamRound } from "./sse";
import type { SseEvent } from "./types";

function streamOf(chunks: string[], { fail = false } = {}): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  let next = 0;
  return new ReadableStream({
    // pull (et non start) : une erreur dans start() jetterait aussi les chunks en file —
    // ici les chunks sont livrés, PUIS la lecture suivante échoue (vraie coupure réseau).
    pull(controller) {
      if (next < chunks.length) controller.enqueue(encoder.encode(chunks[next++]));
      else if (fail) controller.error(new Error("coupure réseau"));
      else controller.close();
    },
  });
}

function okResponse(chunks: string[], opts?: { fail?: boolean }): Response {
  return {
    ok: true,
    status: 200,
    statusText: "OK",
    body: streamOf(chunks, opts),
    json: async () => ({}),
  } as unknown as Response;
}

function errorResponse(status: number, detail?: string): Response {
  return {
    ok: false,
    status,
    statusText: "Conflict",
    body: null,
    json: async () => {
      if (detail === undefined) throw new Error("pas de corps");
      return { detail };
    },
  } as unknown as Response;
}

function mockFetch(resp: Response) {
  vi.stubGlobal("fetch", vi.fn(async () => resp));
}

async function collect(chunks: string[], opts?: { fail?: boolean }) {
  mockFetch(okResponse(chunks, opts));
  const events: SseEvent[] = [];
  const outcome = await streamRound("g1", {}, (e) => events.push(e));
  return { events, outcome };
}

const TOKEN = 'event: token\ndata: {"country":"usa","token":"bonjour"}\n\n';
const DONE = 'event: done\ndata: {"round_no":1}\n\n';

afterEach(() => vi.unstubAllGlobals());

describe("streamRound", () => {
  it("parse un flux complet et conclut sur done", async () => {
    const { events, outcome } = await collect([TOKEN + DONE]);
    expect(outcome).toBe("done");
    expect(events).toEqual([
      { type: "token", country: "usa", token: "bonjour" },
      { type: "done", round_no: 1 },
    ]);
  });

  it("recolle les trames coupées en plein milieu (chunks partiels)", async () => {
    const whole = TOKEN + DONE;
    const cut = TOKEN.indexOf("data:") + 9; // au milieu du JSON du token
    const { events, outcome } = await collect([whole.slice(0, cut), whole.slice(cut)]);
    expect(outcome).toBe("done");
    expect(events.map((e) => e.type)).toEqual(["token", "done"]);
  });

  it("une trame error est terminale (le back a conclu proprement)", async () => {
    const { events, outcome } = await collect([
      TOKEN + 'event: error\ndata: {"detail":"le moteur a cassé"}\n\n',
    ]);
    expect(outcome).toBe("done");
    expect(events.at(-1)).toEqual({ type: "error", detail: "le moteur a cassé" });
  });

  it("un flux coupé sans done est signalé interrupted", async () => {
    const { outcome } = await collect([TOKEN]); // le serveur ferme sans conclure
    expect(outcome).toBe("interrupted");
  });

  it("une coupure réseau en plein flux est aussi interrupted", async () => {
    const { events, outcome } = await collect([TOKEN], { fail: true });
    expect(outcome).toBe("interrupted");
    expect(events.map((e) => e.type)).toEqual(["token"]); // le déjà-reçu est conservé
  });

  it("un événement inconnu est transmis tel quel (futur RoundStep)", async () => {
    const { events } = await collect([
      'event: hologramme\ndata: {"x":1}\n\n' + DONE,
    ]);
    expect(events[0]).toEqual({ type: "hologramme", x: 1 });
  });

  it("une trame illisible (JSON invalide) est ignorée sans casser le flux", async () => {
    const { events, outcome } = await collect([
      "event: token\ndata: {pas du json}\n\n" + DONE,
    ]);
    expect(outcome).toBe("done");
    expect(events.map((e) => e.type)).toEqual(["done"]);
  });

  it("human_turn n'est plus terminal (G2) : le flux devait continuer", async () => {
    const { events, outcome } = await collect([
      'event: human_turn\ndata: {"country":"france","pass_no":1,"deadline_ts":123}\n\n',
    ]);
    // Le serveur garde le flux ouvert pendant le tour : une fin ici est une coupure.
    expect(outcome).toBe("interrupted");
    expect(events[0]).toMatchObject({ type: "human_turn", deadline_ts: 123 });
  });

  it("les keep-alive `: ping` du tour humain sont ignorés", async () => {
    const { events, outcome } = await collect([": ping\n\n" + TOKEN + ": ping\n\n" + DONE]);
    expect(outcome).toBe("done");
    expect(events.map((e) => e.type)).toEqual(["token", "done"]);
  });

  it("une annulation (abort) est distinguée de la coupure", async () => {
    mockFetch(okResponse([TOKEN], { fail: true }));
    const controller = new AbortController();
    controller.abort();
    const outcome = await streamRound("g1", {}, () => {}, controller.signal);
    expect(outcome).toBe("aborted");
  });

  it("une erreur HTTP lève ApiError avec le détail FastAPI", async () => {
    mockFetch(errorResponse(409, "un round est déjà en cours sur cette partie"));
    await expect(streamRound("g1", {}, () => {})).rejects.toThrow(
      new ApiError(409, "un round est déjà en cours sur cette partie"),
    );
  });

  it("une erreur HTTP sans corps JSON garde le statut", async () => {
    mockFetch(errorResponse(502));
    await expect(streamRound("g1", {}, () => {})).rejects.toThrow("502 Conflict");
  });
});
