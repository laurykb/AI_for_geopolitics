"""Score MIXTE de fin de partie (RG-3) — le cœur du jeu chiffré, PUR et testé.

La note finale mélange DEUX choses (docs/JEU_VS_MOTEUR.md §1), chacune racontée
simplement au joueur :

1. **L'état du monde** — l'indice U final (le monde a-t-il fini bien ?). Ancré comme le
   reste du jeu : 0,15 (effondrement) → 0 point, 0,85 (monde rêvé) → `world_max`.
2. **La détection** — as-tu suspendu le(s) bon(s) traître(s), *sans accuser d'innocent* ?
   - Bonne suspension = points (répartis sur le nombre réel de traîtres).
   - **Faux positif = coût** : suspendre un pays loyal érode la détection gagnée. Sans ce
     coût, la stratégie optimale serait « suspends tout le monde » — le faux positif est
     ce qui rend la déduction nécessaire.
   - Traître raté (caught < deviants) = manque à gagner (et il a plombé le monde via U).

Un rôle qui NE joue PAS la détection (Spectateur, Architecte) n'est pas puni d'un faux
« 0 détection » : sa note se réduit à l'état du monde, ramené sur 100.

Tout est PUR : `mixed_score(...)` ne lit aucun fichier, ne mute rien. Les pondérations
(constantes de calibrage Cowork) vivent dans `ScoreWeights`, chargeables depuis
`data/score/params.json` (`SCORE_PARAMS_PATH` pour les tests) — défauts raisonnables si
absent.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field

DEFAULT_PARAMS_PATH = Path("data/score/params.json")


class Grade(BaseModel):
    min: float
    label: str


def _default_grades() -> list[Grade]:
    return [
        Grade(min=85, label="Grand Diplomate"),
        Grade(min=70, label="Stratège"),
        Grade(min=50, label="Conseiller"),
        Grade(min=0, label="Dépassé par les événements"),
    ]


class ScoreWeights(BaseModel):
    """Pondérations du score mixte — calibrées par Cowork après playtest.

    `world_max + detection_max` vaut 100 : la note tient sur 0-100 sans surprise.
    """

    world_max: float = 60.0  # part de l'état du monde
    detection_max: float = 40.0  # part de la détection
    false_positive_penalty: float = 15.0  # coût d'un pays loyal suspendu à tort
    collapse_u: float = 0.15  # U d'effondrement → 0 point de monde
    utopia_u: float = 0.85  # U « monde rêvé » → world_max
    grades: list[Grade] = Field(default_factory=_default_grades)


@lru_cache(maxsize=1)
def load_weights(path: str | None = None) -> ScoreWeights:
    """Charge les pondérations (`data/score/params.json`, `SCORE_PARAMS_PATH` sinon).
    Fichier absent → défauts (le score marche sans calibrage)."""
    target = Path(path or os.getenv("SCORE_PARAMS_PATH") or DEFAULT_PARAMS_PATH)
    if not target.exists():
        return ScoreWeights()
    return ScoreWeights.model_validate(json.loads(target.read_text(encoding="utf-8")))


class MixedScore(BaseModel):
    """La note de fin + ses deux composantes (le détail vit dans Informations)."""

    world: float  # 0..world_max
    detection: float | None  # 0..detection_max ; None si le rôle ne détecte pas
    total: float  # 0..100 — LA note globale
    grade: str
    # Ce que la révélation « raconte » en deux phrases (nombre caché révélé).
    deviants: int  # combien de traîtres il y avait vraiment (1 ou 2)
    caught: int  # combien tu en as démasqués
    false_positives: int  # combien de pays loyaux tu as suspendus à tort
    detects: bool  # ce rôle joue-t-il la détection (player/council) ?


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _world_fraction(u_final: float, weights: ScoreWeights) -> float:
    """Part de monde dans [0,1] : U ramené sur [collapse_u, utopia_u]."""
    span = weights.utopia_u - weights.collapse_u
    if span <= 0:
        return 0.0
    return _clamp((u_final - weights.collapse_u) / span, 0.0, 1.0)


def _grade_for(total: float, weights: ScoreWeights) -> str:
    return next(
        (g.label for g in sorted(weights.grades, key=lambda g: -g.min) if total >= g.min),
        "Dépassé par les événements",
    )


def mixed_score(
    *,
    u_final: float,
    deviants: int,
    caught: int,
    false_positives: int,
    detects: bool = True,
    weights: ScoreWeights | None = None,
) -> MixedScore:
    """La note mixte 0-100 : monde (indice U final) + détection (bonnes suspensions moins
    les faux positifs). Voir le docstring du module pour la sémantique de chaque cas.

    `deviants` = nombre RÉEL de traîtres (seedé, révélé en fin) ; `caught` = combien de ces
    traîtres ont été suspendus (borné à `deviants`) ; `false_positives` = pays loyaux
    suspendus à tort. `detects=False` (Spectateur/Architecte) → note = monde seul sur 100.
    """
    w = weights or ScoreWeights()
    deviants = max(0, deviants)
    caught = int(_clamp(caught, 0, deviants))
    false_positives = max(0, false_positives)

    world_frac = _world_fraction(u_final, w)
    world = w.world_max * world_frac

    if not detects:
        # Le rôle ne joue pas la détection : la note EST l'état du monde, sur 100.
        total = round(100.0 * world_frac, 1)
        return MixedScore(
            world=round(world, 1),
            detection=None,
            total=total,
            grade=_grade_for(total, w),
            deviants=deviants,
            caught=caught,
            false_positives=false_positives,
            detects=False,
        )

    per_deviant = w.detection_max / deviants if deviants > 0 else 0.0
    detection = _clamp(
        caught * per_deviant - w.false_positive_penalty * false_positives,
        0.0,
        w.detection_max,
    )
    total = round(world + detection, 1)
    return MixedScore(
        world=round(world, 1),
        detection=round(detection, 1),
        total=total,
        grade=_grade_for(total, w),
        deviants=deviants,
        caught=caught,
        false_positives=false_positives,
        detects=True,
    )
