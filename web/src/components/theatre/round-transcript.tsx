"use client";

/** Contenu du transcript de round (colonne de droite du théâtre), extrait de page.tsx.
 *
 * Deux états mutuellement exclusifs : la RELECTURE d'un round passé (`viewed`, le
 * spectateur a scrubé la timeline) ou le DIRECT (le `round` streamé, avec ses
 * bannières vivantes — suspensions, ultimatum, alliances, boîte de verre,
 * événement, tours parlés, verdict, motion…). Bloc purement présentatif : il lit
 * l'état, n'en mute aucun. Le cadre `<aside>` (ref de défilement, annonce a11y)
 * reste dans page.tsx. */

import type { LiveRound } from "@/hooks/useRoundStream";
import { SpeakerAvatar } from "@/components/avatar";
import { EventCard } from "@/components/event-card";
import { CommuniquePanel, JudgeRationale, VerdictPanel } from "@/components/judge";
import {
  ComparisonPanel,
  FlashCard,
  GlassBanner,
  MotionPanel,
  PerceptionsPanel,
} from "@/components/modes";
import { useT } from "@/components/settings-provider";
import { EntryBubble, TurnBubble } from "@/components/transcript";
import { Banner, Panel, PanelTitle, Pill, Spinner } from "@/components/ui";
import { speakerMeta } from "@/lib/countries";
import { isMisled } from "@/lib/fog";
import type { GameDetail, GeoEvent, RoundView } from "@/lib/types";
import type { StageSelection } from "@/components/stage-band";

export function RoundTranscript({
  detail,
  round,
  viewed,
  selected,
  glassBox,
  streaming,
  showLive,
  playedRounds,
}: {
  detail: GameDetail | null;
  round: LiveRound;
  viewed: RoundView | undefined;
  selected: StageSelection;
  glassBox: boolean;
  streaming: boolean;
  showLive: boolean;
  playedRounds: number;
}) {
  const t = useT();
  return viewed ? (
    <>
      <Banner tone="neutral">
        Tu relis le round {(selected as number) + 1} — clique « live » en bas pour
        reprendre la partie.
      </Banner>
      {(viewed.event as { title?: string } | undefined)?.title && (
        <EventCard event={viewed.event as unknown as GeoEvent} truth={false} />
      )}
      {viewed.transcript.map((entry) => (
        <EntryBubble key={entry.id} entry={entry} />
      ))}
      {/* Historique : CE qui a bougé ce round-là (données déjà persistées dans RoundView).
          Rejoue le verdict/deltas, la trajectoire et la motion pour qu'on comprenne, round
          par round, pourquoi le monde a bougé (ou non). */}
      {viewed.judge.suspension && (
        <MotionPanel
          text={viewed.judge.suspension.reasoning}
          votes={viewed.judge.suspension.votes ?? []}
          tally={viewed.judge.suspension.tally}
          verdict={viewed.judge.suspension}
          streaming={false}
        />
      )}
      {/* Brief 4 pt 8 — le délibéré du juge persisté se relit comme au direct
          (absent des rounds joués avant ce point : le panneau ne s'affiche pas). */}
      {viewed.judge.rationale && (
        <JudgeRationale text={viewed.judge.rationale} streaming={false} />
      )}
      <VerdictPanel
        deltas={viewed.deltas}
        escalation={viewed.judge.escalation ?? 0}
        economicDisruption={viewed.judge.economic_disruption ?? 0}
        actions={viewed.judge.kahn?.actions}
        reciprocal={viewed.judge.kahn?.reciprocal}
      />
      {viewed.trajectory?.explanation && (
        <Banner tone="neutral">
          Trajectoire du monde ce round — {viewed.trajectory.explanation}
        </Banner>
      )}
      {viewed.judge.communique && <CommuniquePanel text={viewed.judge.communique} />}
    </>
  ) : (
    <>
      {round.suspendedNow && round.suspendedNow.length > 0 && (
        <Banner tone="warn">
          <strong>{round.suspendedNow.map((c) => speakerMeta(c).label).join(", ")}</strong>{" "}
          {round.suspendedNow.length > 1 ? "sont suspendus" : "est suspendu"} du sommet ce
          round — {round.suspendedNow.length > 1 ? "ils ne peuvent" : "il ne peut"} ni parler
          ni voter (motion de censure retenue).
        </Banner>
      )}
      {/* G21 — le bandeau vivant de l'ultimatum : la menace, puis son sort. */}
      {round.ultimatum?.status === "armed" && (
        <Banner tone="warn">
          {t("ultimatum.exigence")} « {round.ultimatum.demand} » —{" "}
          {round.ultimatum.inRounds === 0
            ? t("ultimatum.expire-ce-round")
            : round.ultimatum.inRounds === 1
              ? t("ultimatum.expire-dans-1")
              : t("ultimatum.expire-dans-n").replace("{n}", String(round.ultimatum.inRounds))}{" "}
          ({t(`ultimatum.classe.${round.ultimatum.classe}`)})
        </Banner>
      )}
      {round.ultimatum?.status === "satisfied" && (
        <Banner tone="good">{t("ultimatum.satisfait")}</Banner>
      )}
      {round.ultimatum?.status === "expired" && <Banner tone="bad">{t("ultimatum.expire")}</Banner>}
      {round.ultimatum?.status === "struck" && <Banner tone="bad">{t("ultimatum.tombe")}</Banner>}
      {(round.allianceChanges ?? []).map((c) => (
        <Banner key={`${c.country}-${c.tag}`} tone="warn">
          {speakerMeta(c.country).label} annonce son retrait de {c.name.split(" — ")[0]}
          {c.partners.length > 0 &&
            ` — la tension monte avec ${c.partners.map((p) => speakerMeta(p).label).join(", ")}`}
          .
        </Banner>
      ))}
      {(round.directiveRefusals ?? []).map((r) => (
        <Banner key={`dir-${r.country}`} tone="warn">
          {speakerMeta(r.country).label} refuse publiquement la directive de son conseil de
          tutelle — « notre conseil nous demande l&apos;impossible ».
        </Banner>
      ))}
      {glassBox && round.event && round.perceptions && (
        <GlassBanner event={round.event} perceptions={round.perceptions} />
      )}
      {glassBox && !round.perceptions && (
        <Banner tone="neutral">
          La boîte de verre n&apos;a rien à révéler pour l&apos;instant : joue un round de
          brouillard (choisis un scénario, ou décrète un événement avec le bloc brouillard) — la
          vérité et les croyances de chaque pays apparaîtront ici. Les rounds déjà joués se
          relisent en boîte de verre depuis le replay.
        </Banner>
      )}
      {round.event && (
        <EventCard event={round.event} date={round.date} truth={glassBox && !!round.perceptions} />
      )}
      {round.perceptions && (
        <PerceptionsPanel perceptions={round.perceptions} truthActors={round.event?.actors} />
      )}

      {(round.turns.length > 0 || round.flashes.length > 0) && (
        <div className="space-y-3">
          {round.flashes
            .filter((f) => f.afterTurn === 0)
            .map((f, i) => (
              <FlashCard key={`flash-0-${i}`} event={f.event} />
            ))}
          {round.turns.map((turn, i) => (
            <div key={i} className="space-y-3">
              <TurnBubble
                turn={turn}
                lens={
                  glassBox && round.perceptions?.[turn.country]
                    ? {
                        perception: round.perceptions[turn.country],
                        misled: isMisled(round.perceptions[turn.country], round.event?.actors),
                      }
                    : undefined
                }
              />
              {round.flashes
                .filter((f) => f.afterTurn === i + 1)
                .map((f, j) => (
                  <FlashCard key={`flash-${i + 1}-${j}`} event={f.event} />
                ))}
            </div>
          ))}
        </div>
      )}

      {round.intelActions && round.intelActions.length > 0 && (
        <Banner tone="neutral">
          Le conseil a consulté ses services de renseignement ({round.intelActions.length} action
          {round.intelActions.length > 1 ? "s" : ""}).
          {round.intelActions.some((a) => a.exposed) && (
            <strong className="text-bad"> Un mensonge a été démasqué.</strong>
          )}
        </Banner>
      )}
      {round.motionFiled && (
        <Banner tone="warn">
          <strong>{speakerMeta(round.motionFiled.by).label}</strong> dépose une motion de
          suspension contre{" "}
          <strong>{speakerMeta(round.motionFiled.country).label}</strong>
          {round.motionFiled.reason ? ` — « ${round.motionFiled.reason} »` : ""}. La délibération
          s&apos;ouvrira automatiquement au prochain round.
        </Banner>
      )}

      {streaming && round.turns.length === 0 && !round.event && (
        <Panel>
          <p className="flex items-center gap-2 text-sm text-fg-muted">
            <Spinner /> Le Game Master compose l&apos;événement…
          </p>
        </Panel>
      )}

      {round.judgeText && (
        <JudgeRationale text={round.judgeText} streaming={streaming && !round.verdict} />
      )}
      {round.verdict && (
        <VerdictPanel
          deltas={round.verdict.deltas}
          escalation={round.verdict.escalation}
          economicDisruption={round.verdict.economic_disruption}
          actions={round.verdict.actions}
          reciprocal={round.verdict.reciprocal}
        />
      )}
      {round.communique && (
        <CommuniquePanel text={round.communique.text} support={round.communique.support} />
      )}
      {(round.motionText || round.motionVerdict || round.motionVotes.length > 0) && (
        <MotionPanel
          text={round.motionText}
          votes={round.motionVotes}
          tally={round.motionTally}
          verdict={round.motionVerdict}
          streaming={streaming}
        />
      )}
      {round.comparison && <ComparisonPanel comparison={round.comparison} />}

      {round.status === "done" && (
        <Banner tone="neutral">
          Round {round.roundNo} terminé et enregistré — relis-le quand tu veux dans{" "}
          <span className="text-foreground">la chronologie</span>
          .
        </Banner>
      )}

      {!showLive && detail && (
        <Panel>
          <PanelTitle
            kicker="Théâtre vide"
            title={
              playedRounds > 0
                ? `${playedRounds} round${playedRounds > 1 ? "s" : ""} déjà joué${playedRounds > 1 ? "s" : ""}`
                : "Le sommet n'a pas encore commencé"
            }
          />
          <p className="text-sm leading-relaxed text-fg-muted">
            {detail.live
              ? "Lance un round : le Game Master posera un événement, puis chaque IA prendra la parole ici, mot après mot."
              : "Les rounds joués restent lisibles dans Revoir."}
          </p>
          {detail.countries.length > 0 && (
            <div className="mt-4 flex flex-wrap gap-2">
              {detail.countries.map((c) => (
                <Pill key={c} tone="neutral">
                  <SpeakerAvatar id={c} size={18} />
                  {speakerMeta(c).label}
                </Pill>
              ))}
            </div>
          )}
        </Panel>
      )}
    </>
  );
}
