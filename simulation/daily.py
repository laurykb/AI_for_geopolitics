"""G16 — le Défi du jour (« Le Sommet du jour »), pur et dérivé de la date UTC.

Le levier de rétention le mieux documenté des jeux à session courte (effet Wordle) :
le MÊME sommet pour tout le monde chaque jour — même crise (du pool des fiches
prêtes), mêmes 7 pays, même pays incarné, même horizon court — dérivé DÉTERMINISTE
de la date (`random.Random("daily:<date>")`, même discipline que la Dérive) : aucun
contenu neuf à produire, et deux joueurs du même jour comparent le même exercice.

Le chapitre 0 (tutoriel) est exclu du pool ; les crises maison aussi (le défi ne se
joue que sur des fiches embarquées, identiques pour tous les déploiements).
"""

from __future__ import annotations

import random
from datetime import UTC, datetime

from pydantic import BaseModel

from simulation.crisis import Crisis

DATE_PREFIX = "daily:"
HORIZON = 4  # sommet court : la session tient dans la pause café
SUMMIT_SIZE = 7
TUTORIAL_CRISIS = "sommet_inaugural"  # le chapitre 0 n'est pas un défi


class DailyChallenge(BaseModel):
    """Le défi d'une date : reproductible partout, comparable entre joueurs."""

    date: str
    crisis_id: str
    countries: list[str]
    play_as: str
    horizon: int = HORIZON


def today_utc() -> str:
    """La date du défi — minuit UTC fait tourner le sommet, pour tout le monde."""
    return datetime.now(UTC).date().isoformat()


def date_of(scenario: str) -> str | None:
    """La date portée par `GameRecord.scenario` (`daily:<date>`), ou None."""
    return scenario.removeprefix(DATE_PREFIX) if scenario.startswith(DATE_PREFIX) else None


def challenge_for(date: str, crises: list[Crisis], roster: list[str]) -> DailyChallenge:
    """Le défi d'une date : hash date → crise du pool + rotation des pays.

    Les acteurs de la crise siègent toujours (sinon le round tourne à vide) ; le
    reste de la table et le pays incarné tournent avec la date."""
    pool = sorted(c.id for c in crises if c.events and c.id != TUTORIAL_CRISIS)
    if not pool:
        raise ValueError("aucune crise jouable pour le défi du jour")
    rng = random.Random(f"daily:{date}")
    crisis_id = rng.choice(pool)  # tiré UNE fois (pas dans le générateur !)
    crisis = next(c for c in crises if c.id == crisis_id)
    actors = sorted({a for e in crisis.events for a in e.actors if a in roster})
    rest = [c for c in sorted(roster) if c not in actors]
    rng.shuffle(rest)
    countries = sorted([*actors, *rest[: max(0, SUMMIT_SIZE - len(actors))]])
    return DailyChallenge(
        date=date,
        crisis_id=crisis.id,
        countries=countries,
        play_as=rng.choice(countries),
    )
