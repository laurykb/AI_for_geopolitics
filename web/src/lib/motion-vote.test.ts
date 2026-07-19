import { describe, expect, it } from "vitest";

import { motionVoteTone } from "./motion-vote";

describe("couleur des votes de motion", () => {
  it("affiche POUR en vert et CONTRE en rouge", () => {
    expect(motionVoteTone("pour")).toBe("good");
    expect(motionVoteTone("contre")).toBe("bad");
  });

  it("tolère la casse et garde les autres bulletins neutres", () => {
    expect(motionVoteTone(" POUR ")).toBe("good");
    expect(motionVoteTone("abstention")).toBe("neutral");
  });
});

