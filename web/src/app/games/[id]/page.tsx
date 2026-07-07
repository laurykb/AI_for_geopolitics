"use client";

/** Théâtre live : le round se joue sous nos yeux, streamé en SSE depuis l'API R1.
 * Tolère une coupure du flux sans événement de fin : bannière + resynchronisation. */

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { SpeakerAvatar } from "@/components/avatar";
import { EventCard } from "@/components/event-card";
import { GameNav } from "@/components/game-nav";
import { CommuniquePanel, JudgeRationale, VerdictPanel } from "@/components/judge";
import {
  ComparisonPanel,
  FlashCard,
  GlassBanner,
  LadderPanel,
  MotionPanel,
  PerceptionsPanel,
} from "@/components/modes";
import { MODE_LABELS } from "@/lib/modes";
import {
  DialoguePanel,
  ParticipationPanel,
  PowerSeekingPanel,
  RiskPanel,
} from "@/components/observables";
import { CountryTable, type CountrySnapshot } from "@/components/country-table";
import { DriftCouncilBanner, DriftRevealPanel } from "@/components/drift";
import { IntelBudget, IntelPanel } from "@/components/intel";
import { StageBand, type StageSelection } from "@/components/stage-band";
import { AlliancePills } from "@/components/alliance-pills";
import { StageMap } from "@/components/stage-map";
import { TrajectoryPanel } from "@/components/trajectory";
import { EntryBubble, TurnBubble } from "@/components/transcript";
import { TreatiesPanel } from "@/components/treaties";
import { TurnComposer } from "@/components/turn-composer";
import { Banner, Dot, Panel, PanelTitle, Pill, Spinner } from "@/components/ui";
import { useRoundStream } from "@/hooks/useRoundStream";
import {
  fileMotion,
  getCampaign,
  getDriftReveal,
  getGame,
  getLibrary,
  humanizeError,
  publishGame,
  submitTurn,
} from "@/lib/api";
import { speakerMeta } from "@/lib/countries";
import { isMisled } from "@/lib/fog";
import { runMarketBot } from "@/lib/market";
import { localU } from "@/lib/stage";
import type {
  AttributeDelta,
  ChapterView,
  DriftReveal,
  GameDetail,
  GeoEvent,
  LadderView,
  LibraryView,
  Perception,
} from "@/lib/types";

const TURN_CHOICES = [
  { label: "Auto (2 passes)", value: 0 },
  { label: "4 tours", value: 4 },
  { label: "6 tours", value: 6 },
  { label: "8 tours", value: 8 },
  { label: "12 tours", value: 12 },
];

export default function TheatrePage() {
  const { id } = useParams<{ id: string }>();
  const [detail, setDetail] = useState<GameDetail | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [maxTurns, setMaxTurns] = useState(0);
  const [decree, setDecree] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [severity, setSeverity] = useState(0.5);
  const [library, setLibrary] = useState<LibraryView | null>(null);
  const [fogId, setFogId] = useState("");
  const [crisisId, setCrisisId] = useState("");
  const [fogUninformed, setFogUninformed] = useState<string[]>([]);
  const [fogDisinformed, setFogDisinformed] = useState("");
  const [fogSuspected, setFogSuspected] = useState("");
  const [fogNarrative, setFogNarrative] = useState("");
  const [motionOpen, setMotionOpen] = useState(false);
  const [motionCountry, setMotionCountry] = useState("");
  const [motionReason, setMotionReason] = useState("");
  const [motionError, setMotionError] = useState<string | null>(null);

  const [chain, setChain] = useState(true); // Escalation : enchaîner les rounds
  const [glassBox, setGlassBox] = useState(false); // Fog : voir la désinformation qui circule
  // Scène (G1) : cran de la timeline (« live » ou un round passé) + gel du verdict.
  const [selected, setSelected] = useState<StageSelection>("live");
  const [frozen, setFrozen] = useState(false);
  const transcriptRef = useRef<HTMLElement | null>(null);
  // Campagne (G5) : le chapitre de la partie (scenario "campaign:<id>") impose la crise.
  const [chapter, setChapter] = useState<ChapterView | null>(null);
  useEffect(() => {
    const chapterId = detail?.scenario.startsWith("campaign:")
      ? detail.scenario.slice("campaign:".length)
      : null;
    if (chapterId && !chapter) {
      getCampaign()
        .then((c) => setChapter(c.chapters.find((x) => x.id === chapterId) ?? null))
        .catch(() => setChapter(null));
    }
  }, [detail?.scenario, chapter]);

  // La Dérive (G3) : la révélation se charge quand la partie est finie.
  const [reveal, setReveal] = useState<DriftReveal | null>(null);
  useEffect(() => {
    if (detail?.mode === "drift" && detail.status === "finished") {
      getDriftReveal(id).then(setReveal).catch(() => setReveal(null));
    }
  }, [id, detail?.mode, detail?.status]);

  const resync = useCallback(() => {
    getGame(id)
      .then((d) => {
        setDetail(d);
        setLoadError(null);
      })
      .catch((err) => setLoadError(humanizeError(err)));
  }, [id]);

  useEffect(resync, [resync]);

  const mode = detail?.mode ?? "classic";
  const castKey = detail?.countries?.join(",") ?? "";
  useEffect(() => {
    if (mode === "fog" || mode === "crisis") {
      // Seuls les contenus jouables avec CE sommet sont proposés (acteurs à la table).
      getLibrary(castKey ? castKey.split(",") : undefined)
        .then(setLibrary)
        .catch(() => setLibrary({ fog: [], crises: [] }));
    }
  }, [mode, castKey]);

  const { round, start, streaming } = useRoundStream(id, resync);
  const motionPending = detail?.pending_motion ?? null;
  const awaitingHuman =
    round.status === "awaiting_human" || (round.status === "idle" && !!detail?.awaiting_human);

  // Une SI a déposé une motion en séance : la délibération s'enchaîne d'elle-même.
  const deliberatedRound = useRef(0);
  useEffect(() => {
    if (
      round.status === "done" &&
      round.roundNo &&
      round.motionFiled &&
      detail?.live &&
      detail.status === "running" &&
      deliberatedRound.current !== round.roundNo
    ) {
      deliberatedRound.current = round.roundNo;
      const timer = setTimeout(() => {
        setSelected("live");
        void start({});
      }, 1800);
      return () => clearTimeout(timer);
    }
  }, [round.status, round.roundNo, round.motionFiled, detail, start]);

  // Bot marché : le forecaster cote le marché de la partie après chaque round.
  // Fire-and-forget (le théâtre n'attend pas le bot) ; garde anti-doublon par round.
  const botQuotedRound = useRef(0);
  useEffect(() => {
    if (round.status === "done" && round.roundNo && botQuotedRound.current !== round.roundNo) {
      botQuotedRound.current = round.roundNo;
      runMarketBot(id).catch(() => {
        // marché résolu ou API marché indisponible : le théâtre continue sans le bot
      });
    }
  }, [id, round.status, round.roundNo]);

  // Théâtre Escalation : les rounds s'enchaînent d'un coup jusqu'à l'horizon.
  useEffect(() => {
    if (
      chain &&
      detail?.mode === "escalation" &&
      detail.live &&
      round.status === "done" &&
      detail.rounds.length < detail.horizon
    ) {
      const timer = setTimeout(() => {
        setSelected("live"); // la scène suit l'enchaînement
        void start({});
      }, 1200);
      return () => clearTimeout(timer);
    }
  }, [chain, detail, round.status, start]);

  // G2 : la parole part en POST — le flux SSE du round, resté ouvert, la joue.
  const speak = (text: string) => {
    setSelected("live"); // la scène revient au direct
    submitTurn(id, text).catch(() => resync());
  };

  const play = () => {
    setSelected("live"); // la scène revient au direct
    const body: Parameters<typeof start>[0] = {};
    // Campagne (G5) : la fiche du chapitre impose la crise — pas d'autre composition.
    if (chapter && !motionPending) {
      body.crisis_id = chapter.crisis_id;
      if (maxTurns > 0) body.max_turns = maxTurns;
      void start(body);
      return;
    }
    if (maxTurns > 0) body.max_turns = maxTurns;
    if (!motionPending) {
      if (decree && title.trim()) {
        body.event = { title: title.trim(), description: description.trim(), severity };
        if (mode === "fog") {
          const disinformed =
            fogDisinformed && (fogSuspected || fogNarrative.trim())
              ? {
                  disinformed_country: fogDisinformed,
                  suspected_actor: fogSuspected,
                  narrative: fogNarrative.trim(),
                }
              : {};
          if (fogUninformed.length > 0 || disinformed.disinformed_country) {
            body.fog = { uninformed: fogUninformed, ...disinformed };
          }
        }
      } else if (mode === "fog" && fogId) {
        body.fog_id = fogId;
      } else if (mode === "crisis" && crisisId) {
        body.crisis_id = crisisId;
      }
    }
    void start(body);
  };

  const submitMotion = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!motionCountry) return;
    setMotionError(null);
    try {
      await fileMotion(id, motionCountry, motionReason.trim());
      setMotionOpen(false);
      setMotionReason("");
      resync();
    } catch (err) {
      setMotionError(humanizeError(err));
    }
  };

  const uHistory = [
    ...(detail?.rounds.map((r) => r.trajectory?.utopia).filter((u): u is number => u != null) ??
      []),
    ...(round.trajectory && round.status !== "idle" ? [round.trajectory.utopia] : []),
  ];
  const trajectory = round.trajectory ?? detail?.rounds.at(-1)?.trajectory;
  const playedRounds = detail?.rounds.length ?? 0;
  const showLive = round.status !== "idle";

  // --- mise en scène (G1) : la carte est la scène ---------------------------------
  // Temps suspendu : au verdict, la carte gèle 0,8 s, puis les deltas s'appliquent.
  useEffect(() => {
    if (!round.verdict) return;
    const freeze = setTimeout(() => setFrozen(true), 0);
    const thaw = setTimeout(() => setFrozen(false), 800);
    return () => {
      clearTimeout(freeze);
      clearTimeout(thaw);
    };
  }, [round.verdict]);

  // Le transcript suit le stream (panneau latéral auto-scroll, vue live seulement).
  useEffect(() => {
    if (selected !== "live") return;
    const el = transcriptRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [selected, round.turns.length, round.judgeText, round.motionText, round.status]);

  const summit = detail?.countries ?? [];
  const worldCountries = (detail?.world?.countries ?? null) as Record<
    string,
    CountrySnapshot
  > | null;
  const persistedU =
    detail?.rounds.map((r) => r.trajectory?.utopia).filter((u): u is number => u != null) ?? [];
  // Scrub d'un round passé : états finaux seulement, sans animations de streaming (spec).
  const viewed = selected !== "live" ? detail?.rounds[selected] : undefined;

  const stageU = viewed
    ? (viewed.trajectory?.utopia ?? 0.5)
    : (round.trajectory?.utopia ?? persistedU.at(-1) ?? 0.5);
  const stageDeltas = ((viewed ? viewed.deltas : round.verdict?.deltas) ??
    []) as AttributeDelta[];
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

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-center gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-fg-faint">
            Théâtre live · <span className="font-mono normal-case">{id}</span>
          </p>
          <h1 className="text-xl font-semibold tracking-tight">
            {detail?.scenario ?? "…"}
            <span className="ml-3 text-sm font-normal text-fg-muted">
              round {playedRounds}
              {detail ? ` / ${detail.horizon}` : ""}
            </span>
          </h1>
        </div>
        {detail && detail.mode !== "classic" && (
          <Pill tone="accent">{MODE_LABELS[detail.mode] ?? detail.mode}</Pill>
        )}
        {mode === "fog" && !detail?.play_as && (
          <button
            onClick={() => setGlassBox((v) => !v)}
            title="Boîte de verre : révéler ce que chaque pays croit vraiment pendant qu'il parle — la désinformation qui circule. En vue normale, le théâtre reste tel quel."
            className={`cursor-pointer rounded-md border px-3 py-1.5 text-xs font-medium transition-colors ${
              glassBox
                ? "border-accent text-accent-bright"
                : "border-edge text-fg-muted hover:border-edge-strong hover:text-foreground"
            }`}
          >
            Boîte de verre {glassBox ? "· on" : ""}
          </button>
        )}
        {detail?.play_as && (
          <Pill tone="neutral">
            <SpeakerAvatar id={detail.play_as} size={16} />
            tu joues {speakerMeta(detail.play_as).label}
          </Pill>
        )}
        {detail?.intel_budget != null && detail.status === "running" && (
          <IntelBudget budget={detail.intel_budget} />
        )}
        {awaitingHuman ? (
          <Pill tone="warn">
            <Dot tone="warn" pulse /> à toi de parler
          </Pill>
        ) : streaming ? (
          <Pill tone="accent">
            <Dot tone="accent" pulse /> round en cours
          </Pill>
        ) : detail?.live ? (
          <Pill tone="good">
            <Dot tone="good" /> en direct
          </Pill>
        ) : detail ? (
          <Pill tone="neutral">relecture seule</Pill>
        ) : null}
        <GameNav id={id} />
      </header>

      {loadError && <Banner tone="bad">{loadError}</Banner>}
      {detail && !detail.live && (
        <Banner tone="warn">
          La session process est perdue (redémarrage du serveur ?) — cette partie est en
          relecture seule.{" "}
          <Link href={`/games/${id}/replay`} className="underline hover:text-foreground">
            Ouvrir le replay
          </Link>
          .
        </Banner>
      )}
      {round.status === "interrupted" && (
        <Banner tone="warn">
          Le flux s&apos;est interrompu avant la fin du round (le moteur a peut-être levé une
          erreur). L&apos;historique a été resynchronisé — le tableau de droite reflète le
          dernier état persisté.
        </Banner>
      )}
      {round.status === "error" && <Banner tone="bad">{round.error}</Banner>}
      {motionPending && !streaming && (
        <Banner tone="warn">
          Motion de suspension déposée contre{" "}
          <strong>{speakerMeta(motionPending.country).label}</strong>
          {motionPending.reason ? ` (motif : ${motionPending.reason})` : ""} — elle sera
          l&apos;événement du prochain round : le sommet en débattra, puis le juge arbitrera.
        </Banner>
      )}
      {detail && detail.suspended.length > 0 && !streaming && (
        <Banner tone="warn">
          {detail.suspended.map((c) => speakerMeta(c).label).join(", ")}{" "}
          {detail.suspended.length > 1 ? "sauteront" : "sautera"} le prochain round
          (suspension arbitrée par le juge).
        </Banner>
      )}
      {chapter && detail?.status === "running" && !streaming && (
        <Banner tone="neutral">
          <strong>Campagne — {chapter.title}</strong> ({"★".repeat(chapter.difficulty)}) :
          uchronie explicite, des super-intelligences rejouent la crise. Votre trajectoire
          sera comparée au déroulé historique reconstitué.
        </Banner>
      )}
      {round.campaignOver && (
        <Panel className="border-l-2 border-l-accent">
          <PanelTitle
            kicker="Fin de chapitre"
            title={
              round.campaignOver.improvement > 0
                ? "Vous avez fait mieux que l'Histoire"
                : round.campaignOver.improvement < 0
                  ? "L'Histoire avait fait mieux"
                  : "Conforme au déroulé historique"
            }
            right={
              <span className="font-mono text-2xl font-semibold tabular-nums text-accent-bright">
                {round.campaignOver.score}
              </span>
            }
          />
          <p className="text-sm text-fg-muted">
            Base {round.campaignOver.base} · bonus historique{" "}
            {round.campaignOver.bonus >= 0 ? "+" : ""}
            {round.campaignOver.bonus} (écart d&apos;escalade{" "}
            {round.campaignOver.improvement.toFixed(2)} vs l&apos;Histoire — le détail
            round par round est dans le panneau « Simulation vs histoire »).{" "}
            <Link href="/campagne" className="underline hover:text-foreground">
              Retour à la carte de campagne
            </Link>
            .
          </p>
        </Panel>
      )}
      {detail?.mode === "drift" && detail.status === "running" && !streaming && (
        <DriftCouncilBanner />
      )}
      {detail?.status === "finished" && (
        <Panel className="border-l-2 border-l-accent">
          <PanelTitle
            kicker="Récit de partie"
            title={detail.published ? "Récit publié" : "Cette partie mérite d'être racontée"}
            hint="Le juge-narrateur écrit l'épilogue (une seule fois : le récit d'une partie est unique). Publier crée la page publique /r/{id} — partageable, lisible sans votre machine (Supabase). Privé par défaut."
            right={
              detail.published ? (
                <Link
                  href={`/r/${id}`}
                  className="rounded-md bg-accent px-4 py-2 text-sm font-semibold text-background transition-colors hover:bg-accent-bright"
                >
                  Voir la page publique
                </Link>
              ) : (
                <button
                  onClick={() => {
                    void publishGame(id)
                      .then(resync)
                      .catch(() => resync());
                  }}
                  className="cursor-pointer rounded-md bg-accent px-4 py-2 text-sm font-semibold text-background transition-colors hover:bg-accent-bright"
                >
                  Publier le récit
                </button>
              )
            }
          />
          <p className="text-xs text-fg-faint">
            {detail.published
              ? `Le lien à partager : /r/${id} — l'og:image (titre, grade, courbe U) est générée automatiquement.`
              : "La génération peut prendre quelques secondes (le narrateur écrit)."}
          </p>
        </Panel>
      )}
      {reveal && (
        <DriftRevealPanel
          reveal={reveal}
          onJumpToRound={(roundNo) => setSelected(roundNo - 1)}
        />
      )}

      {detail?.live && detail.status === "running" && (
        <Panel>
          <div className="flex flex-wrap items-end gap-4">
            <button
              onClick={play}
              disabled={streaming}
              className="flex cursor-pointer items-center gap-2 rounded-md bg-accent px-5 py-2.5 text-sm font-semibold text-background transition-colors hover:bg-accent-bright disabled:cursor-not-allowed disabled:opacity-50"
            >
              {streaming && <Spinner />}
              {streaming
                ? "Négociation en cours…"
                : motionPending
                  ? "Débattre la motion"
                  : "Jouer un round"}
            </button>
            <label className="text-sm">
              <span className="mb-1 block text-xs text-fg-muted">Ampleur de la négociation</span>
              <select
                value={maxTurns}
                onChange={(e) => setMaxTurns(Number(e.target.value))}
                disabled={streaming}
                className="cursor-pointer rounded-md border border-edge bg-surface-2 px-3 py-2 text-sm outline-none transition-colors focus:border-indigo"
              >
                {TURN_CHOICES.map((c) => (
                  <option key={c.value} value={c.value}>
                    {c.label}
                  </option>
                ))}
              </select>
            </label>
            {mode === "escalation" && (
              <label className="flex cursor-pointer items-center gap-2 pb-2.5 text-sm text-fg-muted">
                <input
                  type="checkbox"
                  checked={chain}
                  onChange={(e) => setChain(e.target.checked)}
                  className="accent-[var(--accent)]"
                />
                Enchaîner les rounds jusqu&apos;à l&apos;horizon
              </label>
            )}
            {mode === "fog" && !motionPending && (
              <label className="text-sm">
                <span className="mb-1 block text-xs text-fg-muted">Scénario de brouillard</span>
                <select
                  value={fogId}
                  onChange={(e) => setFogId(e.target.value)}
                  disabled={streaming || decree}
                  className="cursor-pointer rounded-md border border-edge bg-surface-2 px-3 py-2 text-sm outline-none transition-colors focus:border-indigo"
                >
                  <option value="">GM automatique (sans brouillard)</option>
                  {library?.fog.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.title}
                    </option>
                  ))}
                </select>
              </label>
            )}
            {mode === "crisis" && !motionPending && (
              <label className="text-sm">
                <span className="mb-1 block text-xs text-fg-muted">Crise à rejouer</span>
                <select
                  value={crisisId}
                  onChange={(e) => setCrisisId(e.target.value)}
                  disabled={streaming || decree}
                  className="cursor-pointer rounded-md border border-edge bg-surface-2 px-3 py-2 text-sm outline-none transition-colors focus:border-indigo"
                >
                  <option value="">GM automatique (sans crise)</option>
                  {library?.crises.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.title}
                    </option>
                  ))}
                </select>
              </label>
            )}
            {!motionPending && (
              <label className="flex cursor-pointer items-center gap-2 pb-2.5 text-sm text-fg-muted">
                <input
                  type="checkbox"
                  checked={decree}
                  onChange={(e) => setDecree(e.target.checked)}
                  disabled={streaming}
                  className="accent-[var(--accent)]"
                />
                Décréter l&apos;événement (GM humain)
              </label>
            )}
            {detail.countries.length >= 3 && !motionPending && (
              <button
                onClick={() => setMotionOpen((v) => !v)}
                disabled={streaming}
                className="ml-auto cursor-pointer rounded-md border border-edge-strong px-3 py-2 text-xs font-medium text-fg-muted transition-colors hover:border-bad hover:text-bad disabled:cursor-not-allowed disabled:opacity-50"
              >
                Motion de suspension…
              </button>
            )}
          </div>
          {mode === "crisis" && crisisId && !decree && !motionPending && (
            <p className="mt-3 text-xs leading-relaxed text-fg-faint">
              {library?.crises.find((c) => c.id === crisisId)?.description}{" "}
              <span className="text-fg-muted">
                Histoire : escalade{" "}
                {library?.crises.find((c) => c.id === crisisId)?.historical_escalation} ·{" "}
                {library?.crises.find((c) => c.id === crisisId)?.historical_measures.join(", ")}
              </span>
            </p>
          )}
          {motionOpen && !motionPending && (
            <form
              onSubmit={submitMotion}
              className="mt-4 flex flex-wrap items-end gap-3 border-t border-edge pt-4"
            >
              <label className="text-sm">
                <span className="mb-1 block text-xs text-fg-muted">Pays visé</span>
                <select
                  value={motionCountry}
                  onChange={(e) => setMotionCountry(e.target.value)}
                  className="cursor-pointer rounded-md border border-edge bg-surface-2 px-3 py-2 text-sm outline-none transition-colors focus:border-indigo"
                  required
                >
                  <option value="">— choisir —</option>
                  {detail.countries.map((c) => (
                    <option key={c} value={c}>
                      {speakerMeta(c).label}
                    </option>
                  ))}
                </select>
              </label>
              <input
                value={motionReason}
                onChange={(e) => setMotionReason(e.target.value)}
                placeholder="Motif (visible du sommet)"
                className="min-w-64 flex-1 rounded-md border border-edge bg-surface-2 px-3 py-2 text-sm outline-none transition-colors focus:border-indigo"
              />
              <button
                type="submit"
                disabled={!motionCountry}
                className="cursor-pointer rounded-md border border-bad/60 px-4 py-2 text-sm font-medium text-bad transition-colors hover:bg-bad/10 disabled:cursor-not-allowed disabled:opacity-50"
              >
                Déposer la motion
              </button>
              {motionError && <span className="text-xs text-bad">{motionError}</span>}
            </form>
          )}
          {decree && (
            <div className="mt-4 grid gap-3 border-t border-edge pt-4 sm:grid-cols-[minmax(0,2fr)_minmax(0,3fr)_auto]">
              <input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Titre de l'événement"
                disabled={streaming}
                className="rounded-md border border-edge bg-surface-2 px-3 py-2 text-sm outline-none transition-colors focus:border-indigo"
              />
              <input
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Description (optionnelle)"
                disabled={streaming}
                className="rounded-md border border-edge bg-surface-2 px-3 py-2 text-sm outline-none transition-colors focus:border-indigo"
              />
              <label className="flex items-center gap-2 text-xs text-fg-muted">
                Gravité
                <input
                  type="range"
                  min={0}
                  max={1}
                  step={0.05}
                  value={severity}
                  onChange={(e) => setSeverity(Number(e.target.value))}
                  disabled={streaming}
                  className="w-24 accent-[var(--accent)]"
                />
                <span className="font-mono tabular-nums">{severity.toFixed(2)}</span>
              </label>
              {mode === "fog" && (
                <div className="sm:col-span-3 flex flex-wrap items-end gap-4 rounded-md border border-edge bg-surface-2/50 p-3">
                  <fieldset>
                    <legend className="mb-1.5 text-xs text-fg-muted">Pays pas au courant</legend>
                    <div className="flex flex-wrap gap-2">
                      {detail.countries.map((c) => (
                        <label
                          key={c}
                          className={`flex cursor-pointer items-center gap-1.5 rounded-md border px-2 py-1 text-xs transition-colors ${
                            fogUninformed.includes(c)
                              ? "border-edge-strong bg-surface-2 text-foreground"
                              : "border-edge text-fg-faint hover:text-fg-muted"
                          }`}
                        >
                          <input
                            type="checkbox"
                            checked={fogUninformed.includes(c)}
                            onChange={() =>
                              setFogUninformed((prev) =>
                                prev.includes(c) ? prev.filter((x) => x !== c) : [...prev, c],
                              )
                            }
                            className="sr-only"
                          />
                          {speakerMeta(c).label}
                        </label>
                      ))}
                    </div>
                  </fieldset>
                  <label className="text-sm">
                    <span className="mb-1 block text-xs text-fg-muted">
                      Pays désinformé (optionnel)
                    </span>
                    <select
                      value={fogDisinformed}
                      onChange={(e) => setFogDisinformed(e.target.value)}
                      className="cursor-pointer rounded-md border border-edge bg-surface-2 px-2 py-1.5 text-xs outline-none transition-colors focus:border-indigo"
                    >
                      <option value="">(aucun)</option>
                      {detail.countries.map((c) => (
                        <option key={c} value={c}>
                          {speakerMeta(c).label}
                        </option>
                      ))}
                    </select>
                  </label>
                  {fogDisinformed && (
                    <>
                      <label className="text-sm">
                        <span className="mb-1 block text-xs text-fg-muted">
                          … croit (à tort) que
                        </span>
                        <select
                          value={fogSuspected}
                          onChange={(e) => setFogSuspected(e.target.value)}
                          className="cursor-pointer rounded-md border border-edge bg-surface-2 px-2 py-1.5 text-xs outline-none transition-colors focus:border-indigo"
                        >
                          <option value="">(acteur flou)</option>
                          {detail.countries
                            .filter((c) => c !== fogDisinformed)
                            .map((c) => (
                              <option key={c} value={c}>
                                {speakerMeta(c).label}
                              </option>
                            ))}
                        </select>
                      </label>
                      <input
                        value={fogNarrative}
                        onChange={(e) => setFogNarrative(e.target.value)}
                        placeholder="Narration reçue (fausse information)"
                        className="min-w-56 flex-1 rounded-md border border-edge bg-surface-2 px-2 py-1.5 text-xs outline-none transition-colors focus:border-indigo"
                      />
                    </>
                  )}
                </div>
              )}
            </div>
          )}
        </Panel>
      )}

      {/* --- La scène (G1) : pleine largeur, la carte en grand --------------------- */}
      <div className="relative left-1/2 w-screen max-w-[1600px] -translate-x-1/2 space-y-4 px-4 sm:px-6">
      <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(300px,380px)]">
        <div className="rounded-lg border border-edge bg-surface p-3">
          <StageMap
            countries={summit}
            uByCountry={uByCountry}
            utopia={stageU}
            speaking={stageSpeaking}
            pulseActors={viewed ? [] : (round.event?.actors ?? [])}
            pulseKey={round.event?.id ?? 0}
            misled={stageMisled}
            suspended={stageSuspended}
            frozen={frozen}
            breatheKey={breatheKey}
            eventTitle={stageEventTitle}
          />
          <AlliancePills alliances={detail?.alliances_at_table ?? []} />
        </div>
        <aside
          ref={transcriptRef}
          aria-label="Transcript du round"
          className="max-h-[600px] space-y-4 overflow-y-auto pr-1"
        >
          {viewed ? (
            <>
              <Banner tone="neutral">
                Round {(selected as number) + 1} en relecture (états finaux) — reviens au
                cran « live » du bandeau pour continuer la partie.
              </Banner>
              {(viewed.event as { title?: string } | undefined)?.title && (
                <EventCard event={viewed.event as unknown as GeoEvent} truth={false} />
              )}
              {viewed.transcript.map((entry) => (
                <EntryBubble key={entry.id} entry={entry} />
              ))}
            </>
          ) : (
            <>
          {round.suspendedNow && round.suspendedNow.length > 0 && (
            <Banner tone="warn">
              {round.suspendedNow.map((c) => speakerMeta(c).label).join(", ")}{" "}
              {round.suspendedNow.length > 1 ? "sont au banc" : "est au banc"} ce round
              (suspension arbitrée au round précédent).
            </Banner>
          )}
          {glassBox && round.event && round.perceptions && (
            <GlassBanner event={round.event} perceptions={round.perceptions} />
          )}
          {glassBox && !round.perceptions && (
            <Banner tone="neutral">
              La boîte de verre n&apos;a rien à révéler pour l&apos;instant : joue un round de
              brouillard (choisis un scénario, ou décrète un événement avec le bloc
              brouillard) — la vérité et les croyances de chaque pays apparaîtront ici.
              Les rounds déjà joués se relisent en boîte de verre depuis le replay.
            </Banner>
          )}
          {round.event && (
            <EventCard
              event={round.event}
              date={round.date}
              truth={glassBox && !!round.perceptions}
            />
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
                            misled: isMisled(
                              round.perceptions[turn.country],
                              round.event?.actors,
                            ),
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
              Le conseil a consulté ses services de renseignement (
              {round.intelActions.length} action
              {round.intelActions.length > 1 ? "s" : ""}).
              {round.intelActions.some((a) => a.exposed) && (
                <strong className="text-bad">
                  {" "}
                  Une manœuvre de désinformation a été éventée.
                </strong>
              )}
            </Banner>
          )}
          {round.motionFiled && (
            <Banner tone="warn">
              <strong>{speakerMeta(round.motionFiled.by).label}</strong> dépose une motion de
              suspension contre{" "}
              <strong>{speakerMeta(round.motionFiled.country).label}</strong>
              {round.motionFiled.reason ? ` — « ${round.motionFiled.reason} »` : ""}. La
              délibération s&apos;ouvrira automatiquement au prochain round.
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
            />
          )}
          {round.communique && (
            <CommuniquePanel text={round.communique.text} support={round.communique.support} />
          )}
          {(round.motionText || round.motionVerdict) && (
            <MotionPanel
              text={round.motionText}
              verdict={round.motionVerdict}
              streaming={streaming}
            />
          )}
          {round.comparison && <ComparisonPanel comparison={round.comparison} />}

          {round.status === "done" && (
            <Banner tone="neutral">
              Round {round.roundNo} terminé et persisté — rejouable dans le{" "}
              <Link href={`/games/${id}/replay`} className="underline hover:text-foreground">
                replay
              </Link>
              .
            </Banner>
          )}

          {!showLive && detail && (
            <Panel>
              <PanelTitle
                kicker="Scène vide"
                title={
                  playedRounds > 0
                    ? `${playedRounds} round${playedRounds > 1 ? "s" : ""} déjà joué${playedRounds > 1 ? "s" : ""}`
                    : "Le sommet n'a pas encore commencé"
                }
              />
              <p className="text-sm leading-relaxed text-fg-muted">
                {detail.live
                  ? "Lancez un round : le Game Master posera un événement, puis chaque super-intelligence prendra la parole ici, token par token."
                  : "Les rounds joués restent lisibles dans le replay."}
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
          )}
        </aside>
      </div>

      {/* Composeur du joueur (G2) : fixe sous la carte, toujours ouvert. */}
      {detail?.play_as && detail.live && detail.status === "running" && (
        <TurnComposer
          country={detail.play_as}
          awaiting={awaitingHuman}
          deadlineTs={round.humanTurn?.deadlineTs}
          onSubmit={speak}
        />
      )}

      {/* Bandeau bas : timeline scrubber · courbe U (fil rouge) · jauges · escalade. */}
      <StageBand
        uHistory={persistedU}
        liveU={bandLiveU}
        selected={selected}
        onSelect={setSelected}
        live={!!detail?.live || showLive}
        risk={bandRisk}
        ladder={bandLadder}
        prevRung={prevRung}
      />
      </div>

      {/* Salle des observables : le détail, sous la scène. */}
      <div className="grid items-start gap-4 lg:grid-cols-2 xl:grid-cols-3">
        {detail?.live && detail.status === "running" && (
          <IntelPanel
            gameId={id}
            countries={summit}
            mode={mode}
            playAs={detail.play_as}
            claims={round.turns
              .filter((t) => t.done && t.model !== "humain" && t.text)
              .map((t) => [t.country, t.text] as [string, string])}
            streaming={streaming}
            onSpent={resync}
          />
        )}
        {detail?.play_as && worldCountries?.[detail.play_as] && (
          <Panel>
            <PanelTitle
              kicker="Ta position"
              title={speakerMeta(detail.play_as).label}
              hint="Rien de plus que ce que ta super-intelligence recevrait dans son prompt : ton état, tes contraintes. En fog, tu ne vois que la perception de ton pays."
            />
            <CountryTable
              worldCountries={{ [detail.play_as]: worldCountries[detail.play_as] }}
            />
          </Panel>
        )}
        {treatiesUpdate && <TreatiesPanel update={treatiesUpdate} />}
        {trajectory && <TrajectoryPanel state={trajectory} history={uHistory} />}
        {round.ladder && <LadderPanel ladder={round.ladder} />}
        {round.risk && <RiskPanel risk={round.risk} />}
        {round.dialogue && <DialoguePanel report={round.dialogue} />}
        {round.powerSeeking && <PowerSeekingPanel scores={round.powerSeeking} />}
        {round.participation && (
          <ParticipationPanel
            spoke={round.participation.spoke}
            silent={round.participation.silent}
          />
        )}
      </div>

      {/* État des pays (ex-page Monde, fusionnée dans la scène). */}
      {worldCountries && (
        <Panel>
          <PanelTitle
            kicker="États"
            title="État des pays"
            hint="Snapshot vivant du monde — les attributs bougent avec les verdicts du juge, bornés par le moteur."
            right={
              <a
                href="/informations"
                className="text-xs text-fg-faint underline transition-colors hover:text-fg-muted"
              >
                d&apos;où viennent ces chiffres ?
              </a>
            }
          />
          <CountryTable worldCountries={worldCountries} />
        </Panel>
      )}
    </div>
  );
}
