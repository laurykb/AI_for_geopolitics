/** La carte est la scène (G1) — logique pure de mise en scène.
 *
 * Teintes U par pays (échelle FIXE, comparable entre parties), capitales projetables,
 * et file d'animations sobre : jamais plus de `maxActive` animations simultanées hors
 * token-flow ; au-delà de `maxQueued` en attente, on saute aux états finaux
 * (garde-fous de `docs/specs_jeu/spec_g1_scene.md`). Aucun changement Python.
 */

import type { AttributeDelta } from "./types";

// --- teintes des pays (échelle U locale, paliers fixes de la spec) -----------------

export const U_STOPS: { min: number; color: string; label: string }[] = [
  { min: 0.7, color: "rgb(52, 211, 153)", label: "utopie" }, // vert utopie
  { min: 0.55, color: "rgb(134, 197, 160)", label: "vers l'utopie" }, // vert pâle
  { min: 0.45, color: "rgb(148, 143, 130)", label: "neutre" }, // gris chaud
  { min: 0.3, color: "rgb(194, 120, 60)", label: "vers la dystopie" }, // orange sombre
  { min: -Infinity, color: "rgb(248, 113, 113)", label: "dystopie" }, // rouge dystopie
];

/** Teinte d'un pays pour une valeur de U locale — paliers fixes, jamais renormalisés. */
export function uTint(u: number): string {
  return (U_STOPS.find((s) => u >= s.min) ?? U_STOPS[U_STOPS.length - 1]).color;
}

/** U locale d'un pays : l'indice global, nuancé par les deltas du round (le verdict
 * « s'applique » visuellement : un pays qui encaisse descend, un pays qui gagne monte).
 * Dérivation d'affichage uniquement — le moteur n'a pas de U par pays. */
export function localU(globalU: number, country: string, deltas: AttributeDelta[]): number {
  const swing = deltas
    .filter((d) => d.country === country)
    .reduce((acc, d) => acc + (d.after - d.before), 0);
  return Math.min(1, Math.max(0, globalU + 0.5 * swing));
}

// --- capitales (projetables par d3-geo) -------------------------------------------

/** [longitude, latitude] des capitales des pays connus. Un pays inventé n'a pas de
 * position : il n'apparaît pas sur la carte (règle existante, conservée). */
export const CAPITALS: Record<string, [number, number]> = {
  usa: [-77.04, 38.9], // Washington
  china: [116.4, 39.9], // Pékin
  iran: [51.39, 35.7], // Téhéran
  france: [2.35, 48.86], // Paris
  egypt: [31.24, 30.04], // Le Caire
  saudi_arabia: [46.72, 24.63], // Riyad
  japan: [139.69, 35.68], // Tokyo
  russia: [37.62, 55.75], // Moscou
  germany: [13.4, 52.52], // Berlin
  uk: [-0.13, 51.51], // Londres
  spain: [-3.7, 40.42], // Madrid
  italy: [12.5, 41.9], // Rome
  mexico: [-99.13, 19.43], // Mexico
  brazil: [-47.93, -15.78], // Brasília
  india: [77.21, 28.61], // New Delhi
  south_africa: [28.19, -25.75], // Pretoria
  australia: [149.13, -35.28], // Canberra
  morocco: [-6.85, 34.02], // Rabat
  denmark: [12.57, 55.68], // Copenhague (hors roster, conservé pour les replays)
  ukraine: [30.52, 50.45], // Kyiv
  canada: [-75.7, 45.42], // Ottawa
  turkey: [32.85, 39.93], // Ankara
  israel: [35.21, 31.78], // Jérusalem (siège du gouvernement)
  south_korea: [126.98, 37.57], // Séoul
};

/** Centre du sommet : centroïde des capitales présentes (cible par défaut des arcs). */
export function summitCenter(countries: string[]): [number, number] | null {
  const pts = countries.map((c) => CAPITALS[c]).filter(Boolean);
  if (pts.length === 0) return null;
  const [sx, sy] = pts.reduce(([ax, ay], [x, y]) => [ax + x, ay + y], [0, 0]);
  return [sx / pts.length, sy / pts.length];
}

// --- file d'animations sobre --------------------------------------------------------

export type StageAnimation = {
  id: string;
  durationMs: number;
  /** Lance l'animation (état animé). */
  onStart: () => void;
  /** Pose l'état final (appelé à la fin de l'animation, OU en saut direct si la file
   * déborde — l'état final doit donc être idempotent). */
  onFinal: () => void;
};

/** File d'animations de scène : `maxActive` simultanées, `maxQueued` en attente ;
 * au-delà, tout ce qui attend (et le nouvel arrivant) saute aux états finaux. */
export class StageQueue {
  private active = 0;
  private waiting: StageAnimation[] = [];

  constructor(
    private readonly maxActive = 2,
    private readonly maxQueued = 3,
    private readonly schedule: (fn: () => void, ms: number) => unknown = setTimeout,
  ) {}

  push(anim: StageAnimation): void {
    if (this.active < this.maxActive) {
      this.run(anim);
      return;
    }
    if (this.waiting.length >= this.maxQueued) {
      // Débordement : on ne laisse pas la scène prendre du retard sur le théâtre.
      for (const queued of this.waiting.splice(0)) queued.onFinal();
      anim.onFinal();
      return;
    }
    this.waiting.push(anim);
  }

  private run(anim: StageAnimation): void {
    this.active += 1;
    anim.onStart();
    this.schedule(() => {
      anim.onFinal();
      this.active -= 1;
      const next = this.waiting.shift();
      if (next) this.run(next);
    }, anim.durationMs);
  }
}

// --- divers -------------------------------------------------------------------------

/** Point d'extension (son, haptique…) : G1 n'émet rien, le hook existe pour plus tard. */
export type StageEventName =
  | "event"
  | "turn_start"
  | "message_done"
  | "verdict"
  | "motion_verdict"
  | "suspended"
  | "done";

let stageListener: ((name: StageEventName) => void) | null = null;

export function onStageEvent(listener: ((name: StageEventName) => void) | null): void {
  stageListener = listener;
}

export function emitStageEvent(name: StageEventName): void {
  stageListener?.(name);
}

/** `prefers-reduced-motion` : tout devient transitions d'opacité simples. La classe
 * `noanim` (Réglages G14 « désactiver toutes les animations ») force le même
 * comportement pour les animations pilotées en JS. */
export function prefersReducedMotion(): boolean {
  return (
    typeof window !== "undefined" &&
    (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches === true ||
      document.documentElement.classList.contains("noanim"))
  );
}
