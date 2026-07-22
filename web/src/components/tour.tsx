"use client";

/** La visite guidée & la mascotte « Laury » (G13).
 *
 * Le moteur (états, étapes, flags) est pur dans `lib/tour.ts` ; ce composant porte
 * React : navigation entre pages, ancrage de la bulle sur `[data-tour=…]`, la
 * proposition à la première connexion, le compagnon de coin d'écran et la partie de
 * démonstration jetable. Les pages ne portent QUE des attributs `data-tour`.
 *
 * Démo jetable : `POST /api/games` SANS owner_id (spectateur) — elle n'apparaît donc
 * ni dans « Tes dernières parties » (filtrées par owner) ni au Classement du jour
 * (aucune XP sans propriétaire), sans changement backend.
 */

import { usePathname, useRouter } from "next/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";

import { useAuth } from "@/components/auth-provider";
import { useT } from "@/components/settings-provider";
import tourData from "@/data/tour.json";
import tutorialData from "@/data/tutorial.json";
import { createGame, getGame } from "@/lib/api";
import { TUTORIAL_EVENT, tutorialMilestoneFromEvent } from "@/lib/tutorial-events";
import {
  initialTour,
  loadTourFlags,
  nextIndexWithoutDemo,
  nextStep,
  previousStep,
  resolvePage,
  resumeTour,
  saveDemoId,
  saveTourDone,
  saveTourStep,
  skipTour,
  startTour,
  type TourState,
  type TourStep,
} from "@/lib/tour";

const STEPS = tourData as TourStep[];
// CC-5 — le chapitre 0 réutilise le même moteur avec ses propres étapes (jalons
// data-tutorial posés par le théâtre : l'étape avance quand l'action est faite).
const TUTORIAL_STEPS = tutorialData as TourStep[];
const MASCOT_HIDDEN_KEY = "wosi.mascot.hidden"; // réactivable via Réglages (G14)
const tutorialDoneKey = (gameId: string) => `wosi.tutorial.${gameId}.done`;
const TARGET_TRIES = 20; // 20 × 150 ms ≈ 3 s avant de sauter une cible manquante
const BUBBLE_W = 340;

type TourApi = {
  state: TourState;
  /** Relance la visite depuis le header « ? » (reprend à l'étape sauvegardée). */
  restart: () => void;
  /** CC-5 — lance le guidage du chapitre 0 sur SA partie (une fois par partie). */
  startTutorial: (gameId: string) => void;
  /** Le compagnon coin bas-droit est-il masqué ? (Réglages G14 : « compagnon on/off ».) */
  mascotHidden: boolean;
  setMascotVisible: (visible: boolean) => void;
};

const TourContext = createContext<TourApi | null>(null);

export function useTour(): TourApi {
  const ctx = useContext(TourContext);
  if (!ctx) throw new Error("useTour doit être utilisé dans <TourProvider>");
  return ctx;
}

export function TourProvider({ children }: { children: React.ReactNode }) {
  const { player } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  const t = useT();
  const [state, setState] = useState<TourState>({ status: "idle", index: 0 });
  // « visite » = la découverte G13 ; « tutoriel » = le guidage du chapitre 0 (CC-5).
  const [mode, setMode] = useState<"visite" | "tutoriel">("visite");
  const [tutorialGameId, setTutorialGameId] = useState<string | null>(null);
  const [demoId, setDemoId] = useState<string | null>(null);
  const [anchor, setAnchor] = useState<DOMRect | null>(null); // rect de la cible
  const [centered, setCentered] = useState(false); // étape sans cible (bulle centrée)
  const [mascotHidden, setMascotHidden] = useState(true);
  const [menuOpen, setMenuOpen] = useState(false);

  const targetEl = useRef<HTMLElement | null>(null);
  const pushedFor = useRef<number>(-1); // une seule navigation par étape
  const demoCreating = useRef(false);
  const [reviewingIndex, setReviewingIndex] = useState<number | null>(null);

  // Les étapes du mode courant (tableaux constants : identité stable par mode).
  const steps = mode === "tutoriel" ? TUTORIAL_STEPS : STEPS;

  // --- flags du joueur (localStorage aujourd'hui ; profil en G14/CC-3) ------------
  // Lecture en microtâche : le stockage est un système externe, on ne pose pas
  // d'état de façon synchrone dans le corps de l'effet (règle set-state-in-effect).
  useEffect(() => {
    let alive = true;
    void Promise.resolve().then(() => {
      if (!alive) return;
      if (!player) {
        setState({ status: "idle", index: 0 });
        setMode("visite"); // une déconnexion interrompt aussi un tutoriel en cours
        return;
      }
      const flags = loadTourFlags(player.id, localStorage);
      setDemoId(flags.demoId);
      setState(initialTour(flags.done));
      setMascotHidden(localStorage.getItem(MASCOT_HIDDEN_KEY) === "1");
    });
    return () => {
      alive = false;
    };
  }, [player]);

  const persistStep = useCallback(
    (index: number) => {
      if (player) saveTourStep(player.id, index, localStorage);
    },
    [player],
  );

  /** Sortie définitive (Terminer, Passer, Échap). Visite : le flag neutralise la
   * proposition. Tutoriel : flag par PARTIE (pas de re-guidage au retour au théâtre),
   * puis retour au mode visite — les flags de la visite ne bougent pas. */
  const finish = useCallback(
    (next: TourState, opts: { resetStep?: boolean } = {}) => {
      setState(next);
      setAnchor(null);
      setCentered(false);
      if (mode === "tutoriel") {
        if (tutorialGameId) localStorage.setItem(tutorialDoneKey(tutorialGameId), "1");
        setMode("visite");
        return;
      }
      if (player) {
        saveTourDone(player.id, localStorage);
        if (opts.resetStep) saveTourStep(player.id, 0, localStorage); // « ? » repartira du début
      }
    },
    [player, mode, tutorialGameId],
  );

  const begin = useCallback(() => {
    setState(startTour());
    persistStep(0);
  }, [persistStep]);

  const advance = useCallback(() => {
    setReviewingIndex(null);
    const s2 = nextStep(state, steps.length);
    if (s2.status === "done") {
      finish(s2, { resetStep: true });
      return;
    }
    if (mode === "visite") persistStep(s2.index); // le tutoriel ne se reprend pas à l'étape
    setState(s2);
    setAnchor(null);
    setCentered(false);
  }, [state, steps, mode, finish, persistStep]);

  const retreat = useCallback(() => {
    const previous = previousStep(state, steps);
    if (previous.index === state.index) return;
    setReviewingIndex(previous.index);
    pushedFor.current = -1;
    if (mode === "visite") persistStep(previous.index);
    setState(previous);
    setAnchor(null);
    setCentered(false);
  }, [mode, persistStep, state, steps]);

  // L'étape sauvegardée reste en place : « ? » reprendra où on s'est arrêté.
  const skip = useCallback(() => {
    finish(skipTour(state));
  }, [state, finish]);

  /** Relance de la VISITE (header « ? », Réglages) — quitte un éventuel tutoriel. */
  const restart = useCallback(() => {
    if (!player) return;
    const flags = loadTourFlags(player.id, localStorage);
    pushedFor.current = -1;
    setMode("visite");
    setMenuOpen(false);
    setAnchor(null);
    setCentered(false);
    setState(resumeTour(flags.step, STEPS.length));
  }, [player]);

  /** CC-5 — guidage du chapitre 0 sur SA partie ; une fois par partie (flag local). */
  const startTutorial = useCallback((gameId: string) => {
    if (localStorage.getItem(tutorialDoneKey(gameId)) === "1") return;
    pushedFor.current = -1;
    setTutorialGameId(gameId);
    setMode("tutoriel");
    setMenuOpen(false);
    setAnchor(null);
    setCentered(false);
    setState({ status: "active", index: 0 });
  }, []);

  /** La partie de démonstration : réutilisée si elle existe encore, sinon recréée. */
  const ensureDemo = useCallback(async (): Promise<string | null> => {
    if (demoId) {
      try {
        await getGame(demoId);
        return demoId;
      } catch {
        // partie purgée : on en recrée une
      }
    }
    try {
      const game = await createGame({
        scenario: "red_sea",
        horizon: 3,
        mode: "classic",
        role: "spectator",
        difficulty: "beginner",
        drift_enabled: false,
      });
      if (player) saveDemoId(player.id, game.id, localStorage);
      return game.id;
    } catch {
      return null; // API injoignable : les étapes démo sauteront d'un bloc
    }
  }, [demoId, player]);

  // --- pilotage de l'étape active : naviguer, puis ancrer la bulle ----------------
  // Tous les setState passent par des callbacks (promesse, timers) — jamais dans le
  // corps de l'effet. Les resets d'ancre vivent dans advance/skip/restart/finish.
  useEffect(() => {
    if (state.status !== "active") return;
    const step = steps[state.index];
    if (!step) {
      // Garde défensive (index toujours borné par nextStep/resumeTour) — en timer,
      // jamais de setState synchrone dans le corps d'un effet.
      const t = setTimeout(() => finish({ status: "done", index: state.index }, { resetStep: true }), 0);
      return () => clearTimeout(t);
    }

    let cancelled = false;
    // Tutoriel : `{demo}` = la partie du chapitre 0 ; visite : la démo jetable.
    const page = resolvePage(step.page, mode === "tutoriel" ? tutorialGameId : demoId);

    // Démo requise et absente : la créer une fois — en échec, sauter le bloc démo.
    // (En tutoriel la partie existe par construction : id manquant = sortie propre.)
    if (page === null) {
      if (mode === "tutoriel") {
        const t = setTimeout(() => finish({ status: "done", index: state.index }), 0);
        return () => clearTimeout(t);
      }
      if (demoCreating.current) return;
      demoCreating.current = true;
      void ensureDemo().then((id) => {
        demoCreating.current = false;
        if (cancelled) return;
        if (id) {
          setDemoId(id);
          return; // l'effet se rejoue avec la démo résolue
        }
        const i = nextIndexWithoutDemo(steps, state.index);
        if (i >= steps.length) finish({ status: "done", index: i }, { resetStep: true });
        else {
          persistStep(i);
          setState({ status: "active", index: i });
        }
      });
      return () => {
        cancelled = true;
      };
    }

    // Mauvaise page (ou étape interne du lobby portée par ?etape=) : une navigation.
    const targetPath = page.split("?")[0];
    if (pathname !== targetPath || page.includes("?")) {
      if (pushedFor.current !== state.index) {
        pushedFor.current = state.index;
        router.push(page);
      }
      if (pathname !== targetPath) return; // l'effet se rejoue au changement de page
    }

    // Ancrer la bulle : cible trouvée → rect ; sans cible → centrée ; cible absente
    // après ~3 s → étape sautée sans crash. Avec un jalon `advanceOn`, la surveillance
    // RESTE ouverte : l'étape avance toute seule quand l'action attendue est faite
    // (et une cible manquante devient une bulle centrée au lieu d'un saut).
    const onMilestone = (event: Event) => {
      if (!step.advanceOn) return;
      if (reviewingIndex === state.index) return;
      const detail = tutorialMilestoneFromEvent(event);
      if (!detail || detail.milestone !== step.advanceOn) return;
      if (detail.gameId && tutorialGameId && detail.gameId !== tutorialGameId) return;
      advance();
    };
    window.addEventListener(TUTORIAL_EVENT, onMilestone);

    let tries = 0;
    let anchored = false;
    const tick = (): boolean => {
      if (
        step.advanceOn &&
        reviewingIndex !== state.index &&
        document.querySelector(`[data-tutorial="${step.advanceOn}"]`)
      ) {
        advance();
        return true;
      }
      if (step.target === null) {
        setCentered(true);
        setAnchor(null);
        return !step.advanceOn;
      }
      if (!anchored) {
        const el = document.querySelector<HTMLElement>(`[data-tour="${step.target}"]`);
        if (el) {
          anchored = true;
          targetEl.current = el;
          el.scrollIntoView({ block: "center", behavior: "auto" });
          setCentered(false);
          setAnchor(el.getBoundingClientRect());
        } else {
          tries += 1;
          if (tries >= TARGET_TRIES) {
            if (!step.advanceOn) {
              advance();
              return true;
            }
            setCentered(true); // cible absente mais action attendue : bulle centrée
            setAnchor(null);
          }
        }
      }
      return anchored && !step.advanceOn;
    };
    const iv = setInterval(() => {
      if (tick()) clearInterval(iv);
    }, 150);
    const t0 = setTimeout(() => {
      if (tick()) clearInterval(iv);
    }, 0);
    return () => {
      cancelled = true;
      clearInterval(iv);
      clearTimeout(t0);
      window.removeEventListener(TUTORIAL_EVENT, onMilestone);
    };
  }, [
    state,
    steps,
    mode,
    tutorialGameId,
    demoId,
    pathname,
    advance,
    ensureDemo,
    finish,
    persistStep,
    reviewingIndex,
    router,
  ]);

  // La bulle suit sa cible au scroll / redimensionnement. (isConnected : une cible
  // retirée du DOM — ex. le bouton motion après le dépôt — garde sa dernière position
  // au lieu d'un rect nul en haut à gauche.)
  useEffect(() => {
    if (state.status !== "active") return;
    const update = () => {
      if (targetEl.current?.isConnected) setAnchor(targetEl.current.getBoundingClientRect());
    };
    window.addEventListener("scroll", update, true);
    window.addEventListener("resize", update);
    return () => {
      window.removeEventListener("scroll", update, true);
      window.removeEventListener("resize", update);
    };
  }, [state]);

  // Échap : sortie propre à tout moment de la visite.
  useEffect(() => {
    if (state.status !== "active") return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") skip();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [state.status, skip]);

  const setMascotVisible = useCallback((visible: boolean) => {
    localStorage.setItem(MASCOT_HIDDEN_KEY, visible ? "0" : "1");
    setMascotHidden(!visible);
    setMenuOpen(false);
  }, []);

  // Chrome d'application seulement (mêmes règles que le header).
  const onAppPage = pathname !== "/" && !pathname.startsWith("/r/");
  const step = state.status === "active" ? steps[state.index] : null;
  const showCompanion =
    !!player && onAppPage && !mascotHidden && state.status !== "active";

  return (
    <TourContext.Provider
      value={{ state, restart, startTutorial, mascotHidden, setMascotVisible }}
    >
      {children}

      {/* Anneau sur la cible + bulle de la mascotte */}
      {step && !step.silent && anchor && (
        <div
          aria-hidden
          className="pointer-events-none fixed z-[70] rounded-lg border-2 border-accent-bright/80 shadow-[0_0_24px_rgba(234,179,8,0.25)]"
          style={{
            top: anchor.top - 6,
            left: anchor.left - 6,
            width: anchor.width + 12,
            height: anchor.height + 12,
          }}
        />
      )}
      {step && !step.silent && (anchor || centered) && (
        <TourBubble
          step={step}
          index={state.index}
          total={steps.length}
          kicker={mode === "tutoriel" ? "tour.ui.kicker-tutoriel" : "tour.ui.kicker-visite"}
          anchor={centered ? null : anchor}
          awaitingAction={!!step.advanceOn}
          reviewing={reviewingIndex === state.index}
          onBack={retreat}
          onNext={advance}
          onSkip={skip}
        />
      )}

      {/* Le compagnon (et la proposition de visite à la première connexion) */}
      {showCompanion && (
        <div className="fixed bottom-4 right-4 z-40 flex flex-col items-end gap-2">
          {state.status === "proposed" && (
            <div className="w-64 rounded-xl border border-edge bg-surface p-3 shadow-[0_16px_48px_-16px_rgba(0,0,0,0.8)]">
              <p className="text-sm">{t("tour.ui.salut")}</p>
              <div className="mt-2 flex justify-end gap-2">
                <button
                  onClick={() => setState({ status: "idle", index: 0 })}
                  className="cursor-pointer rounded-md border border-edge px-2.5 py-1 text-xs text-fg-muted transition-colors hover:border-edge-strong hover:text-foreground"
                >
                  {t("tour.ui.plus-tard")}
                </button>
                <button
                  autoFocus
                  onClick={begin}
                  className="cursor-pointer rounded-md bg-accent px-2.5 py-1 text-xs font-semibold text-background transition-colors hover:bg-accent-bright"
                >
                  {t("tour.ui.cest-parti")}
                </button>
              </div>
            </div>
          )}
          {menuOpen && state.status !== "proposed" && (
            <div className="w-52 rounded-xl border border-edge bg-surface p-2 shadow-[0_16px_48px_-16px_rgba(0,0,0,0.8)]">
              <button
                onClick={restart}
                className="block w-full cursor-pointer rounded-md px-2.5 py-1.5 text-left text-sm transition-colors hover:bg-surface-2"
              >
                {t("tour.ui.faire-visite")}
              </button>
              <button
                onClick={() => setMascotVisible(false)}
                className="block w-full cursor-pointer rounded-md px-2.5 py-1.5 text-left text-sm text-fg-muted transition-colors hover:bg-surface-2"
              >
                {t("tour.ui.masquer")}
              </button>
            </div>
          )}
          <button
            onClick={() => setMenuOpen((v) => !v)}
            aria-expanded={menuOpen}
            aria-label={t("tour.ui.aria-compagnon")}
            title="Laury"
            className="tour-companion cursor-pointer transition-transform hover:scale-105"
          >
            {/* eslint-disable-next-line @next/next/no-img-element -- SVG local, pas d'optimisation utile */}
            <img src="/mascotte/mascotte.svg" alt="" width={64} height={80} />
          </button>
        </div>
      )}
    </TourContext.Provider>
  );
}

/** La bulle : tête de la mascotte + texte court + Suivant / Passer. Ancrée sous (ou
 * sur) sa cible ; centrée en bas sans cible ou sur petit écran. */
function TourBubble({
  step,
  index,
  total,
  kicker,
  anchor,
  awaitingAction,
  reviewing,
  onBack,
  onNext,
  onSkip,
}: {
  step: TourStep;
  index: number;
  total: number;
  kicker: string;
  anchor: DOMRect | null;
  awaitingAction: boolean;
  reviewing: boolean;
  onBack: () => void;
  onNext: () => void;
  onSkip: () => void;
}) {
  const t = useT();
  const last = index === total - 1;

  // Position : sous la cible si la place le permet, sinon au-dessus ; bornée à
  // l'écran. Repli « feuille basse » : sans cible, ou sur mobile (spec).
  let style: React.CSSProperties | undefined;
  const sheet =
    anchor === null || (typeof window !== "undefined" && window.innerWidth < 640);
  if (!sheet && anchor) {
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const left = Math.min(
      Math.max(anchor.left + anchor.width / 2 - BUBBLE_W / 2, 12),
      Math.max(vw - BUBBLE_W - 12, 12),
    );
    const below = anchor.bottom + 220 < vh || anchor.top < 240;
    style = below
      ? { top: Math.min(anchor.bottom + 12, vh - 200), left }
      : { bottom: vh - anchor.top + 12, left };
  }

  return (
    <div
      role="dialog"
      aria-label={`${t("tour.ui.aria-bulle")} — ${t(step.title)}`}
      style={style}
      className={`fixed z-[80] w-[340px] max-w-[calc(100vw-2rem)] rounded-xl border border-edge bg-surface p-4 shadow-[inset_0_1px_0_0_rgba(248,250,252,0.06),0_24px_64px_-24px_rgba(0,0,0,0.9)] ${
        sheet ? "bottom-4 left-1/2 -translate-x-1/2" : ""
      }`}
    >
      <div className="flex items-start gap-3">
        {/* eslint-disable-next-line @next/next/no-img-element -- SVG local, pas d'optimisation utile */}
        <img
          src="/mascotte/mascotte-tete.svg"
          alt=""
          width={44}
          height={44}
          className="shrink-0 rounded-full border border-accent/40 bg-surface-2"
        />
        <div className="min-w-0">
          <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-fg-faint">
            {t(kicker)} · {index + 1}/{total}
          </p>
          <h2 className="mt-0.5 text-sm font-semibold text-foreground">{t(step.title)}</h2>
          <p className="mt-1 text-sm leading-relaxed text-fg-muted">{t(step.text)}</p>
        </div>
      </div>
      <div className="mt-4 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <button
            onClick={onSkip}
            className="cursor-pointer rounded-md border border-edge px-3 py-1.5 text-xs text-fg-muted transition-colors hover:border-edge-strong hover:text-foreground"
          >
            {t("tour.ui.passer")}
          </button>
          <button
            onClick={onBack}
            disabled={index === 0}
            className="cursor-pointer rounded-md border border-edge px-3 py-1.5 text-xs font-medium text-fg-muted transition-colors hover:border-edge-strong hover:text-foreground disabled:cursor-default disabled:opacity-35"
          >
            {t("tour.ui.retour")}
          </button>
        </div>
        <button
          autoFocus
          onClick={onNext}
          disabled={awaitingAction && !reviewing}
          className="cursor-pointer rounded-md bg-accent px-4 py-1.5 text-xs font-semibold text-background transition-colors hover:bg-accent-bright disabled:cursor-default disabled:bg-muted disabled:text-fg-faint"
        >
          {awaitingAction && !reviewing
            ? t("tour.ui.agis")
            : last
              ? t("tour.ui.terminer")
              : t("tour.ui.suivant")}
        </button>
      </div>
    </div>
  );
}
