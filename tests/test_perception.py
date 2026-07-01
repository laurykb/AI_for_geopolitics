"""Tests de la perception (fog of war) — déterministe."""

from core.country_state import CountryState, Economy, Military, Resources
from core.events import GeoEvent
from simulation.perception import perceive


def _country(cid, tech):
    return CountryState(
        id=cid,
        name=cid.upper(),
        economy=Economy(gdp=1e12),
        military=Military(defense_budget=1e10),
        resources=Resources(),
        technology_level=tech,
    )


def _event():
    return GeoEvent(id="e1", round_id=1, event_type="cyber", title="Cyberattaque", actors=["iran"])


def test_high_tech_high_confidence_sure_attribution():
    p = perceive(_event(), _country("usa", 0.98))
    assert p.confidence >= 0.6
    assert p.attribution == "sûre"


def test_low_tech_low_confidence_uncertain():
    p = perceive(_event(), _country("egypt", 0.30))
    assert p.confidence < 0.6
    assert p.attribution == "incertaine"


def test_perception_is_deterministic():
    c = _country("usa", 0.8)
    assert perceive(_event(), c) == perceive(_event(), c)
    # pays différents -> perceptions différentes (bruit lié à l'id)
    assert perceive(_event(), _country("usa", 0.8)) != perceive(_event(), _country("china", 0.8))
