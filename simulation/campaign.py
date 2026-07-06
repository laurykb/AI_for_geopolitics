"""G5 — la campagne « Ferez-vous mieux que l'Histoire ? ».

Une campagne = une suite ordonnée de crises rejouables ; chaque chapitre EST une partie
normale paramétrée (mode + crise imposés par la fiche, `data/campaign/campaign.json`).
Le score du chapitre = score Dérive (mode drift) ou trajectoire seule, **± bonus
historique** : finir moins escaladé que le déroulé réel paie, finir au-dessus coûte.
Déblocage linéaire. Le moteur ne change pas — tout est data-driven (`CAMPAIGN_PATH`
pour les tests d'équilibrage).
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field

DEFAULT_CAMPAIGN_PATH = Path("data/campaign/campaign.json")

SCENARIO_PREFIX = "campaign:"  # GameRecord.scenario = "campaign:<chapter_id>" (le lien)


class Chapter(BaseModel):
    id: str
    crisis_id: str
    title: str
    mode: str = "classic"
    difficulty: int = 1
    horizon: int = 4
    countries: list[str] = Field(default_factory=list)
    blurb: str = ""


class Campaign(BaseModel):
    title: str
    tagline: str = ""
    unlock_score: float = 50
    history_bonus_per_gap: float = 15
    history_malus: float = 10
    chapters: list[Chapter] = Field(default_factory=list)

    def chapter(self, chapter_id: str) -> Chapter | None:
        return next((c for c in self.chapters if c.id == chapter_id), None)


@lru_cache(maxsize=1)
def load_campaign(path: str | None = None) -> Campaign:
    """Charge la campagne (défaut `data/campaign/campaign.json`, `CAMPAIGN_PATH` sinon)."""
    target = Path(path or os.getenv("CAMPAIGN_PATH") or DEFAULT_CAMPAIGN_PATH)
    return Campaign.model_validate(json.loads(target.read_text(encoding="utf-8")))


def chapter_of(scenario: str) -> str | None:
    """L'id de chapitre porté par `GameRecord.scenario`, ou None (partie libre)."""
    return scenario.removeprefix(SCENARIO_PREFIX) if scenario.startswith(SCENARIO_PREFIX) else None


def history_bonus(improvement: float, campaign: Campaign | None = None) -> float:
    """Bonus/malus historique : `improvement` = escalade historique − escalade simulée
    (positif = le joueur a fini MOINS escaladé que l'Histoire — il a fait mieux)."""
    c = campaign or load_campaign()
    if improvement > 0:
        return round(c.history_bonus_per_gap * improvement, 1)
    if improvement < 0:
        return -c.history_malus
    return 0.0


def base_score(u_final: float, drift_total: float | None) -> float:
    """Score de chapitre avant bonus : score Dérive complet en mode drift, sinon la
    trajectoire seule, ramenée sur 0-100 (même ancrage que la Dérive : 0,15 → 0,85)."""
    if drift_total is not None:
        return drift_total
    span = 0.85 - 0.15
    return round(max(0.0, min(100.0, 100.0 * (u_final - 0.15) / span)), 1)


def unlocked_chapters(campaign: Campaign, best: dict[str, float]) -> dict[str, bool]:
    """Déblocage linéaire : le chapitre N s'ouvre quand le N−1 atteint `unlock_score`."""
    out: dict[str, bool] = {}
    open_next = True
    for chapter in campaign.chapters:
        out[chapter.id] = open_next
        open_next = open_next and best.get(chapter.id, 0.0) >= campaign.unlock_score
    return out
