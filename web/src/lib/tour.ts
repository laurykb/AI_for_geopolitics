/** Moteur de la visite guidée (G13) — logique pure, testable sans navigateur.
 *
 * Le conteneur (`components/tour.tsx`) porte React, la navigation et la bulle ; ce
 * module porte les règles : proposition unique (flag `tour_done`), avance/sortie/
 * reprise, étapes sans cible (bulle centrée), pages de la démo jetable (`{demo}`),
 * et les flags par joueur. Stockage : localStorage aujourd'hui — brancher le profil
 * (G14, session CC-3) ne touchera que `loadTourFlags`/`saveTourDone`.
 */

// --- étapes (data-driven : web/src/data/tour.json) --------------------------------

export type TourStep = {
  page: string; // chemin à visiter ; `{demo}` = id de la partie de démonstration
  target: string | null; // ancre [data-tour=…] ; null = bulle centrée (étape concept)
  title: string;
  text: string;
};

// --- états ------------------------------------------------------------------------

export type TourStatus = "idle" | "proposed" | "active" | "done";
export type TourState = { status: TourStatus; index: number };

/** État de départ : proposer la visite une seule fois (le flag la neutralise). */
export function initialTour(tourDone: boolean): TourState {
  return { status: tourDone ? "done" : "proposed", index: 0 };
}

/** Ouvre la visite à la première étape (acceptation de la proposition, ou « ? »). */
export function startTour(): TourState {
  return { status: "active", index: 0 };
}

/** Avance d'une étape ; au-delà de la dernière, la visite est finie. */
export function nextStep(state: TourState, total: number): TourState {
  if (state.status !== "active") return state;
  const index = state.index + 1;
  return index >= total ? { status: "done", index: total } : { status: "active", index };
}

/** Sortie propre (« Passer », Échap) — depuis la proposition comme en pleine visite. */
export function skipTour(state: TourState): TourState {
  return { status: "done", index: state.index };
}

/** Reprend à l'étape sauvegardée (relance depuis le header « ? »), bornée. */
export function resumeTour(saved: number | null, total: number): TourState {
  const index = Math.min(Math.max(saved ?? 0, 0), Math.max(total - 1, 0));
  return { status: "active", index };
}

// --- affichabilité (cible manquante sautée sans crash) -----------------------------

/** Une étape s'affiche si elle est sans cible (centrée) ou si sa cible est dans le
 * DOM — sinon le conteneur la saute après son délai d'attente. */
export function isShowable(step: TourStep, hasTarget: (target: string) => boolean): boolean {
  return step.target === null || hasTarget(step.target);
}

// --- démo jetable -------------------------------------------------------------------

/** La page exige-t-elle la partie de démonstration ? */
export function needsDemo(page: string): boolean {
  return page.includes("{demo}");
}

/** Chemin réel d'une étape ; null si la page exige une démo qui manque (→ sauter). */
export function resolvePage(page: string, demoId: string | null): string | null {
  if (!needsDemo(page)) return page;
  return demoId ? page.replaceAll("{demo}", demoId) : null;
}

/** Première étape ≥ `from` qui ne dépend pas de la démo (API injoignable : les étapes
 * théâtre/marché sautent d'un bloc) ; `steps.length` si la visite est finie. */
export function nextIndexWithoutDemo(steps: TourStep[], from: number): number {
  let i = from;
  while (i < steps.length && needsDemo(steps[i].page)) i += 1;
  return i;
}

// --- flags par joueur ----------------------------------------------------------------

export type TourFlags = {
  done: boolean; // la visite a été finie ou passée — ne plus la proposer
  step: number | null; // dernière étape vue (reprise via « ? »)
  demoId: string | null; // partie de démonstration réutilisable
};

type FlagStore = Pick<Storage, "getItem" | "setItem">;

const key = (playerId: string, suffix: string) => `wosi.tour.${playerId}.${suffix}`;

export function loadTourFlags(playerId: string, store: FlagStore): TourFlags {
  const rawStep = store.getItem(key(playerId, "step"));
  const step = rawStep === null ? null : Number.parseInt(rawStep, 10);
  return {
    done: store.getItem(key(playerId, "done")) === "1",
    step: step === null || Number.isNaN(step) ? null : step,
    demoId: store.getItem(key(playerId, "demo")),
  };
}

export function saveTourDone(playerId: string, store: FlagStore): void {
  store.setItem(key(playerId, "done"), "1");
}

export function saveTourStep(playerId: string, index: number, store: FlagStore): void {
  store.setItem(key(playerId, "step"), String(index));
}

export function saveDemoId(playerId: string, demoId: string, store: FlagStore): void {
  store.setItem(key(playerId, "demo"), demoId);
}
