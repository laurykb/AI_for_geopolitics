"""XP — la carrière du joueur (G12 §2), distincte des LP (la compétence).

Tous les modes, ne baisse JAMAIS : récompense le temps joué, aller au bout, la victoire
du mode, la première partie du jour et les gains de marché (bornés). Les paramètres
vivent dans `data/gamefeel/params.json` (bloc `xp`, surchargeable par `GAMEFEEL_PARAMS_PATH`).
Niveaux à courbe douce, sans plafond. Logique PURE (aucun état de partie).
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field

_DEFAULT_PARAMS = Path(__file__).resolve().parent.parent / "data" / "gamefeel" / "params.json"


class XpParams(BaseModel):
    """Paramètres de la carrière (bloc `xp` de params.json ; défauts = spec §2)."""

    per_round: int = 10
    finished_bonus: int = 40  # partie terminée (pas abandonnée)
    victory_bonus: int = 30  # « victoire » du mode (§6)
    first_of_day_bonus: int = 20  # streak léger, jamais de malus
    market_divisor: int = 10  # gains nets de marché / 10…
    market_cap: int = 50  # …bornés à +50 (et jamais négatif)
    spectator_mult: float = 0.5
    difficulty_mult: dict[str, float] = Field(
        default_factory=lambda: {"beginner": 1.0, "intermediate": 1.2, "expert": 1.5}
    )
    level_base: int = 100  # coût du niveau 1
    level_step: int = 20  # +20 par niveau (niveau n coûte base + step×(n−1))


@lru_cache(maxsize=4)
def _load(path: str) -> XpParams:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return XpParams.model_validate(data.get("xp", {}))


def load_xp_params() -> XpParams:
    """Paramètres XP (surchargeables par `GAMEFEEL_PARAMS_PATH` pour les tests)."""
    return _load(os.getenv("GAMEFEEL_PARAMS_PATH", str(_DEFAULT_PARAMS)))


def xp_gain(
    *,
    rounds: int,
    finished: bool,
    victory: bool,
    first_of_day: bool,
    market_net: float,
    difficulty: str,
    spectator: bool,
    params: XpParams | None = None,
) -> int:
    """XP gagnés en fin de partie (§2) — toujours ≥ 0 (la carrière ne baisse jamais)."""
    p = params or load_xp_params()
    base = p.per_round * max(0, rounds)
    if finished:
        base += p.finished_bonus
    if victory:
        base += p.victory_bonus
    if first_of_day:
        base += p.first_of_day_bonus
    base += max(0.0, min(float(p.market_cap), market_net / p.market_divisor))
    mult = p.difficulty_mult.get(difficulty, 1.0)
    if spectator:
        mult *= p.spectator_mult
    return max(0, round(base * mult))


class LevelProgress(BaseModel):
    """Niveau atteint par un total d'XP + progression vers le suivant (sans plafond)."""

    level: int
    into_level: int  # XP acquis dans le niveau courant
    span: int  # XP entre ce niveau et le suivant
    to_next: int  # XP restants avant le niveau suivant
    progress: float  # 0..1 vers le niveau suivant


def _level_cost(level: int, params: XpParams) -> int:
    """Coût pour passer DU niveau `level` au suivant : base + step×(level−1)."""
    return params.level_base + params.level_step * (level - 1)


def level_for(xp: int, params: XpParams | None = None) -> LevelProgress:
    """Niveau (≥ 1) atteint par un total d'XP cumulé, et la progression vers le suivant."""
    p = params or load_xp_params()
    remaining = max(0, int(xp))
    level = 1
    while remaining >= _level_cost(level, p):
        remaining -= _level_cost(level, p)
        level += 1
    span = _level_cost(level, p)
    return LevelProgress(
        level=level,
        into_level=remaining,
        span=span,
        to_next=span - remaining,
        progress=remaining / span,
    )
