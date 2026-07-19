import { describe, expect, it } from "vitest";

import { roundButtonLabel } from "./round-controls";

const label = (overrides: Partial<Parameters<typeof roundButtonLabel>[0]> = {}) =>
  roundButtonLabel({
    spectator: false,
    accelerationActive: false,
    active: false,
    motionPending: false,
    playedRounds: 0,
    ...overrides,
  });

describe("libellé du bouton de round", () => {
  it("propose de continuer après le premier round, y compris après resynchronisation", () => {
    expect(label({ playedRounds: 1 })).toBe("Continuer la partie");
    expect(label({ playedRounds: 8 })).toBe("Continuer la partie");
  });

  it("garde les états prioritaires explicites", () => {
    expect(label()).toBe("Jouer un round");
    expect(label({ playedRounds: 1, active: true })).toBe("Négociation en cours…");
    expect(label({ playedRounds: 1, motionPending: true })).toBe("Débattre la motion");
  });
});

