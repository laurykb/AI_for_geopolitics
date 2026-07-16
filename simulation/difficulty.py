"""Table de difficulté (G11-d §4) — leviers d'économie et de moteur, jamais de modèle.

Chaque niveau (Débutant / Intermédiaire / Expert) fixe des leviers : brief gratuit,
budget de renseignement, seuil d'actes du juge, vitesse de dérive k, contexte donné
aux SI, amplitude des deltas. Les valeurs vivent dans
`data/gamefeel/params.json` (bloc `difficulty`, surchargeable par
`GAMEFEEL_PARAMS_PATH`) par-dessus les défauts canoniques ci-dessous : Cowork équilibre
sans code. Les helpers dérivent les params drift (k, seuil) et gamefeel (amplitude).

CC-15c : les anciens drapeaux `show_postures`/`show_griefs` (visibilité d'observables
par niveau) ont été RETIRÉS — jamais appliqués côté serveur, et l'audit de simplicité
a inversé la logique : la difficulté ne cache plus d'information, elle règle la
DENSITÉ d'affichage, côté front (`web/src/lib/density.ts`).
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel

from simulation import drift_game
from simulation.grudges import DeltaParams, load_gamefeel_params

_DEFAULT_PARAMS = Path(__file__).resolve().parent.parent / "data" / "gamefeel" / "params.json"


class DifficultyParams(BaseModel):
    """Les leviers d'un niveau (§4). Toutes les valeurs sont des données, pas du code."""

    free_brief: int = 0  # briefs de renseignement offerts par round
    intel_budget: float = 100  # crédits de renseignement (G4)
    judge_min_acts: int = 2  # seuil d'actes pour qu'une motion soit retenue (Dérive)
    drift_k: float = 0.12  # vitesse de dérive (G3)
    si_context: str = "normal"  # reduced | normal | full (résumé des actions du joueur)
    amplitude: float = 0.5  # amplitude des deltas par partie (G9 §4)


# Défauts canoniques = spec §4 (params.json les surcharge par niveau).
_DEFAULTS: dict[str, dict] = {
    "beginner": {
        "free_brief": 1,
        "intel_budget": 150,
        "judge_min_acts": 2,
        "drift_k": 0.09,
        "si_context": "reduced",
        "amplitude": 0.4,
    },
    "intermediate": {
        "free_brief": 0,
        "intel_budget": 100,
        "judge_min_acts": 2,
        "drift_k": 0.12,
        "si_context": "normal",
        "amplitude": 0.5,
    },
    "expert": {
        "free_brief": 0,
        "intel_budget": 60,
        "judge_min_acts": 3,
        "drift_k": 0.16,
        "si_context": "full",
        "amplitude": 0.6,
    },
}


@lru_cache(maxsize=4)
def _overrides(path: str) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data.get("difficulty", {})


def load_difficulty(level: str) -> DifficultyParams:
    """Leviers d'un niveau (défaut Intermédiaire si le niveau est inconnu)."""
    key = level if level in _DEFAULTS else "intermediate"
    overrides = _overrides(os.getenv("GAMEFEEL_PARAMS_PATH", str(_DEFAULT_PARAMS)))
    merged = {**_DEFAULTS[key], **overrides.get(key, {})}
    return DifficultyParams.model_validate(merged)


def drift_params(level: str) -> drift_game.DriftParams:
    """Params drift du niveau : vitesse k et seuil d'actes du juge (§4). Le seuil est
    `open_acts` — la porte « preuves » d'une motion (`evidence_met`), câblée dans le round.
    `model_copy` imbriqué : les défauts drift `lru_cache`d ne sont JAMAIS mutés."""
    d = load_difficulty(level)
    base = drift_game.load_params()
    return base.model_copy(
        update={
            "k": d.drift_k,
            "judge": base.judge.model_copy(update={"open_acts": d.judge_min_acts}),
        }
    )


def delta_params(level: str) -> DeltaParams:
    """Params d'amplitude gamefeel du niveau (le reste = défauts gamefeel)."""
    d = load_difficulty(level)
    base = load_gamefeel_params().deltas
    return base.model_copy(update={"amplitude_total": d.amplitude})
