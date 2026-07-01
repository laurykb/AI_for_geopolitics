"""Horloge de simulation : chaque round fait avancer le temps (~6 mois par défaut).

Permet une timeline réaliste : chaque round correspond à une date, éventuellement
avec un pas aléatoire (jitter). Déterministe si `seed` est fourni.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date

_DAYS_IN_MONTH = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


def _is_leap(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def add_months(start: date, months: int) -> date:
    """Ajoute `months` mois à une date, en bornant le jour à la fin de mois."""
    index = start.month - 1 + months
    year = start.year + index // 12
    month = index % 12 + 1
    max_day = 29 if (month == 2 and _is_leap(year)) else _DAYS_IN_MONTH[month - 1]
    return date(year, month, min(start.day, max_day))


@dataclass
class SimClock:
    """Avance la date de la simulation round après round."""

    current_date: date = field(default_factory=lambda: date(2025, 1, 1))
    base_months: int = 6
    jitter_months: int = 0
    seed: int | None = None

    def __post_init__(self) -> None:
        self._rng = random.Random(self.seed)

    def advance(self) -> date:
        """Avance d'~`base_months` (± jitter), au moins 1 mois. Renvoie la nouvelle date."""
        step = self.base_months
        if self.jitter_months:
            step += self._rng.randint(-self.jitter_months, self.jitter_months)
        self.current_date = add_months(self.current_date, max(1, step))
        return self.current_date

    @property
    def iso(self) -> str:
        return self.current_date.isoformat()
