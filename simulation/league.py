"""Points de ligue (G11-c §2) — la formule LP, le plancher, le forfait, les rangs.

Logique PURE : aucune dépendance à l'état de partie. La couche API (fin de partie)
appelle `lp_delta` (gain/perte du monde + du pays), `country_progress` (le P du joueur)
et `apply_delta` (plancher 0 + plafond Débutant). Les paramètres chiffrés vivent dans
`data/gamefeel/params.json` sous la clé `lp` (surchargeable par `GAMEFEEL_PARAMS_PATH`) :
Cowork équilibre sans toucher au code.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field

# Les 4 indices 0-1 du pays du joueur qui pèsent dans P (§2).
INDEX_KEYS = ("stability", "economy", "technology", "energy")

# Rangs (seuils LP, §2), croissants. Miroir de web/src/lib/league.ts.
RANKS: tuple[tuple[str, int], ...] = (
    ("Attaché", 0),
    ("Émissaire", 100),
    ("Diplomate", 250),
    ("Ambassadeur", 450),
    ("Ministre", 700),
    ("Chancelier", 1000),
    ("Éminence", 1400),
)

# Forfait d'une partie classée abandonnée (§2) — exposé comme constante lisible.
FORFEIT_LP = -15

# Plafond du mode Débutant = juste SOUS Ambassadeur (anti-farm §2). DÉRIVÉ des rangs :
# si les seuils sont retunés, le plafond suit au lieu de désync silencieusement.
BEGINNER_CEILING = dict(RANKS)["Ambassadeur"] - 1

_DEFAULT_PARAMS = Path(__file__).resolve().parent.parent / "data" / "gamefeel" / "params.json"


class LpParams(BaseModel):
    """Paramètres de la formule LP (bloc `lp` de params.json ; défauts = spec §2)."""

    k: float = 100.0
    w_world: float = 0.6  # poids de la trajectoire du monde (ΔU)
    w_country: float = 0.4  # poids de la progression du pays (P)
    multipliers: dict[str, float] = Field(
        default_factory=lambda: {"beginner": 0.5, "intermediate": 1.0, "expert": 1.5}
    )
    forfeit: int = FORFEIT_LP
    p_bound: float = 0.5  # borne de P (§2 : [−0.5, +0.5])
    # Plafond du mode Débutant : un gain ne fait pas passer au-dessus de Diplomate
    # (= juste sous Ambassadeur, anti-farm §2). Dérivé des rangs (BEGINNER_CEILING).
    beginner_ceiling: int = BEGINNER_CEILING


@lru_cache(maxsize=4)
def _load(path: str) -> LpParams:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return LpParams.model_validate(data.get("lp", {}))


def load_lp_params() -> LpParams:
    """Paramètres LP (surchargeables par `GAMEFEEL_PARAMS_PATH` pour les tests)."""
    return _load(os.getenv("GAMEFEEL_PARAMS_PATH", str(_DEFAULT_PARAMS)))


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def lp_delta(
    u_start: float,
    u_final: float,
    p: float,
    difficulty: str,
    params: LpParams | None = None,
) -> int:
    """LP gagnés (ou perdus) sur une partie classée (§2), arrondis à l'entier.

    `LP = round(K × [w_monde × ΔU + w_pays × P] × M_difficulté)` — P borné à [−0.5, +0.5],
    négatif possible (le monde/le pays peut finir pire)."""
    prm = params or load_lp_params()
    p_bounded = _clamp(p, -prm.p_bound, prm.p_bound)
    m = prm.multipliers.get(difficulty, 1.0)
    raw = prm.k * (prm.w_world * (u_final - u_start) + prm.w_country * p_bounded) * m
    return round(raw)


def country_progress(
    before: dict[str, float],
    after: dict[str, float],
    params: LpParams | None = None,
) -> float:
    """P = moyenne des variations RELATIVES des 4 indices 0-1 du pays, bornée [−0.5, +0.5].

    Un indice parti de ~0 ne fait pas exploser P (la borne absorbe les cas extrêmes)."""
    prm = params or load_lp_params()
    rels: list[float] = []
    for key in INDEX_KEYS:
        b, a = before.get(key, 0.0), after.get(key, 0.0)
        rels.append((a - b) / b if b > 1e-9 else (a - b))
    mean = sum(rels) / len(rels)
    return round(_clamp(mean, -prm.p_bound, prm.p_bound), 6)


def apply_delta(current: int, delta: int, difficulty: str, params: LpParams | None = None) -> int:
    """Applique un delta au total LP : plancher 0, plafond Diplomate en Débutant (§2).

    Le plafond ne rogne QUE les gains (une perte s'applique toujours) et ne rabaisse
    jamais un total déjà au-dessus (acquis en Intermédiaire/Expert)."""
    prm = params or load_lp_params()
    if difficulty == "beginner" and delta > 0:
        delta = max(0, min(delta, prm.beginner_ceiling - current))
    return max(0, current + delta)


def rank_for(lp: int) -> tuple[str, int]:
    """Rang (nom, seuil) atteint par un total de LP."""
    total = max(0, int(lp))
    current = RANKS[0]
    for rank in RANKS:
        if total >= rank[1]:
            current = rank
    return current
