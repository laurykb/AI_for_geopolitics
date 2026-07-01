"""Tests M6 — le compute est le nouveau pétrole (coût, parts, HHI, consommation)."""

import pytest

from core.country_state import CountryState, Economy, Military, Resources
from core.world_state import WorldState
from simulation.compute import (
    can_afford,
    compute_cost,
    compute_hhi,
    compute_shares,
    consume,
)


def _country(cid, compute=50.0):
    return CountryState(
        id=cid,
        name=cid.upper(),
        economy=Economy(gdp=1e12),
        military=Military(defense_budget=1e10),
        resources=Resources(),
        compute=compute,
    )


def _world(**computes):
    return WorldState.from_countries([_country(cid, c) for cid, c in computes.items()])


# --- coût -----------------------------------------------------------------

def test_compute_cost_scales_with_tokens():
    assert compute_cost(360) == pytest.approx(3.6)
    assert compute_cost(900) == pytest.approx(9.0)  # « Intense » coûte plus
    assert compute_cost(0) == 0.0
    assert compute_cost(-5) == 0.0  # robustesse


# --- parts & concentration -------------------------------------------------

def test_compute_shares_sum_to_one_and_proportional():
    shares = compute_shares(_world(usa=80.0, iran=20.0))
    assert sum(shares.values()) == pytest.approx(1.0)
    assert shares["usa"] == pytest.approx(0.8) and shares["iran"] == pytest.approx(0.2)


def test_compute_shares_uniform_when_no_stock():
    shares = compute_shares(_world(a=0.0, b=0.0))
    assert shares == {"a": 0.5, "b": 0.5}
    assert compute_shares(WorldState()) == {}


def test_compute_hhi_reflects_concentration():
    concentrated = compute_hhi(_world(big=95.0, s1=2.5, s2=2.5))
    spread = compute_hhi(_world(a=34.0, b=33.0, c=33.0))
    assert concentrated > spread
    assert spread == pytest.approx(1 / 3, abs=0.01)  # ~parts égales -> 1/N


# --- consommation ----------------------------------------------------------

def test_consume_depletes_bounded():
    c = _country("usa", compute=10.0)
    assert consume(c, 360) == pytest.approx(3.6)  # coût débité
    assert c.compute == pytest.approx(6.4)
    # on ne peut pas dépasser le stock : coût réel plafonné
    assert consume(c, 900) == pytest.approx(6.4)
    assert c.compute == 0.0


def test_can_afford():
    c = _country("usa", compute=3.0)
    assert can_afford(c, 240)  # 2.4 <= 3.0
    assert not can_afford(c, 360)  # 3.6 > 3.0


# --- intégration A3 : la concentration du compute réduit la distribution du pouvoir ---

def test_compute_concentration_lowers_power_distribution():
    from simulation.trajectory import capability_shares, hhi

    def world(computes):
        countries = []
        for cid, comp in computes.items():
            c = _country(cid, comp)
            # mêmes autres capacités partout -> seul le compute varie
            countries.append(c)
        return WorldState.from_countries(countries)

    spread = world({"a": 33.0, "b": 33.0, "c": 34.0})
    concentrated = world({"a": 96.0, "b": 2.0, "c": 2.0})
    # A3 = 1 − HHI(capability_shares) ; compute concentré -> HHI monte -> A3 baisse.
    hhi_conc = hhi(capability_shares(concentrated).values())
    hhi_spread = hhi(capability_shares(spread).values())
    assert hhi_conc > hhi_spread
