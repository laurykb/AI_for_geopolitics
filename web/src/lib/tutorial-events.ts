export const TUTORIAL_EVENT = "wosi:tutorial-milestone";

export type TutorialMilestone =
  | "round-started"
  | "round-done"
  | "next-round-started"
  | "player-spoke"
  | "motion-filed"
  | "motion-vote-ready"
  | "vote-submitted"
  | "bet-confirmed";

export type TutorialMilestoneDetail = {
  milestone: TutorialMilestone;
  gameId?: string;
  roundNo?: number;
};

export function emitTutorialMilestone(
  detail: TutorialMilestoneDetail,
  target: Pick<EventTarget, "dispatchEvent"> = window,
): void {
  target.dispatchEvent(new CustomEvent<TutorialMilestoneDetail>(TUTORIAL_EVENT, { detail }));
}

export function tutorialMilestoneFromEvent(event: Event): TutorialMilestoneDetail | null {
  if (!(event instanceof CustomEvent)) return null;
  const detail = event.detail as Partial<TutorialMilestoneDetail> | undefined;
  return detail?.milestone ? (detail as TutorialMilestoneDetail) : null;
}
