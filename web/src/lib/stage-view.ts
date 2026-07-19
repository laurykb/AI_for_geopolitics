/** Modèle de vue de la scène (G1) — dérivation PURE partagée par le théâtre.
 *
 * Le théâtre affiche soit le DIRECT (`round` streamé), soit un round PASSÉ que le
 * spectateur relit (`viewed`, scrub de la timeline). Les deux cas produisent les
 * mêmes valeurs d'affichage (teinte U par pays, orateur, perceptions brouillées,
 * bandeau du bas…). Cette fonction centralise le « live vs relecture » pour que la
 * page n'ait plus à le trancher ligne à ligne — et pour le rendre testable.
 * Aucune dépendance à React : entrées → sorties, rien d'autre. */

import { speakerMeta } from "./countries";
import { isMisled } from "./fog";
import { localU } from "./stage";
import type {
  AttributeDelta,
  GameDetail,
  LadderView,
  Perception,
  RoundView,
} from "./types";
import type { LiveRound } from "@/hooks/useRoundStream";
import type { StageSelection } from "@/components/stage-band";

export type StageViewInput = {
  round: LiveRound;
  detail: GameDetail | null;
  /** Round passé en relecture (scrub), ou `undefined` en direct. */
  viewed: RoundView | undefined;
  summit: string[];
  streaming: boolean;
  awaitingHuman: boolean;
  playedRounds: number;
  persistedU: number[];
  showLive: boolean;
  selected: StageSelection;
};

export function deriveStageView(input: StageViewInput) {
  const {
    round,
    detail,
    viewed,
    summit,
    streaming,
    awaitingHuman,
    playedRounds,
    persistedU,
    showLive,
    selected,
  } = input;

  const stageU = viewed
    ? (viewed.trajectory?.utopia ?? 0.5)
    : (round.trajectory?.utopia ?? persistedU.at(-1) ?? 0.5);
  const stageDeltas = ((viewed ? viewed.deltas : round.verdict?.deltas) ?? []) as AttributeDelta[];
  const uByCountry = Object.fromEntries(summit.map((c) => [c, localU(stageU, c, stageDeltas)]));
  const stageSpeaking = viewed
    ? null
    : streaming
      ? ([...round.turns].reverse().find((t) => !t.done)?.country ?? null)
      : awaitingHuman
        ? (detail?.play_as ?? null)
        : null;
  const stagePerceptions = viewed
    ? ((viewed.judge?.perceptions ?? undefined) as Record<string, Perception> | undefined)
    : round.perceptions;
  const stageEventActors = viewed
    ? (viewed.event as { actors?: string[] } | undefined)?.actors
    : round.event?.actors;
  const stageMisled = Object.fromEntries(
    Object.entries(stagePerceptions ?? {})
      .filter(([, p]) => isMisled(p, stageEventActors))
      .map(([c, p]) => [c, p.narrative ?? p.suspected_actor ?? "perception brouillée"]),
  );
  const stageSuspended = viewed
    ? ((viewed.judge?.suspended ?? []) as string[])
    : (round.suspendedNow ?? []);
  const stageEventTitle = viewed
    ? (viewed.event as { title?: string } | undefined)?.title
    : round.event?.title;
  const breatheKey = round.status === "done" ? (round.roundNo ?? 0) : 0;

  // a11y — annonce du direct pour les lecteurs d'écran (région sr-only, pas le stream
  // token par token qui serait illisible : on annonce les jalons).
  const lastDoneTurn = [...round.turns].filter((t) => t.done).at(-1);
  const liveAnnouncement =
    round.status === "done"
      ? `Round ${round.roundNo ?? playedRounds} terminé.`
      : round.verdict
        ? "Le juge a rendu son verdict."
        : lastDoneTurn
          ? `${speakerMeta(lastDoneTurn.country).label} a parlé.`
          : round.event
            ? `Événement : ${round.event.title}.`
            : "";

  const bandLiveU =
    showLive && round.status !== "done" && round.trajectory ? round.trajectory.utopia : undefined;
  const bandRisk = (viewed ? viewed.risk : round.risk) ?? detail?.rounds.at(-1)?.risk;
  const bandLadder = viewed
    ? ((viewed.judge?.ladder ?? undefined) as LadderView | undefined)
    : round.ladder;
  const prevRungIndex = viewed ? (selected as number) - 1 : (detail?.rounds.length ?? 0) - 1;
  const prevRung =
    ((detail?.rounds[prevRungIndex]?.judge?.ladder ?? undefined) as LadderView | undefined)
      ?.reached ?? null;
  const treatiesUpdate =
    (viewed ? viewed.judge.treaties : round.treaties) ?? detail?.rounds.at(-1)?.judge.treaties;

  return {
    stageU,
    uByCountry,
    stageSpeaking,
    stageMisled,
    stageSuspended,
    stageEventTitle,
    breatheKey,
    liveAnnouncement,
    bandLiveU,
    bandRisk,
    bandLadder,
    prevRung,
    treatiesUpdate,
  };
}

export type StageView = ReturnType<typeof deriveStageView>;
