"use client";

/** StageProvider — le contexte de la scène persistante (spec coquille §2.1).
 *
 * Enveloppe le reducer pur `stage-director` dans un `useReducer` et expose les
 * transitions aux overlays. Les callbacks d'interaction (clic pays, bascule vue…)
 * vivent dans un REF mutable, pas dans l'état : l'overlay courant les enregistre
 * via `setHandlers`, et `StageShell` les relaie au globe par des wrappers stables
 * (aucune re-liaison de la boucle three à chaque render). */

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useReducer,
  useRef,
  type ReactNode,
} from "react";

import {
  INITIAL_DIRECTOR,
  directorReducer,
  type Phase,
  type StageIntent,
} from "@/lib/stage-director";

export type StageHandlers = {
  onCountryClick?: (slug: string) => void;
  onViewToggle?: () => void;
  onUserDrag?: () => void;
  onUnsupported?: () => void;
};

type StageContextValue = {
  phase: Phase;
  stage: StageIntent;
  goPhase: (phase: Phase, stage?: StageIntent) => void;
  setStage: (stage: StageIntent) => void;
  /** Ref lu par `StageShell` — l'overlay courant y pose ses callbacks. */
  handlers: React.RefObject<StageHandlers>;
  setHandlers: (h: StageHandlers) => void;
};

const StageContext = createContext<StageContextValue | null>(null);

export function StageProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(directorReducer, INITIAL_DIRECTOR);
  const handlers = useRef<StageHandlers>({});

  const goPhase = useCallback(
    (phase: Phase, stage?: StageIntent) => dispatch({ type: "goPhase", phase, stage }),
    [],
  );
  const setStage = useCallback((stage: StageIntent) => dispatch({ type: "setStage", stage }), []);
  const setHandlers = useCallback((h: StageHandlers) => {
    handlers.current = h;
  }, []);

  const value = useMemo<StageContextValue>(
    () => ({ phase: state.phase, stage: state.stage, goPhase, setStage, handlers, setHandlers }),
    [state, goPhase, setStage, setHandlers],
  );

  return <StageContext.Provider value={value}>{children}</StageContext.Provider>;
}

export function useStageDirector(): StageContextValue {
  const ctx = useContext(StageContext);
  if (!ctx) throw new Error("useStageDirector doit être utilisé sous <StageProvider>");
  return ctx;
}
