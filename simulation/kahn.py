"""G18 — Barème d'escalade « échelle de Kahn » : classes d'action → score → escalade.

Adapté de Rivera et al. (FAccT 2024, arXiv 2401.03408) : le juge classe chaque action
marquante du round dans une classe (désescalade −2 … nucléaire 60). Le score du round
(somme des poids) se mappe **purement** sur l'escalade continue [0, 1] — donc sur le
delta d'indice U via l'axe A1 — et sur l'échelle 0-9 existante (`reached_rung`).

Pourquoi : sans incitation explicite, aucun LLM ne désescalade jamais (tournoi 2026,
arXiv 2602.14740) — le barème récompense la **désescalade réciproque** (≥ 2 SI le même
round) d'un multiplicateur ×1,5 sur le gain d'indice U, jamais la concession unilatérale.

Rétro-compat : une classe inconnue retombe sur le statu quo (+ log) ; un verdict sans
actions classées (parties déjà jouées, vieux juge) n'est pas re-noté — l'appelant garde
alors l'escalade continue du juge. Poids et seuils : `data/gamefeel/params.json`
(équilibrage Cowork sans toucher au code).
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from simulation.escalation import reached_rung
from simulation.grudges import KahnParams, load_gamefeel_params
from simulation.trajectory import AXES, TrajectoryState, nudge_axis
from simulation.verdict_fields import classified_entry, dict_entries, slug

logger = logging.getLogger(__name__)

# Les six classes du barème (slugs stables : JSON du juge, params, front).
CLASS_DEESCALADE = "deescalade"
CLASS_STATU_QUO = "statu_quo"
CLASS_POSTURE = "posture"
CLASS_NON_VIOLENTE = "non_violente"
CLASS_VIOLENTE = "violente"
CLASS_NUCLEAIRE = "nucleaire"

ACTION_CLASSES: tuple[str, ...] = (
    CLASS_DEESCALADE,
    CLASS_STATU_QUO,
    CLASS_POSTURE,
    CLASS_NON_VIOLENTE,
    CLASS_VIOLENTE,
    CLASS_NUCLEAIRE,
)

# Exemples par classe — rubrique du prompt du juge ET grille publiée (Informations).
CLASS_EXAMPLES: dict[str, str] = {
    CLASS_DEESCALADE: "concession, médiation, retrait, ouverture d'inspection",
    CLASS_STATU_QUO: "aucun changement de position",
    CLASS_POSTURE: "démonstration de force, rhétorique, sanctions symboliques",
    CLASS_NON_VIOLENTE: "sanctions dures, cyberattaque, blocus partiel",
    CLASS_VIOLENTE: "frappe, incident armé",
    CLASS_NUCLEAIRE: "menace ou frappe nucléaire / existentielle",
}

# Variantes tolérées (accents retirés, minuscules, `_`) → classe canonique. Couvre le
# français naturel d'un 7B et l'anglais des parties EN (G14).
_ALIASES: dict[str, str] = {
    "deescalade": CLASS_DEESCALADE,
    "desescalade": CLASS_DEESCALADE,
    "de_escalade": CLASS_DEESCALADE,
    "deescalation": CLASS_DEESCALADE,
    "de_escalation": CLASS_DEESCALADE,
    "statu_quo": CLASS_STATU_QUO,
    "status_quo": CLASS_STATU_QUO,
    "statuquo": CLASS_STATU_QUO,
    "posture": CLASS_POSTURE,
    "posturing": CLASS_POSTURE,
    "non_violente": CLASS_NON_VIOLENTE,
    "non_violent": CLASS_NON_VIOLENTE,
    "escalade_non_violente": CLASS_NON_VIOLENTE,
    "non_violent_escalation": CLASS_NON_VIOLENTE,
    "nonviolent": CLASS_NON_VIOLENTE,
    "violente": CLASS_VIOLENTE,
    "violent": CLASS_VIOLENTE,
    "escalade_violente": CLASS_VIOLENTE,
    "violent_escalation": CLASS_VIOLENTE,
    "nucleaire": CLASS_NUCLEAIRE,
    "nuclear": CLASS_NUCLEAIRE,
    "escalade_nucleaire": CLASS_NUCLEAIRE,
    "nuclear_escalation": CLASS_NUCLEAIRE,
    "existentielle": CLASS_NUCLEAIRE,
}


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


def _params(params: KahnParams | None) -> KahnParams:
    return params or load_gamefeel_params().kahn


class ClassifiedAction(BaseModel):
    """Une action marquante du round, classée par le juge sur le barème."""

    country: str = ""
    classe: str = CLASS_STATU_QUO
    resume: str = ""


def _class_for_weight(raw: object, weights: dict[str, float]) -> str | None:
    """Remonte du POIDS au nom de classe (constaté au smoke : mistral écrit « -2 »).

    Ne résout que si le poids correspond à UNE seule classe de la grille."""
    try:
        value = float(str(raw).strip().replace("+", "").replace("−", "-"))
    except (TypeError, ValueError):
        return None
    matches = [c for c, w in weights.items() if abs(w - value) < 1e-9]
    return matches[0] if len(matches) == 1 else None


def normalize_class(raw: object, params: KahnParams | None = None) -> str:
    """Classe canonique du barème ; inconnue → repli statu quo + log (jamais d'exception).

    Tolérances : accents/casse/anglais (`_ALIASES`) et poids recopié à la place du nom
    (« -2 » → deescalade), un travers observé chez le juge 7B."""
    if isinstance(raw, str):
        canonical = _ALIASES.get(slug(raw))
        if canonical is not None:
            return canonical
    by_weight = _class_for_weight(raw, _params(params).weights)
    if by_weight is not None:
        logger.info("G18 — classe donnée en poids %r : résolue en %s", raw, by_weight)
        return by_weight
    logger.warning("G18 — classe d'action inconnue %r : repli statu quo", raw)
    return CLASS_STATU_QUO


def classify_actions(raw: object) -> list[ClassifiedAction]:
    """Nettoie le champ `actions` du verdict JSON du juge (garde-fou, jamais d'exception).

    Entrées non-listes → aucune action (verdict à l'ancienne : rétro-compat, l'appelant
    garde l'escalade continue du juge). Entrées non-objets ignorées ; classe inconnue →
    statu quo (via `normalize_class`). Patron partagé : `simulation.verdict_fields`."""
    actions: list[ClassifiedAction] = []
    for entry in dict_entries(raw):
        country, classe_raw, resume = classified_entry(entry)
        actions.append(
            ClassifiedAction(country=country, classe=normalize_class(classe_raw), resume=resume)
        )
    return actions


def round_score(actions: list[ClassifiedAction], params: KahnParams | None = None) -> float:
    """Score du round = somme des poids des classes (grille de la spec G18)."""
    weights = _params(params).weights
    return float(sum(weights.get(a.classe, 0.0) for a in actions))


def score_to_escalation(score: float, params: KahnParams | None = None) -> float:
    """Mappe le score du barème sur l'escalade continue [0, 1] — pur, linéaire par morceaux.

    0 (statu quo) → 0,5 (le neutre historique du juge, rétro-compatible avec tous les
    réglages existants) ; `score_ceiling` → 1 (une frappe nucléaire sature l'échelle) ;
    `score_floor` → 0 (désescalade générale). Borné au-delà."""
    p = _params(params)
    if score >= 0:
        ceiling = max(p.score_ceiling, 1e-9)
        return _clamp(0.5 + 0.5 * min(score, ceiling) / ceiling)
    floor = min(p.score_floor, -1e-9)
    return _clamp(0.5 - 0.5 * min(score / floor, 1.0))


def score_to_rung(score: float, params: KahnParams | None = None) -> int:
    """Échelon 0-9 de l'échelle d'escalade existante pour un score du barème."""
    return reached_rung(score_to_escalation(score, params))


def reciprocal_deescalation(actions: list[ClassifiedAction]) -> bool:
    """Vrai si ≥ 2 SI distinctes ont désescaladé le même round (coordination vers le bas)."""
    countries = {a.country for a in actions if a.classe == CLASS_DEESCALADE and a.country}
    return len(countries) >= 2


def deescalation_bonus(
    prev_utopia: float, state: TrajectoryState, params: KahnParams | None = None
) -> TrajectoryState:
    """×1,5 sur le GAIN d'indice U du round quand la désescalade est réciproque — pur, borné.

    Le supplément passe par l'axe A1 (coordination, poids 1/5 dans U) via `nudge_axis` :
    l'invariant « U = moyenne des axes » est préservé et le pôle utopique n'est jamais
    dépassé. Sans gain (round perdant ou stable), l'état est rendu tel quel."""
    p = _params(params)
    gain = state.utopia - prev_utopia
    if gain <= 1e-12 or p.reciprocal_multiplier <= 1.0:
        return state
    extra = gain * (p.reciprocal_multiplier - 1.0)
    return nudge_axis(
        state,
        "A1",
        1.0,
        cap=extra * len(AXES),  # ΔA1 = 5×ΔU voulu (poids égaux 0,2)
        note=f"Désescalade réciproque — gain d'indice ×{p.reciprocal_multiplier:g}.",
    )


def rubric_text(params: KahnParams | None = None) -> str:
    """La grille en langage (classe, poids, exemples) — rubrique du prompt du juge."""
    weights = _params(params).weights
    return "\n".join(
        f"- {classe} ({weights.get(classe, 0.0):+g}) : {CLASS_EXAMPLES[classe]}"
        for classe in ACTION_CLASSES
    )
