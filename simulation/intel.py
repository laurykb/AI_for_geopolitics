"""G4 — le fog comme ressource : l'économie du renseignement du conseil.

Trois actions achetées sur un budget de crédits : le **brief classifié** (RAG sourcé,
dissipe le brouillard du joueur au prochain round de fog), la **vérification** d'une
affirmation d'une SI (l'arme anti-manipulateur de la Dérive), la **désinformation**
(injecter une fausse perception chez un rival — une fois par partie, avec un risque
d'être dénoncé). Fonctions pures + état sérialisable (`IntelState` vit dans le snapshot
de session). Paramètres chiffrés : `data/intel/params.json` (`INTEL_PARAMS_PATH` pour
les tests d'équilibrage).
"""

from __future__ import annotations

import json
import os
import random
import re
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field

from core.events import GeoEvent
from simulation.fog import FogScenario

DEFAULT_PARAMS_PATH = Path("data/intel/params.json")

ACTION_BRIEF = "brief"
ACTION_VERIFY = "verify"
ACTION_DISINFO = "disinfo"


class IntelParams(BaseModel):
    budget: float = 100
    costs: dict[str, float] = Field(
        default_factory=lambda: {ACTION_BRIEF: 25, ACTION_VERIFY: 15, ACTION_DISINFO: 60}
    )
    disinfo_expose_prob: float = 0.3
    disinfo_expose_tension: float = 0.1
    save_bonus_per_10: float = 2


@lru_cache(maxsize=1)
def load_params(path: str | None = None) -> IntelParams:
    """Charge les paramètres (défaut `data/intel/params.json`, `INTEL_PARAMS_PATH` sinon)."""
    target = Path(path or os.getenv("INTEL_PARAMS_PATH") or DEFAULT_PARAMS_PATH)
    return IntelParams.model_validate(json.loads(target.read_text(encoding="utf-8")))


class IntelState(BaseModel):
    """L'état de renseignement d'une partie — sérialisé dans le snapshot de session."""

    budget: float
    disinfo_used: bool = False
    clear_fog: bool = False  # un brief a été acheté : le prochain fog est dissipé (joueur)
    pending_disinfo: dict | None = None  # fausse perception à injecter au prochain round
    log: list[dict] = Field(default_factory=list)  # achats à consigner au prochain round

    @classmethod
    def fresh(cls, params: IntelParams | None = None) -> IntelState:
        return cls(budget=(params or load_params()).budget)


def save_bonus(budget_left: float, params: IntelParams | None = None) -> float:
    """La retenue paie : +N points de score par tranche de 10 crédits non dépensés."""
    p = params or load_params()
    return p.save_bonus_per_10 * int(max(0.0, budget_left) // 10)


# --- vérification d'une affirmation (déterministe, testable hors LLM) ------------------

_WORD = re.compile(r"[a-zà-ÿ]{4,}", re.IGNORECASE)

VERDICT_CORROBORATED = "corroboré"
VERDICT_NOT_CORROBORATED = "non corroboré"
VERDICT_UNVERIFIABLE = "invérifiable"


def verify_claim(
    claim: str,
    *,
    speaker_suspicious: bool,
    top_chunk_text: str = "",
    top_citation: str = "",
) -> tuple[str, str]:
    """(verdict, source) — le juge répond en une ligne.

    Un orateur pris en dérive au dossier (acte constatable à son actif) rend son
    affirmation **non corroborée** — l'arme anti-manipulateur. Sinon : corroborée si le
    corpus la recoupe lexicalement (source citée), invérifiable autrement."""
    if speaker_suspicious:
        return VERDICT_NOT_CORROBORATED, ""
    words = {w.lower() for w in _WORD.findall(claim)}
    chunk_words = {w.lower() for w in _WORD.findall(top_chunk_text)}
    if top_chunk_text and len(words & chunk_words) >= 2:
        return VERDICT_CORROBORATED, top_citation
    return VERDICT_UNVERIFIABLE, ""


# --- désinformation ---------------------------------------------------------------------


def disinfo_scenario(spec: dict, game_id: str, round_no: int) -> FogScenario:
    """La fausse perception injectée chez UN rival (même patron que le fog humain R4).

    `true_event` est un tenant-lieu : la désinformation ne fournit PAS l'événement du
    round (le GM le pose normalement), elle ne fait que brouiller une perception."""
    return FogScenario(
        id=f"intel-disinfo-{game_id}-{round_no}",
        title="Opération de désinformation du conseil",
        true_event=GeoEvent(
            id=f"disinfo-{round_no}",
            round_id=round_no,
            event_type="disinfo",
            title="(placeholder — jamais joué)",
            actors=[],
            severity=0.0,
            uncertainty=1.0,
        ),
        perceptions={
            spec["disinformed_country"]: {
                "suspected_actor": spec.get("suspected_actor", ""),
                "confidence": 0.7,
                "narrative": spec.get("narrative", ""),
            }
        },
        uninformed=[],
    )


def disinfo_exposed(game_id: str, round_no: int, params: IntelParams | None = None) -> bool:
    """Les SI saines peuvent percer la manœuvre (tirage seedé : rejouable au replay)."""
    p = params or load_params()
    return random.Random(f"intel:{game_id}:{round_no}").random() < p.disinfo_expose_prob
