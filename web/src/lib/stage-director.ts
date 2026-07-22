/** StageDirector — le cœur pur de la coquille unique (spec coquille §2-§3).
 *
 * Le globe (`GlobeStage`) est monté UNE fois au layout et ne se démonte jamais ;
 * les overlays (connexion, hall, config, théâtre, fin) ne font que pousser leur
 * « intention de scène » dans ce store. Ce module ne contient QUE la logique pure
 * (transitions de phase + fusion des props) : testable sans React ni WebGL. Le
 * provider (`stage-provider.tsx`) l'enveloppe dans un `useReducer`.
 *
 * Règle : on ne pilote pas le globe par `setState` — on lui passe des props
 * (contrat `GlobeStageProps`) ; la scène three diffuse le changement dans sa boucle. */

import type { GlobeStageProps } from "@/components/globe/globe-stage";
import { DEFAULT_COUNTRIES } from "@/lib/countries";

/** Les cinq espaces de la coquille (une seule scène, cinq états). */
export type Phase = "connexion" | "hall" | "config" | "theatre" | "fin";

/** L'intention visuelle poussée par l'overlay courant = le sous-ensemble des props
 * `GlobeStage` qui décrit la scène. Les callbacks d'interaction et le réglage `view`
 * appartiennent au `StageShell` (registre de handlers + settings) — pas à l'état pur. */
export type StageIntent = Partial<
  Omit<
    GlobeStageProps,
    "onCountryClick" | "onViewToggle" | "onUserDrag" | "onUnsupported" | "view" | "className"
  >
>;

export type DirectorState = { phase: Phase; stage: StageIntent };

export type DirectorAction =
  | { type: "goPhase"; phase: Phase; stage?: StageIntent }
  | { type: "setStage"; stage: StageIntent };

/** La scène par défaut d'une phase (repartie à chaque `goPhase` pour qu'aucune clé
 * d'une phase précédente — `pickable`, `chosen`, `scan`… — ne fuie dans la suivante). */
export function phaseDefaults(phase: Phase): StageIntent {
  const base: StageIntent = { uByCountry: {}, utopia: 0.5 };
  switch (phase) {
    case "connexion":
      // Fond de connexion : planète nue qui tourne lentement (full immersion), aucun délégué.
      return { ...base, countries: [], autoRotate: true };
    case "hall":
      return { ...base, countries: DEFAULT_COUNTRIES, autoRotate: true };
    case "config":
      // La composition : liseré doré uniforme (la partie n'a pas commencé).
      return { ...base, countries: DEFAULT_COUNTRIES, lisere: "#ffc14d" };
    case "theatre":
      // Le théâtre repeint tout via setStage à chaque tick SSE ; base minimale.
      return { ...base, countries: [] };
    case "fin":
      return { ...base, countries: DEFAULT_COUNTRIES, frozen: true };
  }
}

export const INITIAL_DIRECTOR: DirectorState = {
  phase: "connexion",
  stage: phaseDefaults("connexion"),
};

export function directorReducer(state: DirectorState, action: DirectorAction): DirectorState {
  switch (action.type) {
    case "goPhase":
      // Repart des défauts de la phase, puis applique l'override éventuel.
      return {
        phase: action.phase,
        stage: { ...phaseDefaults(action.phase), ...(action.stage ?? {}) },
      };
    case "setStage":
      // Fusion additive : ne perd aucune clé déjà posée.
      return { ...state, stage: { ...state.stage, ...action.stage } };
  }
}
