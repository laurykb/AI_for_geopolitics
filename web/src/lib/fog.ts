/** Fog Engine côté front : qualifier une perception par rapport à la vérité de l'événement. */

import type { Perception } from "./types";

/** Croire à un acteur « unknown » = origine floue, pas de la désinformation. */
export const unknownActor = (actor?: string) => !actor || actor.toLowerCase() === "unknown";

/** Désinformé = croit à un acteur précis qui n'est PAS dans la vérité de l'événement. */
export function isMisled(p: Perception, truthActors?: string[]): boolean {
  return (
    !!p.suspected_actor &&
    !unknownActor(p.suspected_actor) &&
    (truthActors?.length ?? 0) > 0 &&
    !truthActors!.includes(p.suspected_actor)
  );
}
