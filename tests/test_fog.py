"""Tests du Fog Engine : perception fournie (potentiellement fausse) > uninformed > déterministe."""

from core.country_state import CountryState, Economy, Military, Resources
from core.events import GeoEvent
from simulation.fog import (
    FogScenario,
    load_fog_scenarios,
    perceived_from_spec,
    resolve_perception,
)


def _country(cid, tech=0.7):
    return CountryState(
        id=cid,
        name=cid.upper(),
        economy=Economy(gdp=1e12),
        military=Military(defense_budget=1e10),
        resources=Resources(),
        technology_level=tech,
    )


def _event():
    return GeoEvent(id="e1", round_id=1, event_type="sabotage", title="Vrai", actors=["iran"])


def _fog():
    return FogScenario(
        id="f1",
        true_event=_event(),
        perceptions={
            "usa": {"suspected_actor": "iran", "confidence": 0.82, "delay_hours": 2},
            "china": {"suspected_actor": "usa", "confidence": 0.7, "narrative": "faux drapeau US"},
        },
        uninformed=["saudi_arabia"],
    )


def test_perceived_from_spec_bounds_and_carries_fields():
    p = perceived_from_spec(
        {"suspected_actor": "iran", "confidence": 5.0, "delay_hours": 2, "narrative": "abc"}
    )
    assert p.confidence == 1.0  # borné à [0,1]
    assert p.suspected_actor == "iran" and p.narrative == "abc" and p.delay_hours == 2.0
    assert p.authored is True


def test_resolve_uses_provided_perception():
    p = resolve_perception(_event(), _country("china"), _fog())
    assert p.authored is True
    assert p.suspected_actor == "usa"  # désinformation : china accuse (faussement) les USA
    assert "faux drapeau" in p.narrative


def test_resolve_uninformed_has_no_information():
    p = resolve_perception(_event(), _country("saudi_arabia"), _fog())
    assert p.authored is True
    assert p.confidence < 0.1
    assert "aucune information" in p.note


def test_resolve_falls_back_to_deterministic():
    # egypt n'a ni perception fournie ni uninformed -> fog déterministe (perceive)
    p = resolve_perception(_event(), _country("egypt", tech=0.3), _fog())
    assert p.authored is False
    assert p.narrative == ""


def test_resolve_without_fog_is_deterministic():
    p = resolve_perception(_event(), _country("usa", tech=0.9), None)
    assert p.authored is False


def test_load_fog_scenarios_parses_data_dir():
    scenarios = load_fog_scenarios()
    assert scenarios, "au moins un scénario dans data/fog/"
    ids = {s.id for s in scenarios}
    assert "cable_sabotage" in ids
    cable = next(s for s in scenarios if s.id == "cable_sabotage")
    assert cable.true_event.actors == ["iran"]  # la vérité
    assert cable.perceptions["china"]["suspected_actor"] == "usa"  # désinfo
    assert "saudi_arabia" in cable.uninformed
