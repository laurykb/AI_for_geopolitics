/** Décisions pures de la bulle d'aide (`<Hint>`) — testées sans DOM.
 *
 * Deux façons d'ouvrir : le survol (volatil — quitter referme) et le clic ou le
 * focus clavier (épinglé — seuls Échap, un clic dehors ou la perte de focus
 * referment). C'est ce qui rend la bulle utilisable au clavier ET au tactile,
 * pas seulement à la souris. */

export type HintState = {
  open: boolean;
  /** true : ouverte par clic/focus — le survol qui s'en va ne referme pas. */
  pinned: boolean;
};

export type HintEvent =
  | "hover" // la souris entre sur le « ? »
  | "unhover" // la souris sort
  | "click" // clic souris ou tap tactile
  | "focus" // focus clavier
  | "blur" // le focus part ailleurs
  | "escape" // touche Échap
  | "outside"; // pointeur posé hors de la bulle

export const HINT_CLOSED: HintState = { open: false, pinned: false };

export function hintNext(state: HintState, event: HintEvent): HintState {
  switch (event) {
    case "hover":
      return state.open ? state : { ...state, open: true };
    case "unhover":
      return state.pinned ? state : HINT_CLOSED;
    case "click":
    case "focus":
      return { open: true, pinned: true };
    case "blur":
    case "escape":
    case "outside":
      return HINT_CLOSED;
  }
}
