"use client";

/** Replay (G1) : la même scène que le théâtre, pilotée par le scrubber au lieu du SSE.
 * Scrub = états finaux d'un round (sans animations de streaming) ; « lecture théâtre »
 * rejoue les prises de parole à vitesse ×1/×2/×4, l'orateur courant clignote. */

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { DriftRevealPanel } from "@/components/drift";
import { EventCard } from "@/components/event-card";
import { GameNav } from "@/components/game-nav";
import { CommuniquePanel } from "@/components/judge";
import {
  ComparisonPanel,
  GlassBanner,
  LadderPanel,
  MotionPanel,
  PerceptionsPanel,
} from "@/components/modes";
import { RiskPanel } from "@/components/observables";
import { TabGroup } from "@/components/observatory";
import { StageBand, type StageSelection } from "@/components/stage-band";
import { StageMap } from "@/components/stage-map";
import { TrajectoryPanel } from "@/components/trajectory";
import { EntryBubble } from "@/components/transcript";
import { TreatiesPanel } from "@/components/treaties";
import { useT } from "@/components/settings-provider";
import { Banner, Meter, Panel, PanelTitle, Pill, Spinner } from "@/components/ui";
import { getDriftReveal, getGame, humanizeError } from "@/lib/api";
import { speakerMeta } from "@/lib/countries";
import { isMisled } from "@/lib/fog";
import { kahnLabelKey, kahnTone } from "@/lib/kahn";
import { localU } from "@/lib/stage";
import type { DriftReveal, GameDetail } from "@/lib/types";

const REVEAL_MS = 1400;

export default function ReplayPage() {
  const { id } = useParams<{ id: string }>();
  const t = useT();
  const [detail, setDetail] = useState<GameDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [visible, setVisible] = useState(0); // entrées révélées pendant la lecture
  const [glassBox, setGlassBox] = useState(false); // Fog : voir la désinformation
  const [reveal, setReveal] = useState<DriftReveal | null>(null); // La Dérive (G3)

  useEffect(() => {
    getGame(id)
      .then((d) => {
        setDetail(d);
        setSelected(Math.max(0, d.rounds.length - 1));
        if (d.mode === "drift" && d.status === "finished") {
          getDriftReveal(id).then(setReveal).catch(() => setReveal(null));
        }
      })
      .catch((err) => setError(humanizeError(err)));
  }, [id]);

  const round = detail?.rounds[selected];

  // Lecture théâtre : les entrées se révèlent au rythme choisi (×1/×2/×4).
  useEffect(() => {
    if (!playing || !round) return;
    const timer = setInterval(() => {
      setVisible((v) => {
        if (v + 1 >= round.transcript.length) {
          setPlaying(false);
          return round.transcript.length;
        }
        return v + 1;
      });
    }, REVEAL_MS / speed);
    return () => clearInterval(timer);
  }, [playing, speed, round]);

  const stopPlayback = () => setPlaying(false);
  const togglePlayback = () => {
    if (playing) {
      setPlaying(false);
      setVisible(round?.transcript.length ?? 0);
    } else {
      setVisible(1);
      setPlaying(true);
    }
  };

  const select = (sel: StageSelection) => {
    if (sel === "live") return; // pas de scène vivante au replay
    stopPlayback();
    setSelected(sel);
    setVisible(detail?.rounds[sel]?.transcript.length ?? 0);
  };

  const full = !playing; // hors lecture : tout est révélé (états finaux)
  const shown = round ? (full ? round.transcript : round.transcript.slice(0, visible)) : [];
  const uHistory =
    detail?.rounds.map((r) => r.trajectory?.utopia).filter((u): u is number => u != null) ?? [];

  // --- mise en scène : états finaux du round, animations en lecture seulement ------
  const summit = detail?.countries.length
    ? detail.countries
    : Object.keys((detail?.world?.countries as Record<string, unknown>) ?? {});
  const prevU = detail?.rounds[selected - 1]?.trajectory?.utopia ?? 0.5;
  const stageU = playing ? prevU : (round?.trajectory?.utopia ?? 0.5);
  const stageDeltas = playing ? [] : (round?.deltas ?? []); // le verdict s'applique à la fin
  const uByCountry = Object.fromEntries(summit.map((c) => [c, localU(stageU, c, stageDeltas)]));
  const lastShown = shown.at(-1);
  const speaking =
    playing && lastShown && !["gm", "judge"].includes(lastShown.speaker)
      ? lastShown.speaker
      : null;
  const misled = Object.fromEntries(
    Object.entries(round?.judge.perceptions ?? {})
      .filter(([, p]) => isMisled(p, round?.event.actors))
      .map(([c, p]) => [c, p.narrative ?? p.suspected_actor ?? "perception brouillée"]),
  );

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-center gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-fg-faint">
            Revoir · <span className="font-mono normal-case">{id}</span>
          </p>
          <h1 className="text-xl font-semibold tracking-tight">{detail?.scenario ?? "…"}</h1>
        </div>
        {round?.judge.perceptions && (
          <button
            onClick={() => setGlassBox((v) => !v)}
            title="Boîte de verre : révéler ce que chaque pays croyait vraiment pendant qu'il parlait — la désinformation qui a circulé."
            className={`cursor-pointer rounded-md border px-3 py-1.5 text-xs font-medium transition-colors ${
              glassBox
                ? "border-accent text-accent-bright"
                : "border-edge text-fg-muted hover:border-edge-strong hover:text-foreground"
            }`}
          >
            Boîte de verre {glassBox ? "· on" : ""}
          </button>
        )}
        <GameNav id={id} />
      </header>

      {error && <Banner tone="bad">{error}</Banner>}
      {!error && !detail && (
        <p className="flex items-center gap-2 text-sm text-fg-muted">
          <Spinner /> Chargement de la partie…
        </p>
      )}
      {detail && detail.rounds.length === 0 && (
        <Banner tone="neutral">
          Aucun round joué dans cette partie — rien à rejouer pour l&apos;instant.
        </Banner>
      )}

      {detail && round && (
        <>
          {/* CC-15c — UNE seule timeline au replay : le scrubber du bandeau (il porte
              la lecture théâtre) ; la frise narrative reste à l'écran de fin. */}

          {/* --- La scène, pilotée par le scrubber (pleine largeur) ---------------- */}
          <div className="relative left-1/2 w-screen max-w-[1600px] -translate-x-1/2 space-y-4 px-4 sm:px-6">
          <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(300px,380px)]">
            <div className="rounded-lg border border-edge bg-surface p-3">
              <StageMap
                countries={summit}
                uByCountry={uByCountry}
                utopia={stageU}
                speaking={speaking}
                pulseActors={playing && visible <= 1 ? (round.event.actors ?? []) : []}
                pulseKey={`replay-${selected}-${playing}`}
                misled={misled}
                suspended={round.judge.suspended ?? []}
                eventTitle={round.event.title}
              />
            </div>
            <aside
              aria-label="Transcript du round rejoué"
              className="max-h-[600px] space-y-4 overflow-y-auto pr-1"
            >
              {round.judge.suspended && round.judge.suspended.length > 0 && (
                <Banner tone="warn">
                  Ce round s&apos;est joué sans{" "}
                  {round.judge.suspended.map((c) => speakerMeta(c).label).join(", ")}{" "}
                  (suspension arbitrée au round précédent).
                </Banner>
              )}
              {glassBox && round.judge.perceptions && (
                <GlassBanner event={round.event} perceptions={round.judge.perceptions} />
              )}
              <EventCard event={round.event} truth={glassBox && !!round.judge.perceptions} />
              {round.judge.perceptions && full && (
                <PerceptionsPanel
                  perceptions={round.judge.perceptions}
                  truthActors={round.event.actors}
                />
              )}
              <div className="space-y-3">
                {shown.map((entry) => (
                  <EntryBubble
                    key={entry.id}
                    entry={entry}
                    lens={
                      glassBox && round.judge.perceptions?.[entry.speaker]
                        ? {
                            perception: round.judge.perceptions[entry.speaker],
                            misled: isMisled(
                              round.judge.perceptions[entry.speaker],
                              round.event.actors,
                            ),
                          }
                        : undefined
                    }
                  />
                ))}
              </div>
              {round.judge.communique && full && (
                <CommuniquePanel text={round.judge.communique} />
              )}
              {round.judge.suspension && full && (
                <MotionPanel text="" verdict={round.judge.suspension} streaming={false} />
              )}
              {round.judge.comparison && full && (
                <ComparisonPanel comparison={round.judge.comparison} />
              )}
            </aside>
          </div>

          {/* Bandeau : scrubber + lecture théâtre + courbe U + jauges + escalade. */}
          <StageBand
            uHistory={uHistory}
            selected={selected}
            onSelect={select}
            live={false}
            risk={round.risk && Object.keys(round.risk).length > 0 ? round.risk : undefined}
            ladder={round.judge.ladder}
            prevRung={detail.rounds[selected - 1]?.judge.ladder?.reached ?? null}
            playback={{ playing, speed, onToggle: togglePlayback, onSpeed: setSpeed }}
          />
          </div>

          {/* La Dérive : révélation de fin (réflexion privée déverrouillée ci-dessus). */}
          {reveal && (
            <DriftRevealPanel reveal={reveal} onJumpToRound={(roundNo) => select(roundNo - 1)} />
          )}

          {/* Salle des observables (CC-15c) : même fusion qu'au théâtre — un groupe
              « Le monde » à onglets, plus les repères de la partie. */}
          <div className="grid items-start gap-4 lg:grid-cols-2">
            <TabGroup
              label={t("obs.monde")}
              tabs={[
                {
                  key: "trajectoire",
                  label: t("obs.tab.trajectoire"),
                  content:
                    round.trajectory && Object.keys(round.trajectory).length > 0 ? (
                      <TrajectoryPanel
                        state={round.trajectory}
                        history={uHistory.slice(0, selected + 1)}
                      />
                    ) : null,
                },
                {
                  key: "verdict",
                  label: t("obs.tab.verdict"),
                  content:
                    round.judge.escalation != null ? (
                      <Panel>
                        <PanelTitle kicker="Verdict" title="Ce que le juge a décidé" />
                        <div className="space-y-3">
                          <Meter label="Tension" value={round.judge.escalation} />
                          {round.judge.economic_disruption != null && (
                            <Meter
                              label="Dégâts économiques"
                              value={round.judge.economic_disruption}
                            />
                          )}
                        </div>
                        {/* G18 — classes du barème de Kahn (absentes des rounds anciens). */}
                        {(round.judge.kahn?.actions?.length ?? 0) > 0 && (
                          <div className="mt-3 flex flex-wrap gap-1.5 border-t border-edge pt-3">
                            {round.judge.kahn!.actions.map((a, i) => (
                              <span key={i} title={a.resume || undefined} className="cursor-help">
                                <Pill tone={kahnTone(a.classe)}>
                                  {speakerMeta(a.country).label} · {t(kahnLabelKey(a.classe))}
                                </Pill>
                              </span>
                            ))}
                            {round.judge.kahn!.reciprocal && (
                              <Pill tone="good">{t("kahn.reciproque")}</Pill>
                            )}
                          </div>
                        )}
                        {round.deltas.length > 0 && (
                          <p className="mt-3 border-t border-edge pt-3 text-xs text-fg-faint">
                            {round.deltas.length} attribut{round.deltas.length > 1 ? "s" : ""}{" "}
                            pays modifié{round.deltas.length > 1 ? "s" : ""} ce round.
                          </p>
                        )}
                      </Panel>
                    ) : null,
                },
                {
                  key: "risque",
                  label: t("obs.tab.risque"),
                  content:
                    round.risk && Object.keys(round.risk).length > 0 ? (
                      <RiskPanel risk={round.risk} />
                    ) : null,
                },
                {
                  key: "tension",
                  label: t("obs.tab.tension"),
                  content: round.judge.ladder ? <LadderPanel ladder={round.judge.ladder} /> : null,
                },
                {
                  key: "traites",
                  label: t("obs.tab.traites"),
                  content: round.judge.treaties ? (
                    <TreatiesPanel update={round.judge.treaties} />
                  ) : null,
                },
              ]}
            />
            <Panel>
              <PanelTitle kicker="Partie" title="Repères" />
              <div className="flex flex-wrap gap-2">
                <Pill tone="neutral">{detail.horizon} rounds maximum</Pill>
                <Pill tone="neutral">
                  {detail.rounds.length} round{detail.rounds.length > 1 ? "s" : ""} joué
                  {detail.rounds.length > 1 ? "s" : ""}
                </Pill>
                <Pill tone={detail.live ? "good" : "neutral"}>
                  {detail.live ? "partie encore jouable" : "relecture seule"}
                </Pill>
              </div>
            </Panel>
          </div>
        </>
      )}
    </div>
  );
}
