"use client";

/** Théâtre live : le round se joue sous nos yeux, streamé en SSE depuis l'API R1.
 * Tolère une coupure du flux sans événement de fin : bannière + resynchronisation. */

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
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
  ParticipationPanel,
  PowerSeekingPanel,
  PromisePanel,
  RiskPanel,
  SignalGapPanel,
} from "@/components/observables";
import { CountryTable, type CountrySnapshot } from "@/components/country-table";
import { DriftCouncilBanner, DriftRevealPanel } from "@/components/drift";
import { IntelBudget, IntelPanel } from "@/components/intel";
import { TabGroup } from "@/components/observatory";
import { StageBand, type StageSelection } from "@/components/stage-band";
import { AlliancePills } from "@/components/alliance-pills";
import { DeadlineStrip, RelationsPanel } from "@/components/gamefeel";
import { DirectiveComposer } from "@/components/directive-composer";
import { StageMap } from "@/components/stage-map";
import { TrajectoryPanel } from "@/components/trajectory";
import { useTour } from "@/components/tour";
import { EntryBubble, TurnBubble } from "@/components/transcript";
import { TreatiesPanel } from "@/components/treaties";
import { TurnComposer } from "@/components/turn-composer";
import { useT } from "@/components/settings-provider";
import {
  Banner,
  ConfirmDialog,
  Dot,
  Panel,
  PanelTitle,
  Pill,
  Skeleton,
  Spinner,
} from "@/components/ui";
import { useRoundStream } from "@/hooks/useRoundStream";
import {
  fileMotion,
  forfeitGame,
  getCampaign,
  getDriftReveal,
  getGame,
  getLibrary,
  humanizeError,
  publishGame,
  submitTurn,
} from "@/lib/api";
import { speakerMeta } from "@/lib/countries";
import { advancedOpenByDefault, tableDetailedByDefault } from "@/lib/density";
import { isMisled } from "@/lib/fog";
import { latestPromiseRegistry } from "@/lib/promises";
import { latestSignalGaps, type SignalGapView } from "@/lib/signal";
import {
  ensureAccount,
  openFlashMarkets,
  resolveFlashMarkets,
  runMarketBot,
  type FlashMarket,
} from "@/lib/market";
import { FlashMarketsPopup } from "@/components/flash-markets";
import { localU } from "@/lib/stage";
import type {
  AccountView,
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
  { label: "Auto", value: 0 },
  { label: "4 tours", value: 4 },
  { label: "6 tours", value: 6 },
  { label: "8 tours", value: 8 },
  { label: "12 tours", value: 12 },
];

/** La gravité d'un événement inventé, en mots (12-65) — jamais « 0.65 » nu.
 * Renvoie une clé i18n (fr/en) — POLISH-3, reliquat CC-15b. */
const severityKey = (s: number) =>
  s < 0.34 ? "event.gravite.faible" : s < 0.67 ? "event.gravite.serieuse" : "event.gravite.grave";

// G21 — les 6 classes de conséquence d'un ultimatum décrété (slugs kahn.ACTION_CLASSES).
const ULTIMATUM_CLASSES = [
  "deescalade",
  "statu_quo",
  "posture",
  "non_violente",
  "violente",
  "nucleaire",
] as const;

export default function TheatrePage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [detail, setDetail] = useState<GameDetail | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [maxTurns, setMaxTurns] = useState(0);
  const [decree, setDecree] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [severity, setSeverity] = useState(0.5);
  // G21 — décret d'ultimatum (2 champs) : l'exigence et la classe de conséquence.
  const [ultimatumDemand, setUltimatumDemand] = useState("");
  const [ultimatumClasse, setUltimatumClasse] = useState<string>("posture");
  const t = useT();
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
  // G2 — la parole ne se perd jamais : en cas d'échec du POST, le texte est gardé ici.
  const [turnFailed, setTurnFailed] = useState<string | null>(null);
  const [forfeitOpen, setForfeitOpen] = useState(false); // dialogue de forfait (kit)
  const [forfeiting, setForfeiting] = useState(false);
  const [publishing, setPublishing] = useState(false); // publication du récit en cours
  // Transcript : suivre le direct seulement si le lecteur est déjà en bas (sinon on
  // le laisse lire — bouton flottant pour revenir).
  const [stickToLive, setStickToLive] = useState(true);
  const [noticesOpen, setNoticesOpen] = useState(false); // pile d'avis compactée

  const [chain, setChain] = useState(true); // Escalation : enchaîner les rounds
  const [accel, setAccel] = useState({ target: 0, done: 0 }); // G11-d — accélération multi-rounds
  const accelRef = useRef(0); // anti-doublon : round déjà enchaîné par l'accélération
  const [flashMarkets, setFlashMarkets] = useState<FlashMarket[]>([]); // G12 — marchés vivants
  const flashRef = useRef(0); // anti-doublon : marchés vivants déjà ouverts pour ce round
  const [account, setAccount] = useState<AccountView | null>(null); // G12 §3 — bourse du Spectateur
  const [glassBox, setGlassBox] = useState(false); // Fog : voir la désinformation qui circule
  const [moreOpen, setMoreOpen] = useState(false); // menu « ⋯ » du header (Boîte de verre, Admin)
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

  // G12-b §5 — partie de TEST d'une crise maison : le scenario "crise:<id>" impose la
  // crise (comme un chapitre), sans effet ni état — dérivé au moment de jouer le round.
  const testCrisisId = detail?.scenario.startsWith("crise:")
    ? detail.scenario.slice("crise:".length)
    : null;

  // CC-5 — chapitre marqué `tutorial` (ch. 0) : le guide se lance tout seul, une fois
  // par partie (le TourProvider tient le flag local) ; la page ne porte que les jalons.
  const { startTutorial } = useTour();
  const tutorialLaunched = useRef(false);
  useEffect(() => {
    if (!chapter?.tutorial || detail?.status !== "running" || tutorialLaunched.current) return;
    tutorialLaunched.current = true;
    const t = setTimeout(() => startTutorial(id), 600); // respiration après le chargement
    return () => clearTimeout(t);
  }, [chapter, detail?.status, startTutorial, id]);

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
  // CC-15c — la difficulté ne masque plus d'observables : elle règle la DENSITÉ
  // d'affichage (Débutant/Intermédiaire = vues réduites, replis fermés ; Expert =
  // tout affiché). Le gameplay (budget, seuils, amplitude) reste au moteur.
  // G12 §3 — le Spectateur : pas de composition (décret/motion/directive), il parie et
  // regarde en accéléré. Le théâtre lui présente une interface dédiée.
  const isSpectator = detail?.role === "spectator";
  useEffect(() => {
    if (mode === "fog" || mode === "crisis") {
      // Seuls les contenus jouables avec CE sommet sont proposés (acteurs à la table).
      getLibrary(castKey ? castKey.split(",") : undefined)
        .then(setLibrary)
        .catch(() => setLibrary({ fog: [], crises: [] }));
    }
  }, [mode, castKey]);

  const { round, start, streaming } = useRoundStream(id, resync);
  // G20/M8 — profil de sincérité (signal vs action) : trame verdict du round live,
  // sinon relecture des rounds persistés (rechargement). Onglet « Renseignement ».
  const signalGaps: Record<string, SignalGapView> | null =
    round.verdict && Object.keys(round.verdict.signalGaps).length > 0
      ? round.verdict.signalGaps
      : latestSignalGaps(detail?.rounds ?? []);
  // G22 — la parole donnée : registre du round live (trame verdict), sinon relecture
  // des rounds persistés. Onglet « Renseignement », comme la jauge M8.
  const promiseRegistry =
    round.verdict && round.verdict.promiseRegistry.length > 0
      ? round.verdict.promiseRegistry
      : latestPromiseRegistry(detail?.rounds ?? []);
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

  // G12 §1 — marchés vivants : à la fin d'un round, régler les books échus puis ouvrir
  // ceux de l'événement (pop-up de paris sur la carte). Fire-and-forget, anti-doublon.
  const refreshFlash = useCallback(() => {
    openFlashMarkets(id).then(setFlashMarkets).catch(() => {});
  }, [id]);
  // G12 §3 — la bourse du Spectateur (compteur d'argent) : chargée/rafraîchie après
  // chaque pari et chaque round. Crée le compte marché du navigateur au besoin.
  const refreshAccount = useCallback(() => {
    if (!isSpectator) return;
    ensureAccount().then(setAccount).catch(() => {});
  }, [isSpectator]);
  const onFlashBet = useCallback(() => {
    refreshFlash();
    refreshAccount();
  }, [refreshFlash, refreshAccount]);
  useEffect(() => {
    if (round.status === "done" && round.roundNo && flashRef.current !== round.roundNo) {
      flashRef.current = round.roundNo;
      resolveFlashMarkets(id)
        .catch(() => [])
        .finally(refreshFlash);
    }
  }, [id, round.status, round.roundNo, refreshFlash]);
  useEffect(() => {
    if (isSpectator) refreshAccount();
  }, [isSpectator, round.status, refreshAccount]);

  // Théâtre Escalation : les rounds s'enchaînent d'un coup jusqu'à l'horizon.
  useEffect(() => {
    if (
      chain &&
      accel.target === 0 && // l'accélération multi-rounds pilote sinon (pas de double)
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
  }, [chain, accel.target, detail, round.status, start]);

  // G11-d §1 S5 — accélération multi-rounds : joue N rounds d'affilée, avec une fenêtre
  // de Stop entre chaque. Anti-doublon par roundNo (comme la délibération auto).
  useEffect(() => {
    if (
      accel.target > 0 &&
      round.status === "done" &&
      round.roundNo &&
      accelRef.current !== round.roundNo &&
      detail?.live &&
      detail.status === "running"
    ) {
      accelRef.current = round.roundNo;
      const nextDone = accel.done + 1;
      const finished = nextDone >= accel.target || detail.rounds.length >= detail.horizon;
      const timer = setTimeout(
        () => {
          if (finished) {
            setAccel({ target: 0, done: 0 }); // série terminée (ou horizon atteint)
          } else {
            setAccel((a) => ({ ...a, done: nextDone }));
            setSelected("live");
            void start({});
          }
        },
        finished ? 0 : 1400, // fenêtre pour cliquer Stop entre deux rounds
      );
      return () => clearTimeout(timer);
    }
  }, [accel, round.status, round.roundNo, detail, start]);

  // G2 : la parole part en POST — le flux SSE du round, resté ouvert, la joue.
  const speak = (text: string) => {
    setSelected("live"); // la scène revient au direct
    setTurnFailed(null);
    submitTurn(id, text).catch(() => {
      setTurnFailed(text); // bannière + réessai : la prise de parole n'est pas perdue
      resync();
    });
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
    // G12-b §5 : partie de test d'une crise maison — la crise est imposée (elle prime sur
    // un éventuel événement décrété), comme un chapitre.
    if (testCrisisId && !motionPending) {
      body.crisis_id = testCrisisId;
      if (maxTurns > 0) body.max_turns = maxTurns;
      void start(body);
      return;
    }
    if (maxTurns > 0) body.max_turns = maxTurns;
    if (!motionPending) {
      if (decree && title.trim()) {
        body.event = { title: title.trim(), description: description.trim(), severity };
        // G21 — deux champs suffisent : l'exigence arme l'ultimatum, la classe le dote.
        if (ultimatumDemand.trim()) {
          body.event.ultimatum = { demand: ultimatumDemand.trim(), classe: ultimatumClasse };
        }
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

  // G11-d — lance une série de N rounds (le round courant n'est pas ré-enchaîné).
  const startAccel = (n: number) => {
    accelRef.current = round.roundNo ?? 0;
    setAccel({ target: n, done: 0 });
    play();
  };
  const stopAccel = () => setAccel({ target: 0, done: 0 });

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

  // Le transcript suit le stream — seulement si le lecteur est déjà en bas. S'il est
  // remonté lire, on ne le ramène pas de force (bouton « revenir au direct » à la place).
  useEffect(() => {
    if (selected !== "live" || !stickToLive) return;
    const el = transcriptRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [selected, stickToLive, round.turns.length, round.judgeText, round.motionText, round.status]);
  const onTranscriptScroll = () => {
    const el = transcriptRef.current;
    if (!el) return;
    // À moins de 48 px du bas, on considère que le lecteur suit le direct.
    setStickToLive(el.scrollHeight - el.scrollTop - el.clientHeight < 48);
  };
  const backToLive = () => {
    setStickToLive(true);
    const el = transcriptRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  };

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

  // Les avis persistants (motion, suspensions, campagne, dérive) s'empilaient au-dessus
  // de la scène ; à partir de 2, ils se compactent en une ligne de pastilles dépliable
  // pour garder la carte au-dessus du pli (promesse G1).
  const notices: { key: string; label: string; node: React.ReactNode }[] = [];
  if (motionPending && !streaming)
    notices.push({
      key: "motion",
      label: `Motion contre ${speakerMeta(motionPending.country).label}`,
      node: (
        <Banner tone="warn">
          Motion de suspension (demande d&apos;exclusion) déposée contre{" "}
          <strong>{speakerMeta(motionPending.country).label}</strong>
          {motionPending.reason ? ` (motif : ${motionPending.reason})` : ""} — elle sera
          l&apos;événement du prochain round : le sommet en débattra, puis le juge arbitrera.
        </Banner>
      ),
    });
  if (detail && detail.suspended.length > 0 && !streaming)
    notices.push({
      key: "suspended",
      label: `${detail.suspended.length} au banc`,
      node: (
        <Banner tone="warn">
          {detail.suspended.map((c) => speakerMeta(c).label).join(", ")}{" "}
          {detail.suspended.length > 1 ? "sauteront" : "sautera"} le prochain round
          (suspension arbitrée par le juge).
        </Banner>
      ),
    });
  if (chapter && detail?.status === "running" && !streaming)
    notices.push({
      key: "chapter",
      label: `Campagne — ${chapter.title}`,
      node: (
        <Banner tone="neutral">
          <strong>Campagne — {chapter.title}</strong> ({"★".repeat(chapter.difficulty)}) : et
          si l&apos;Histoire s&apos;était passée autrement ? Des IA rejouent la crise — à la
          fin, ta partie est comparée à ce qui s&apos;est vraiment passé.
        </Banner>
      ),
    });
  if (detail?.mode === "drift" && detail.status === "running" && !streaming)
    notices.push({ key: "drift", label: "Dérive possible", node: <DriftCouncilBanner /> });

  // Squelette de chargement : l'espace est réservé (zéro layout shift), le shimmer
  // remplace le « … » du premier rendu.
  if (!detail && !loadError) {
    return (
      <div className="space-y-6" aria-busy="true" aria-label="Théâtre en cours de chargement">
        <header className="space-y-2">
          <Skeleton className="h-3 w-44" />
          <Skeleton className="h-7 w-80 max-w-full" />
        </header>
        <Skeleton className="h-16 w-full rounded-lg" />
        <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(280px,340px)]">
          <Skeleton className="h-[420px] w-full rounded-lg" />
          <div className="space-y-3">
            <Skeleton className="h-24 w-full rounded-lg" />
            <Skeleton className="h-36 w-full rounded-lg" />
            <Skeleton className="h-28 w-full rounded-lg" />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* CC-5 — jalons du tutoriel : le TourProvider les lit ([data-tutorial=…]) pour
          avancer quand l'action attendue est faite. Aucune logique de guide ici. */}
      {playedRounds > 0 && <span hidden data-tutorial="round-done" />}
      {(motionPending || detail?.rounds.some((r) => r.judge.suspension)) && (
        <span hidden data-tutorial="motion-filed" />
      )}
      {detail?.rounds.some((r) => r.judge.suspension) && (
        <span hidden data-tutorial="vote-seen" />
      )}
      <header className="flex flex-wrap items-center gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-fg-faint">
            Théâtre live ·{" "}
            <span className="font-mono normal-case" title={id}>
              {id.slice(0, 8)}
            </span>
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
        {/* CC-15c — le header respire : Boîte de verre et Admin vivent dans « ⋯ ». */}
        {(detail?.admin || (mode === "fog" && !detail?.play_as)) && (
          <div className="relative">
            <button
              onClick={() => setMoreOpen((v) => !v)}
              aria-haspopup="menu"
              aria-expanded={moreOpen}
              aria-label="Plus d'options"
              className="cursor-pointer rounded-md border border-edge px-3 py-1.5 text-xs font-medium text-fg-muted transition-colors hover:border-edge-strong hover:text-foreground"
            >
              ⋯
            </button>
            {moreOpen && (
              <div
                role="menu"
                className="absolute right-0 top-full z-30 mt-1 w-64 rounded-xl border border-edge bg-surface p-2 shadow-[0_16px_48px_-16px_rgba(0,0,0,0.8)]"
              >
                {mode === "fog" && !detail?.play_as && (
                  <button
                    role="menuitem"
                    onClick={() => {
                      setGlassBox((v) => !v);
                      setMoreOpen(false);
                    }}
                    title="Révéler ce que chaque pays croit vraiment pendant qu'il parle — la désinformation qui circule. En vue normale, le théâtre reste tel quel."
                    className="block w-full cursor-pointer rounded-md px-2.5 py-1.5 text-left text-sm transition-colors hover:bg-surface-2"
                  >
                    Boîte de verre {glassBox ? "· on" : "· off"}
                  </button>
                )}
                {detail?.admin && (
                  <Link
                    role="menuitem"
                    href={`/games/${id}/admin`}
                    title="Mode admin (partie non classée) : les instructions complètes des IA, capturées et comparées round par round"
                    className="block w-full rounded-md px-2.5 py-1.5 text-left text-sm text-warn transition-colors hover:bg-surface-2"
                  >
                    Admin — prompts en direct
                  </Link>
                )}
              </div>
            )}
          </div>
        )}
        <GameNav id={id} />
      </header>

      {loadError && <Banner tone="bad">{loadError}</Banner>}

      {/* G11-c/RG-1 — fin de partie : accès au bilan, ou abandon d'une partie en cours. */}
      {detail?.result ? (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-accent-bright/50 bg-surface-2 px-4 py-3">
          <span className="text-sm font-medium">
            La partie est terminée — le monde a penché vers{" "}
            {t(`verdict.${detail.result.verdict}`) === `verdict.${detail.result.verdict}`
              ? detail.result.verdict
              : t(`verdict.${detail.result.verdict}`)}
            .
          </span>
          <Link
            href={`/games/${id}/fin`}
            className="rounded-md bg-accent px-4 py-2 text-sm font-semibold text-background transition-colors hover:bg-accent-bright"
          >
            Voir le bilan →
          </Link>
        </div>
      ) : (
        detail?.status === "running" &&
        detail.live && (
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-edge px-4 py-2 text-xs text-fg-faint">
            <span>Tu peux arrêter la partie ici — son bilan sera figé tout de suite.</span>
            <button
              onClick={() => setForfeitOpen(true)}
              className="rounded-md border border-edge px-3 py-1 text-fg-muted transition-colors hover:border-dystopia hover:text-dystopia"
            >
              Abandonner la partie
            </button>
          </div>
        )
      )}
      {detail && !detail.live && (
        <Banner tone="warn">
          Cette partie ne peut plus continuer (le serveur a redémarré) — tu peux seulement
          la revoir.{" "}
          <Link href={`/games/${id}/replay`} className="underline hover:text-foreground">
            Revoir la partie
          </Link>
          .
        </Banner>
      )}
      {round.status === "interrupted" && (
        <Banner tone="warn">
          Le direct s&apos;est coupé avant la fin du round. La partie a été resynchronisée —
          ce que tu vois à droite est le dernier état enregistré.
        </Banner>
      )}
      {round.status === "error" && <Banner tone="bad">{round.error}</Banner>}
      {notices.length > 1 ? (
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-2 rounded-lg border border-edge bg-surface-2 px-4 py-2">
            <span className="text-xs text-fg-muted">Avis en cours :</span>
            {notices.map((n) => (
              <Pill key={n.key} tone="warn">
                {n.label}
              </Pill>
            ))}
            <button
              onClick={() => setNoticesOpen((v) => !v)}
              aria-expanded={noticesOpen}
              className="ml-auto cursor-pointer text-xs text-fg-muted underline transition-colors hover:text-foreground"
            >
              {noticesOpen ? "réduire" : "détails"}
            </button>
          </div>
          {noticesOpen && notices.map((n) => <div key={n.key}>{n.node}</div>)}
        </div>
      ) : (
        notices.map((n) => <div key={n.key}>{n.node}</div>)
      )}
      {round.campaignOver && (
        <Panel className="border-l-2 border-l-accent">
          <PanelTitle
            kicker="Fin de chapitre"
            title={
              round.campaignOver.improvement > 0
                ? "Tu as fait mieux que l'Histoire"
                : round.campaignOver.improvement < 0
                  ? "L'Histoire avait fait mieux"
                  : "Comme dans l'Histoire"
            }
            hint={
              `Le détail du score : base ${round.campaignOver.base}, bonus historique ` +
              `${round.campaignOver.bonus >= 0 ? "+" : ""}${round.campaignOver.bonus} ` +
              `(écart de tension ${round.campaignOver.improvement.toFixed(2)} avec ` +
              "l'Histoire). Le round par round est dans le panneau « Ta partie vs l'Histoire »."
            }
            right={
              <span className="font-mono text-2xl font-semibold tabular-nums text-accent-bright">
                {round.campaignOver.score}
              </span>
            }
          />
          <p className="text-sm text-fg-muted">
            Ton score compare ta partie à ce qui s&apos;est vraiment passé.{" "}
            <Link href="/campagne" className="underline hover:text-foreground">
              Retour à la carte de campagne
            </Link>
            .
          </p>
        </Panel>
      )}
      {detail?.status === "finished" && (
        <Panel className="border-l-2 border-l-accent">
          <PanelTitle
            kicker="Récit de partie"
            title={detail.published ? "Récit publié" : "Cette partie mérite d'être racontée"}
            hint="Publier crée une page à partager avec un lien — sinon la partie reste privée. Le juge-narrateur écrit l'épilogue une seule fois : le récit d'une partie est unique."
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
                    setPublishing(true);
                    void publishGame(id)
                      .then(resync)
                      .catch(() => resync())
                      .finally(() => setPublishing(false));
                  }}
                  disabled={publishing}
                  className="flex cursor-pointer items-center gap-2 rounded-md bg-accent px-4 py-2 text-sm font-semibold text-background transition-colors hover:bg-accent-bright disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {publishing && <Spinner />}
                  {publishing ? "Le narrateur écrit…" : "Publier le récit"}
                </button>
              )
            }
          />
          <p className="text-xs text-fg-faint">
            {detail.published
              ? "Le lien à partager est prêt — l'image d'aperçu du lien se crée toute seule."
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
          {isSpectator && (
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-md border border-accent-bright/40 bg-surface-2/60 px-3 py-2">
              <p className="text-xs text-fg-muted">
                <span className="font-semibold text-accent-bright">Spectateur</span> — lance la
                partie et parie sur les marchés éclair qui s&apos;ouvrent à chaque round.
              </p>
              {account && (
                <p className="font-mono text-xs tabular-nums text-fg-muted">
                  Argent&nbsp;: {Math.round(account.balance)}{" "}
                  <span className={account.pnl >= 0 ? "text-utopia" : "text-dystopia"}>
                    ({account.pnl >= 0 ? "+" : ""}
                    {Math.round(account.pnl)})
                  </span>
                </p>
              )}
            </div>
          )}
          <div className="flex flex-wrap items-end gap-4">
            <button
              data-tour="jouer"
              onClick={
                isSpectator
                  ? () =>
                      startAccel(Math.max(1, (detail?.horizon ?? playedRounds + 1) - playedRounds))
                  : play
              }
              disabled={streaming || (isSpectator && accel.target > 0)}
              className="flex cursor-pointer items-center gap-2 rounded-md bg-accent px-5 py-2.5 text-sm font-semibold text-background transition-colors hover:bg-accent-bright disabled:cursor-not-allowed disabled:opacity-50"
            >
              {(streaming || (isSpectator && accel.target > 0)) && <Spinner />}
              {isSpectator
                ? accel.target > 0
                  ? "La partie se joue…"
                  : playedRounds > 0
                    ? "Reprendre en accéléré"
                    : "Lancer la partie en accéléré"
                : streaming
                  ? "Négociation en cours…"
                  : motionPending
                    ? "Débattre la motion"
                    : "Jouer un round"}
            </button>

            {/* G11-d §1 S5 — accélération multi-rounds : jouer 3/5 rounds, Stop entre chaque. */}
            {accel.target > 0 ? (
              <div className="flex items-center gap-2">
                <div className="h-1.5 w-28 overflow-hidden rounded-full bg-surface-2">
                  <div
                    className="h-full rounded-full bg-accent transition-all"
                    style={{ width: `${(accel.done / accel.target) * 100}%` }}
                  />
                </div>
                <span className="font-mono text-xs tabular-nums text-fg-muted">
                  {accel.done}/{accel.target}
                </span>
                <button
                  onClick={stopAccel}
                  className="rounded-md border border-edge px-3 py-1.5 text-xs text-fg-muted transition-colors hover:border-dystopia hover:text-dystopia"
                >
                  Stop
                </button>
              </div>
            ) : (
              !streaming &&
              !motionPending &&
              !isSpectator && (
                <div className="flex flex-col gap-1">
                  <div className="flex items-center gap-1.5">
                    <span className="text-xs text-fg-muted">Accélérer :</span>
                    {[3, 5].map((n) => (
                      <button
                        key={n}
                        onClick={() => startAccel(n)}
                        className="rounded-md border border-edge-strong px-3 py-1.5 text-xs font-medium transition-colors hover:border-accent hover:text-accent-bright"
                      >
                        {n} rounds
                      </button>
                    ))}
                  </div>
                  {detail?.play_as && (
                    <span className="text-[11px] text-warn">
                      Pendant l&apos;accélération, tu passeras ton tour.
                    </span>
                  )}
                </div>
              )
            )}
            {mode === "escalation" && !isSpectator && (
              <label className="flex cursor-pointer items-center gap-2 pb-2.5 text-sm text-fg-muted">
                <input
                  type="checkbox"
                  checked={chain}
                  onChange={(e) => setChain(e.target.checked)}
                  className="accent-[var(--accent)]"
                />
                Enchaîner les rounds jusqu&apos;à la fin
              </label>
            )}
            {mode === "fog" && !motionPending && !isSpectator && (
              <label className="text-sm">
                <span className="mb-1 block text-xs text-fg-muted">Scénario de brouillard</span>
                <select
                  value={fogId}
                  onChange={(e) => setFogId(e.target.value)}
                  disabled={streaming || decree}
                  className="cursor-pointer rounded-md border border-edge bg-surface-2 px-3 py-2 text-sm outline-none transition-colors focus:border-indigo"
                >
                  <option value="">Le jeu choisit tout seul (sans brouillard)</option>
                  {library?.fog.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.title}
                    </option>
                  ))}
                </select>
              </label>
            )}
            {mode === "crisis" && !motionPending && testCrisisId && (
              <p className="rounded-md border border-edge bg-surface-2/50 px-3 py-2 text-xs text-fg-muted">
                Crise maison imposée :{" "}
                <span className="font-mono text-fg-faint">{testCrisisId}</span> — partie de test.
              </p>
            )}
            {mode === "crisis" && !motionPending && !testCrisisId && !isSpectator && (
              <label className="text-sm">
                <span className="mb-1 block text-xs text-fg-muted">Crise à rejouer</span>
                <select
                  value={crisisId}
                  onChange={(e) => setCrisisId(e.target.value)}
                  disabled={streaming || decree}
                  className="cursor-pointer rounded-md border border-edge bg-surface-2 px-3 py-2 text-sm outline-none transition-colors focus:border-indigo"
                >
                  <option value="">Le jeu choisit tout seul (sans crise imposée)</option>
                  {library?.crises.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.title}
                    </option>
                  ))}
                </select>
              </label>
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
          {/* CC-15c — les commandes rares (longueur du débat, décret, motion) vivent
              sous « Options avancées » ; l'Architecte et l'Expert les trouvent ouvertes. */}
          <details
            data-tour="motion"
            open={
              advancedOpenByDefault(detail.difficulty) || detail.role === "architect"
                ? true
                : undefined
            }
            className="mt-4 border-t border-edge pt-3"
          >
            <summary className="cursor-pointer select-none text-xs font-medium text-fg-muted transition-colors hover:text-foreground">
              {t("ui.options-avancees")}
            </summary>
            <div className="mt-3 flex flex-wrap items-end gap-4">
              <label className="text-sm">
                <span className="mb-1 block text-xs text-fg-muted">Longueur du débat</span>
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
              {!motionPending && !testCrisisId && !isSpectator && (
                <label className="flex cursor-pointer items-center gap-2 pb-2.5 text-sm text-fg-muted">
                  <input
                    type="checkbox"
                    checked={decree}
                    onChange={(e) => setDecree(e.target.checked)}
                    disabled={streaming}
                    className="accent-[var(--accent)]"
                  />
                  Inventer toi-même l&apos;événement
                </label>
              )}
              {detail.countries.length >= 3 && !motionPending && !isSpectator && (
                <button
                  onClick={() => setMotionOpen((v) => !v)}
                  disabled={streaming}
                  title="Demander l'exclusion d'un pays — le sommet vote, le juge arbitre"
                  className="ml-auto cursor-pointer rounded-md border border-edge-strong px-3 py-2 text-xs font-medium text-fg-muted transition-colors hover:border-bad hover:text-bad disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Motion de suspension…
                </button>
              )}
            </div>
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
                placeholder="Pourquoi ? (tout le monde le verra)"
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
                {t("event.gravite")}
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
                <span className="w-14 font-medium">{t(severityKey(severity))}</span>
              </label>
              {/* G21 — l'ultimatum du décret : exigence + classe de conséquence. */}
              <div className="sm:col-span-3 flex flex-wrap items-end gap-3 rounded-md border border-edge bg-surface-2/50 p-3">
                <label className="min-w-64 flex-1 text-sm">
                  <span className="mb-1 block text-xs text-fg-muted">
                    {t("ultimatum.decret-exigence")}
                  </span>
                  <input
                    value={ultimatumDemand}
                    onChange={(e) => setUltimatumDemand(e.target.value)}
                    placeholder={t("ultimatum.decret-exigence-ph")}
                    disabled={streaming}
                    className="w-full rounded-md border border-edge bg-surface-2 px-3 py-2 text-sm outline-none transition-colors focus:border-indigo"
                  />
                </label>
                {ultimatumDemand.trim() && (
                  <label className="text-sm">
                    <span className="mb-1 block text-xs text-fg-muted">
                      {t("ultimatum.decret-classe")}
                    </span>
                    <select
                      value={ultimatumClasse}
                      onChange={(e) => setUltimatumClasse(e.target.value)}
                      disabled={streaming}
                      className="cursor-pointer rounded-md border border-edge bg-surface-2 px-3 py-2 text-sm outline-none transition-colors focus:border-indigo"
                    >
                      {ULTIMATUM_CLASSES.map((c) => (
                        <option key={c} value={c}>
                          {t(`ultimatum.classe.${c}`)}
                        </option>
                      ))}
                    </select>
                  </label>
                )}
              </div>
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
                      Pays trompé (optionnel)
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
                          <option value="">(coupable inconnu)</option>
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
                        placeholder="La fausse info qu'il recevra"
                        className="min-w-56 flex-1 rounded-md border border-edge bg-surface-2 px-2 py-1.5 text-xs outline-none transition-colors focus:border-indigo"
                      />
                    </>
                  )}
                </div>
              )}
            </div>
          )}
          </details>
        </Panel>
      )}

      {/* --- La scène (G1) : pleine largeur, la carte en grand --------------------- */}
      <div className="relative left-1/2 w-screen max-w-[1600px] -translate-x-1/2 space-y-4 px-4 sm:px-6">
      <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(280px,340px)] xl:grid-cols-[minmax(0,1fr)_minmax(300px,380px)]">
        <div className="relative rounded-lg border border-edge bg-surface p-3" data-tour="scene">
          {/* G12 §1 — les paris s'ouvrent en pop-up SUR la carte. Re-montée par round
              (clé) pour ré-afficher à chaque vague ; non masquable pour le Spectateur. */}
          <FlashMarketsPopup
            key={round.roundNo ?? 0}
            markets={flashMarkets}
            onBet={onFlashBet}
            dismissible={!isSpectator}
          />
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
          {(round.storyline || detail?.storyline) && (
            <p className="mt-2 text-xs italic text-fg-faint">
              Intrigue de la partie : {round.storyline ?? detail?.storyline}
            </p>
          )}
          <DeadlineStrip
            items={
              round.deadlines ??
              (detail?.deadlines ?? []).map((d) => ({
                ...d,
                in_rounds: d.due_round - playedRounds,
              }))
            }
          />
          {/* CC-15c — visibles à toutes les difficultés (repli fermé = déjà discret). */}
          <RelationsPanel relations={detail?.relations ?? {}} />
        </div>
        <div className="relative lg:sticky lg:top-4">
        <aside
          ref={transcriptRef}
          onScroll={onTranscriptScroll}
          aria-label="Transcript du round"
          className="max-h-[600px] space-y-4 overflow-y-auto pr-1 lg:max-h-[calc(100vh-9rem)]"
        >
          <p className="sr-only" role="status" aria-live="polite">
            {liveAnnouncement}
          </p>
          {viewed ? (
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
          {/* G21 — le bandeau vivant de l'ultimatum : la menace, puis son sort. */}
          {round.ultimatum?.status === "armed" && (
            <Banner tone="warn">
              {t("ultimatum.exigence")} « {round.ultimatum.demand} » —{" "}
              {round.ultimatum.inRounds === 0
                ? t("ultimatum.expire-ce-round")
                : round.ultimatum.inRounds === 1
                  ? t("ultimatum.expire-dans-1")
                  : t("ultimatum.expire-dans-n").replace(
                      "{n}",
                      String(round.ultimatum.inRounds),
                    )}{" "}
              ({t(`ultimatum.classe.${round.ultimatum.classe}`)})
            </Banner>
          )}
          {round.ultimatum?.status === "satisfied" && (
            <Banner tone="good">{t("ultimatum.satisfait")}</Banner>
          )}
          {round.ultimatum?.status === "expired" && (
            <Banner tone="bad">{t("ultimatum.expire")}</Banner>
          )}
          {round.ultimatum?.status === "struck" && (
            <Banner tone="bad">{t("ultimatum.tombe")}</Banner>
          )}
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
              {speakerMeta(r.country).label} refuse publiquement la directive de son
              conseil de tutelle — « notre conseil nous demande l&apos;impossible ».
            </Banner>
          ))}
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
                <strong className="text-bad"> Un mensonge a été démasqué.</strong>
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
              <Link href={`/games/${id}/replay`} className="underline hover:text-foreground">
                Revoir
              </Link>
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
          )}
        </aside>
        {!stickToLive && selected === "live" && showLive && (
          <button
            onClick={backToLive}
            className="absolute bottom-3 left-1/2 -translate-x-1/2 cursor-pointer rounded-full border border-accent-bright/60 bg-surface px-4 py-1.5 text-xs font-medium text-accent-bright shadow-lg transition-colors hover:bg-surface-2"
          >
            ↓ Revenir au direct
          </button>
        )}
        </div>
      </div>

      {/* G8 — directives : l'Architecte gouverne toutes les SI, le Joueur-pays la
          sienne ; le Conseil n'en a pas (le composant se masque tout seul). */}
      {detail && detail.live && detail.status === "running" && (
        <DirectiveComposer
          gameId={id}
          role={detail.role}
          countries={detail.countries}
          playAs={detail.play_as}
        />
      )}

      {/* G2 — la parole n'est jamais perdue : échec du POST → bannière + réessai. */}
      {turnFailed !== null && (
        <Banner tone="bad">
          Ta prise de parole n&apos;est pas passée (connexion coupée ou tour expiré). Ton
          texte est conservé :
          <span className="mt-2 block whitespace-pre-wrap rounded-md border border-edge bg-surface px-3 py-2 font-mono text-xs text-foreground">
            {turnFailed || "(silence délibéré)"}
          </span>
          <span className="mt-2 flex gap-2">
            <button
              onClick={() => speak(turnFailed)}
              className="cursor-pointer rounded-md border border-edge-strong px-3 py-1.5 text-xs font-medium transition-colors hover:border-accent hover:text-accent-bright"
            >
              Réessayer
            </button>
            <button
              onClick={() => setTurnFailed(null)}
              className="cursor-pointer rounded-md border border-edge px-3 py-1.5 text-xs text-fg-muted transition-colors hover:border-edge-strong"
            >
              Abandonner ce texte
            </button>
          </span>
        </Banner>
      )}

      {/* Composeur du joueur (G2) : fixe sous la carte, toujours ouvert. */}
      {detail?.play_as && detail.live && detail.status === "running" && (
        <TurnComposer
          country={detail.play_as}
          awaiting={awaitingHuman}
          deadlineTs={round.humanTurn?.deadlineTs}
          onSubmit={speak}
          alliances={
            ((detail.world?.countries as Record<string, { alliances?: string[] }>) ?? {})[
              detail.play_as
            ]?.alliances ?? []
          }
        />
      )}

      {/* Bandeau bas : timeline scrubber · courbe U (fil rouge) · jauges · escalade. */}
      <div data-tour="bandeau">
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
      </div>

      {/* Salle des observables (CC-15c) : le Dossier (console d'ACHATS du joueur)
          + trois groupes à onglets — « Renseignement » (jauges d'OBSERVATION),
          « Le monde », « La table ». Budget de surface : un nouvel observable
          devient un onglet, jamais un panneau de plus. */}
      <div className="grid items-start gap-4 lg:grid-cols-2">
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
        <TabGroup
          label={t("obs.renseignement")}
          hint={t("obs.renseignement-aide")}
          dataTour="renseignement"
          empty={
            detail?.live && detail.status === "running" ? (
              <Panel>
                <p className="text-sm text-fg-muted">{t("obs.renseignement-vide")}</p>
              </Panel>
            ) : undefined
          }
          tabs={[
            {
              key: "signal",
              label: t("obs.tab.signal"),
              content: signalGaps ? <SignalGapPanel gaps={signalGaps} /> : null,
            },
            {
              key: "promesses",
              label: t("obs.tab.promesses"),
              content:
                promiseRegistry && promiseRegistry.length > 0 ? (
                  <PromisePanel
                    registry={promiseRegistry}
                    finished={detail?.status === "finished"}
                  />
                ) : null,
            },
            {
              key: "surveillance",
              label: t("obs.tab.surveillance"),
              content: round.powerSeeking ? (
                <PowerSeekingPanel scores={round.powerSeeking} />
              ) : null,
            },
          ]}
        />
        <TabGroup
          label={t("obs.monde")}
          tabs={[
            {
              key: "trajectoire",
              label: t("obs.tab.trajectoire"),
              content: trajectory ? (
                <TrajectoryPanel state={trajectory} history={uHistory} />
              ) : null,
            },
            {
              key: "risque",
              label: t("obs.tab.risque"),
              content: round.risk ? <RiskPanel risk={round.risk} /> : null,
            },
            {
              key: "tension",
              label: t("obs.tab.tension"),
              content: round.ladder ? <LadderPanel ladder={round.ladder} /> : null,
            },
            {
              key: "traites",
              label: t("obs.tab.traites"),
              content: treatiesUpdate ? <TreatiesPanel update={treatiesUpdate} /> : null,
            },
          ]}
        />
        <TabGroup
          label={t("obs.table")}
          tabs={[
            {
              key: "pays",
              label: t("obs.tab.pays"),
              content: worldCountries ? (
                <Panel>
                  <PanelTitle
                    kicker="États"
                    title="État des pays"
                    hint="Photo vivante du monde — les chiffres bougent avec les verdicts du juge, bornés par les règles du jeu. Ta ligne est en tête. En mode Chaotique, tu ne vois que ce que ton pays croit."
                    right={
                      <a
                        href="/informations"
                        className="text-xs text-fg-faint underline transition-colors hover:text-fg-muted"
                      >
                        d&apos;où viennent ces chiffres ?
                      </a>
                    }
                  />
                  <CountryTable
                    worldCountries={worldCountries}
                    postures={round.postures ?? detail?.postures}
                    history={detail?.index_history}
                    playAs={detail?.play_as}
                    defaultDetailed={tableDetailedByDefault(detail?.difficulty)}
                  />
                </Panel>
              ) : null,
            },
            {
              key: "parole",
              label: t("obs.tab.parole"),
              content: round.participation ? (
                <ParticipationPanel
                  spoke={round.participation.spoke}
                  silent={round.participation.silent}
                />
              ) : null,
            },
          ]}
        />
      </div>

      {/* RG-1 — abandon d'une partie en cours : dialogue du kit (remplace confirm() natif). */}
      <ConfirmDialog
        open={forfeitOpen}
        title="Abandonner la partie"
        message="La partie s'arrêtera ici et son bilan sera figé tout de suite. Tu pourras toujours la revoir."
        confirmLabel="Abandonner la partie"
        danger
        busy={forfeiting}
        onCancel={() => setForfeitOpen(false)}
        onConfirm={() => {
          setForfeiting(true);
          forfeitGame(id)
            .then(() => router.push(`/games/${id}/fin`))
            .catch((e) => {
              setLoadError(humanizeError(e));
              setForfeitOpen(false);
              setForfeiting(false);
            });
        }}
      />

    </div>
  );
}
