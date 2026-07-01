"""Tests de l'horloge de simulation."""

from datetime import date

from simulation.clock import SimClock, add_months


def test_add_months_basic_and_year_rollover():
    assert add_months(date(2025, 1, 1), 6) == date(2025, 7, 1)
    assert add_months(date(2025, 10, 15), 6) == date(2026, 4, 15)


def test_add_months_clamps_day_to_month_end():
    # 31 août + 6 mois -> février (28 en 2026, non bissextile)
    assert add_months(date(2025, 8, 31), 6) == date(2026, 2, 28)


def test_advance_default_six_months():
    clock = SimClock(current_date=date(2025, 1, 1))
    assert clock.advance() == date(2025, 7, 1)
    assert clock.advance() == date(2026, 1, 1)
    assert clock.iso == "2026-01-01"


def test_jitter_is_bounded_and_deterministic():
    clock = SimClock(current_date=date(2025, 1, 1), base_months=6, jitter_months=3, seed=42)
    prev = clock.current_date
    for _ in range(20):
        new = clock.advance()
        # écart en mois ∈ [3, 9] (6 ± 3), et strictement croissant
        months = (new.year - prev.year) * 12 + (new.month - prev.month)
        assert 3 <= months <= 9
        prev = new
