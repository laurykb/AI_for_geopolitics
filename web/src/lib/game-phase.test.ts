import { describe, expect, it } from "vitest";

import { canStartRound, deriveGamePhase } from "./game-phase";

const phase = (
  overrides: Partial<Parameters<typeof deriveGamePhase>[0]> = {},
) =>
  deriveGamePhase({
    detailLoaded: true,
    gameStatus: "running",
    live: true,
    hasResult: false,
    playedRounds: 0,
    horizon: 8,
    liveStatus: "idle",
    inFlight: false,
    ...overrides,
  });

describe("etat produit du theatre", () => {
  it("distingue le premier lancement de la continuation", () => {
    expect(phase()).toBe("ready");
    expect(phase({ playedRounds: 1 })).toBe("round_complete");
    expect(canStartRound(phase())).toBe(true);
    expect(canStartRound(phase({ playedRounds: 1 }))).toBe(true);
  });

  it("donne la priorite aux decisions humaines", () => {
    expect(phase({ liveStatus: "awaiting_human", inFlight: true })).toBe("awaiting_player");
    expect(phase({ liveStatus: "awaiting_vote", inFlight: true })).toBe("awaiting_vote");
    expect(phase({ awaitingHumanSnapshot: true })).toBe("awaiting_player");
  });

  it("ne reactive pas le bouton pendant la fermeture du flux", () => {
    expect(phase({ playedRounds: 1, liveStatus: "done", inFlight: true })).toBe("resolving");
    expect(canStartRound(phase({ playedRounds: 1, liveStatus: "done", inFlight: true }))).toBe(
      false,
    );
  });

  it("reprend l'état explicite du serveur après un rechargement", () => {
    expect(phase({ serverPhase: "round_complete" })).toBe("round_complete");
    expect(phase({ serverPhase: "round_running" })).toBe("round_running");
  });

  it("represente les fins et les pannes explicitement", () => {
    expect(phase({ gameStatus: "finished", hasResult: true })).toBe("game_complete");
    expect(phase({ live: false })).toBe("replay_only");
    expect(phase({ liveStatus: "interrupted" })).toBe("disconnected");
    expect(phase({ liveStatus: "error" })).toBe("error");
  });

  it("réactive Continuer après resynchronisation d'une coupure", () => {
    expect(
      phase({
        playedRounds: 2,
        liveStatus: "interrupted",
        serverPhase: "round_complete",
      }),
    ).toBe("round_complete");
    expect(phase({ liveStatus: "error", serverPhase: "ready" })).toBe("ready");
  });

  it("reste déconnecté tant que le serveur pense que le round tourne", () => {
    expect(
      phase({ liveStatus: "interrupted", serverPhase: "round_running" }),
    ).toBe("disconnected");
  });
});
