/** CC-15c — densité d'affichage par difficulté (décision d'audit, inversée).
 *
 * AVANT (G11-d + lot G18-G23) : la difficulté CACHAIT des observables en Expert
 * (postures, griefs, jauge signal-action, parole donnée) — moins d'aide pour un jeu
 * plus dur. L'audit de simplicité (`docs/AUDIT_SIMPLICITE.md`) inverse la logique :
 * Débutant/Intermédiaire = SURFACE réduite (vues simples, replis fermés, 3 panneaux
 * d'observables au plus), Expert = tout affiché par défaut.
 *
 * La difficulté GAMEPLAY ne bouge pas : budget de renseignement, seuils du juge et
 * amplitude des deltas restent dans le moteur (`simulation/difficulty.py`). Ici, on ne
 * décide QUE de la densité de l'écran — plus aucun observable n'est masqué par la
 * difficulté. */

import type { Difficulty } from "./types";

export type Density = "reduced" | "full";

/** La règle unique : Expert voit tout, les autres jouent en surface réduite. */
export function densityFor(difficulty: Difficulty | undefined): Density {
  return (difficulty ?? "intermediate") === "expert" ? "full" : "reduced";
}

/** RG-4 — l'instrumentation (le MOTEUR) n'est visible qu'en Expert.
 *
 * Le tri « jeu vs moteur » (`docs/JEU_VS_MOTEUR.md` §4) : la façade par défaut
 * (Débutant/Intermédiaire) ne montre que le JEU — la scène (carte + transcript),
 * l'indice U en clair, le marché, et les outils de détection (motion, Boîte de
 * verre, Dossier, suspects). Tout le MOTEUR — les métriques M1-M7 (recherche de
 * pouvoir, corrigibilité, dérive des valeurs, compute, traités), les jauges
 * risque/escalade/trajectoire/participation détaillées, les panneaux de détection
 * fine (« elle dit / elle fait », « parole donnée », « l'ombre du GM ») — ne
 * s'affiche qu'en Expert, et n'est expliqué que dans l'onglet Informations.
 *
 * Rien n'est SUPPRIMÉ : le lot G18-G23 et M1-M7 sont ROUTÉS, pas retirés. */
export function engineVisible(difficulty: Difficulty | undefined): boolean {
  return densityFor(difficulty) === "full";
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
