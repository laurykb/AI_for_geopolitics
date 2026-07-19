import { describe, expect, it } from "vitest";

import {
  emitTutorialMilestone,
  TUTORIAL_EVENT,
  tutorialMilestoneFromEvent,
} from "./tutorial-events";

describe("événements métier du tutoriel", () => {
  it("transporte un jalon sans dépendre du DOM de la scène", () => {
    const target = new EventTarget();
    let received: ReturnType<typeof tutorialMilestoneFromEvent> = null;
    target.addEventListener(TUTORIAL_EVENT, (event) => {
      received = tutorialMilestoneFromEvent(event);
    });

    emitTutorialMilestone({ milestone: "round-done", gameId: "g1", roundNo: 2 }, target);

    expect(received).toEqual({ milestone: "round-done", gameId: "g1", roundNo: 2 });
  });
});
