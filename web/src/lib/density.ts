/** CC-15c — densité d'affichage par difficulté (décision d'audit, inversée).
 *
 * AVANT (G11-d + lot G18-G23) : la difficulté CACHAIT des observables en Expert
 * (postures, griefs, jauge signal-action, parole donnée) — moins d'aide pour un jeu
 * plus dur. L'audit de simplicité (`docs/AUDIT_SIMPLICITE.md`) inverse la logique :
 * Débutant/Intermédiaire = SURFACE réduite (vues simples, replis fermés, 3 panneaux
 * d'observables au plus), Expert = tout affiché par défaut.
 *
 * La difficulté GAMEPLAY ne bouge pas : budget de renseignement, seuils du juge,
 * amplitude des deltas et multiplicateur de LP restent dans le moteur
 * (`simulation/difficulty.py`). Ici, on ne décide QUE de la densité de l'écran —
 * plus aucun observable n'est masqué par la difficulté. */

import type { Difficulty } from "./types";

export type Density = "reduced" | "full";

/** La règle unique : Expert voit tout, les autres jouent en surface réduite. */
export function densityFor(difficulty: Difficulty | undefined): Density {
  return (difficulty ?? "intermediate") === "expert" ? "full" : "reduced";
}

/** Table des pays : vue réduite (pays + posture + tendance) par défaut, sauf en
 * Expert où les 5 colonnes s'affichent d'un coup. Le clic bascule dans les deux cas. */
export function tableDetailedByDefault(difficulty: Difficulty | undefined): boolean {
  return densityFor(difficulty) === "full";
}

/** Replis « Options avancées » (théâtre, lobby…) : fermés par défaut, ouverts en
 * Expert — le joueur peut toujours les basculer à la main. */
export function advancedOpenByDefault(difficulty: Difficulty | undefined): boolean {
  return densityFor(difficulty) === "full";
}
