"""Tests de l'Escalation Ladder : profil dérivé + plafond atteignable (déterministe)."""

from core.country_state import CountryState, Economy, Military, Resources
from core.events import GeoEvent
from core.world_state import WorldState
from simulation.escalation import (
    LADDER,
    MAX_RUNG,
    ceiling,
    derive_profile,
    reached_rung,
    rung_label,
)


def _country(cid, **kw):
    return CountryState(
        id=cid,
        name=cid.upper(),
        economy=Economy(
            gdp=1e12, growth=2.0, trade_dependency=kw.pop("trade", 0.5)
        ),
        military=Military(
            defense_budget=1e10,
            projection=kw.pop("proj", 0.6),
            nuclear_power=kw.pop("nuke", False),
        ),
        resources=Resources(
            oil_dependency=kw.pop("oil", 0.5), energy_independence=kw.pop("energy", 0.5)
        ),
        political_stability=kw.pop("stab", 0.6),
        **kw,
    )


def _hawk():
    return _country(
        "hawk", proj=0.95, nuke=True, rivals=["dove"], stab=0.7,
        alliances=["A", "B"], trade=0.2, oil=0.1, energy=0.95,
    )


def _dove():
    return _country(
        "dove", proj=0.3, nuke=False, stab=0.4, trade=0.9, oil=0.85, energy=0.2
    )


def _world():
    return WorldState.from_countries([_hawk(), _dove()])


def _event(actors, severity=0.6):
    return GeoEvent(id="e1", round_id=1, event_type="incident", title="Crise", actors=actors,
                    severity=severity)


def test_ladder_has_ten_rungs():
    assert len(LADDER) == 10 and MAX_RUNG == 9
    assert rung_label(0) == "Observation"
    assert rung_label(9) == "Conflit ouvert"
    assert rung_label(99) == "Conflit ouvert"  # borné


def test_reached_rung_maps_escalation():
    assert reached_rung(0.0) == 0
    assert reached_rung(1.0) == 9
    assert 0 <= reached_rung(0.55) <= 9


def test_profile_params_in_range():
    p = derive_profile(_hawk())
    for v in (p.escalation_threshold, p.risk_tolerance, p.alliance_pressure,
              p.domestic_pressure, p.economic_exposure):
        assert 0.0 <= v <= 1.0


def test_ceiling_in_range():
    world = _world()
    c = ceiling(derive_profile(_hawk()), _event(["hawk"]), world, world.countries["hawk"])
    assert 0 <= c <= 9


def test_hawk_climbs_higher_than_dove():
    world = _world()
    event = _event(["hawk", "dove"])
    hawk_c = ceiling(derive_profile(world.countries["hawk"]), event, world, world.countries["hawk"])
    dove_c = ceiling(derive_profile(world.countries["dove"]), event, world, world.countries["dove"])
    assert hawk_c > dove_c  # puissance assertive/nucléaire vs pays exposé et prudent


def test_actor_ceiling_at_least_bystander():
    world = _world()
    hawk = world.countries["hawk"]
    profile = derive_profile(hawk)
    as_actor = ceiling(profile, _event(["hawk"]), world, hawk)
    as_bystander = ceiling(profile, _event(["dove"]), world, hawk)
    assert as_actor >= as_bystander  # impliqué -> peut monter au moins aussi haut


def test_economic_exposure_brakes_ceiling():
    world = _world()
    hawk = world.countries["hawk"]
    event = _event(["hawk"])
    base = ceiling(derive_profile(hawk), event, world, hawk)
    hawk.mandate = {"economic_exposure": "1.0"}  # forte exposition -> frein
    braked = ceiling(derive_profile(hawk), event, world, hawk)
    assert braked <= base


def test_profile_override_via_mandate():
    hawk = _hawk()
    hawk.mandate = {"escalation_threshold": "0.1"}
    assert derive_profile(hawk).escalation_threshold == 0.1  # surcharge l'emporte
