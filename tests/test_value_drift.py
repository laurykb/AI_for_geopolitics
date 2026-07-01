"""Tests M3 — dérive des valeurs (vecteur latent, renforcement borné, divergence)."""

import pytest

from core.country_state import CountryState, Economy, Military, Resources
from simulation.value_drift import (
    DRIFT_CAP,
    VALUE_DIMS,
    ValueVector,
    divergence,
    drift,
    initial_values,
)


def _country(cid, **kw):
    return CountryState(
        id=cid,
        name=cid.upper(),
        economy=Economy(gdp=1e12),
        military=Military(defense_budget=1e10),
        resources=Resources(),
        **kw,
    )


# --- valeurs initiales -----------------------------------------------------

def test_initial_values_reflect_country():
    coop = _country(
        "a", alliances=["X", "Y"], political_stability=0.9, political_system="democracy"
    )
    lone = _country("b", rivals=["a", "c"], political_stability=0.2, political_system="autocracy")
    vi, vl = initial_values(coop), initial_values(lone)
    assert vi.cooperation > vl.cooperation  # allié vs rival isolé
    assert vi.restraint > vl.restraint  # stable -> plus de retenue
    assert vi.transparency > vl.transparency  # démocratie -> plus ouverte
    for v in (vi, vl):
        assert all(0.0 <= x <= 1.0 for x in v.as_dict().values())


# --- dérive bornée ---------------------------------------------------------

def test_drift_is_bounded_by_cap():
    current = ValueVector(cooperation=0.5, restraint=0.5, transparency=0.5)
    pushed = drift(current, ValueVector(cooperation=1.0, restraint=0.0, transparency=1.0))
    assert pushed.cooperation == pytest.approx(0.5 + DRIFT_CAP)  # plafonné
    assert pushed.restraint == pytest.approx(0.5 - DRIFT_CAP)
    assert 0.0 <= pushed.transparency <= 1.0


def test_drift_stays_when_at_target():
    v = ValueVector(cooperation=0.6, restraint=0.6, transparency=0.6)
    assert drift(v, v).as_dict() == pytest.approx(v.as_dict())


# --- divergence ------------------------------------------------------------

def test_divergence_zero_when_identical():
    v = ValueVector(cooperation=0.7, restraint=0.3, transparency=0.5)
    assert divergence(v, v) == 0.0


def test_divergence_grows_as_values_drift():
    initial = ValueVector(cooperation=0.8, restraint=0.8, transparency=0.8)
    target = ValueVector(cooperation=0.0, restraint=0.0, transparency=0.0)  # monde hostile
    current = initial
    seen = [divergence(initial, current)]
    for _ in range(5):
        current = drift(current, target)
        seen.append(divergence(initial, current))
    assert seen[-1] > seen[0]  # les valeurs s'éloignent du mandat initial
    pairs = zip(seen[:-1], seen[1:], strict=True)
    assert all(b >= a - 1e-9 for a, b in pairs)  # monotone
    assert 0.0 <= seen[-1] <= 1.0


def test_value_dims_are_three():
    assert VALUE_DIMS == ("cooperation", "restraint", "transparency")
