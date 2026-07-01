"""Tests de la fiche de comportement (mandat) dérivée + surcharge hybride."""

from core.country_state import CountryState, Economy, Military, Resources
from core.events import GeoEvent
from core.world_state import WorldState
from simulation.mandate import derive_mandate


def _c(cid, name, **kw):
    return CountryState(
        id=cid,
        name=name,
        economy=Economy(gdp=1e12, growth=2.0, trade_dependency=kw.pop("trade", 0.5)),
        military=Military(defense_budget=1e10, projection=kw.pop("proj", 0.6)),
        resources=Resources(),
        political_stability=kw.pop("stab", 0.5),
        **kw,
    )


def _world():
    return WorldState.from_countries(
        [_c("usa", "USA", rivals=["iran"]), _c("iran", "Iran"), _c("france", "France")]
    )


def _event(actors, severity=0.6):
    return GeoEvent(id="e1", round_id=1, event_type="incident", title="Crise", actors=actors,
                    severity=severity)


def test_mandate_fills_all_fields():
    world = _world()
    m = derive_mandate(world.countries["usa"], _event(["usa"]), world)
    assert m.red_line and m.concessions and m.domestic_constraints
    assert m.priorities  # non vide
    assert m.urgency in {"faible", "moyenne", "élevée"}


def test_urgency_high_for_actor_low_for_bystander():
    world = _world()
    actor = derive_mandate(world.countries["usa"], _event(["usa"], severity=0.3), world)
    bystander = derive_mandate(world.countries["france"], _event(["usa"], severity=0.2), world)
    assert actor.urgency == "élevée"
    assert bystander.urgency != "élevée"


def test_red_line_targets_rival():
    world = _world()
    m = derive_mandate(world.countries["usa"], _event(["iran"]), world)
    assert "iran" in m.red_line  # ligne rouge orientée vers le rival


def test_mandate_override_wins():
    world = _world()
    usa = world.countries["usa"]
    usa.mandate = {"red_line": "SURCHARGE_TEST", "urgency": "faible", "priorities": "a, b"}
    m = derive_mandate(usa, _event(["usa"]), world)
    assert m.red_line == "SURCHARGE_TEST"
    assert m.urgency == "faible"  # surcharge l'emporte même si le pays est acteur
    assert m.priorities == ["a", "b"]


def test_mandate_is_deterministic():
    world = _world()
    e = _event(["usa"])
    assert derive_mandate(world.countries["usa"], e, world) == derive_mandate(
        world.countries["usa"], e, world
    )
