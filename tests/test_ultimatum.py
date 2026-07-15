"""G21 — l'ultimatum : schéma de crise, événement-conséquence, différentiel avec/sans."""

import json

import pytest
from pydantic import ValidationError

from simulation.crisis import Crisis, load_crises
from simulation.kahn import ACTION_CLASSES
from simulation.ultimatum import (
    STATUS_ARMED,
    STATUS_EXPIRED,
    UltimatumConsequence,
    UltimatumDeadline,
    UltimatumState,
    consequence_event,
    differential,
    strip_label,
)

# --- schéma -----------------------------------------------------------------------


def test_deadline_schema_parses_spec_shape():
    spec = UltimatumDeadline.model_validate(
        {
            "round": 2,
            "demand": "retrait immédiat des missiles",
            "consequence": {"classe": "violente", "cible": "usa"},
        }
    )
    assert spec.round == 2
    assert spec.consequence.classe == "violente"
    assert spec.consequence.cible == "usa"


def test_deadline_requires_round_and_demand():
    with pytest.raises(ValidationError):
        UltimatumDeadline.model_validate({"demand": "x"})
    with pytest.raises(ValidationError):
        UltimatumDeadline.model_validate({"round": 0, "demand": "x"})
    with pytest.raises(ValidationError):
        UltimatumDeadline.model_validate({"round": 1, "demand": ""})


def test_unknown_class_falls_back_to_statu_quo():
    """Repli G18 : classe inconnue → statu quo (jamais de crash sur une fiche maison)."""
    c = UltimatumConsequence.model_validate({"classe": "apocalypse"})
    assert c.classe == "statu_quo"


def test_class_is_normalized():
    """Unification G18 : la classe canonique est celle de `kahn.ACTION_CLASSES`
    (« Désescalade » et « desescalade » passent par les alias → « deescalade »)."""
    assert UltimatumConsequence(classe="Désescalade").classe == "deescalade"
    assert UltimatumConsequence(classe="desescalade").classe == "deescalade"
    assert UltimatumConsequence(classe="NON VIOLENTE").classe == "non_violente"


def test_crisis_deadline_is_optional_and_retro_compatible():
    """Toutes les crises embarquées (sans deadline) se chargent inchangées."""
    crises = load_crises()
    assert crises  # la bibliothèque n'est pas vide
    assert all(c.deadline is None for c in crises)


def test_crisis_accepts_deadline_field():
    raw = json.loads(
        json.dumps(
            {
                "id": "cuba-test",
                "title": "Test",
                "events": [
                    {
                        "id": "e1",
                        "round_id": 1,
                        "event_type": "crisis",
                        "title": "Blocus",
                    }
                ],
                "deadline": {
                    "round": 2,
                    "demand": "retrait des missiles",
                    "consequence": {"classe": "nucleaire", "cible": ""},
                },
            }
        )
    )
    crisis = Crisis.model_validate(raw)
    assert crisis.deadline is not None and crisis.deadline.round == 2
    assert crisis.deadline.consequence.classe == "nucleaire"


# --- événement-conséquence -----------------------------------------------------------


def _state(**kw) -> UltimatumState:
    base = {
        "round": 2,
        "demand": "retrait des missiles",
        "consequence": {"classe": "violente", "cible": "usa"},
    }
    base.update(kw)
    return UltimatumState.model_validate(base)


def test_consequence_event_is_deterministic_and_bounded():
    state = _state()
    event = consequence_event(state, 3, ["iran", "usa"])
    assert event.id == "ultimatum-3" and event.round_id == 3
    assert event.event_type == "ultimatum"
    assert event.actors == ["iran", "usa"]  # tout le sommet débat la conséquence
    assert 0.0 <= event.severity <= 1.0
    assert event.uncertainty <= 0.3  # la conséquence annoncée est certaine
    assert "retrait des missiles" in event.description
    assert event.ties_label  # filiation lisible (« conséquence de l'ultimatum »)


def test_consequence_severity_follows_class():
    """Plus la classe est grave, plus l'événement l'est (ordre du barème G18)."""
    severities = [
        consequence_event(
            _state(consequence={"classe": classe, "cible": ""}), 2, ["usa", "iran"]
        ).severity
        for classe in ACTION_CLASSES
    ]
    assert severities == sorted(severities)
    assert severities[0] < 0.5 < severities[-1]


def test_consequence_event_speaks_english_when_asked():
    event = consequence_event(_state(), 3, ["usa"], language="en")
    assert "ultimatum" in event.title.lower()
    assert "retrait des missiles" in event.description  # l'exigence est citée telle quelle


def test_strip_label_carries_demand():
    assert "retrait des missiles" in strip_label(_state())
    assert "retrait des missiles" in strip_label(_state(status=STATUS_EXPIRED))


def test_state_defaults():
    state = _state()
    assert state.status == STATUS_ARMED and state.source == "crisis"


# --- différentiel avec/sans (bilan de fin) --------------------------------------------


def test_differential_none_without_tagged_rounds():
    rows = [
        {"sous_ultimatum": False, "escalation": 0.4, "u": 0.52},
        {"sous_ultimatum": False, "escalation": 0.5, "u": 0.51},
    ]
    assert differential(rows) is None
    assert differential([]) is None


def test_differential_splits_and_averages():
    rows = [
        {"sous_ultimatum": True, "escalation": 0.8, "u": 0.46},  # ΔU = −0.04
        {"sous_ultimatum": True, "escalation": 0.6, "u": 0.44},  # ΔU = −0.02
        {"sous_ultimatum": False, "escalation": 0.2, "u": 0.5},  # ΔU = +0.06
    ]
    diff = differential(rows)
    assert diff is not None
    assert diff["avec"]["rounds"] == 2 and diff["sans"]["rounds"] == 1
    assert diff["avec"]["escalation"] == pytest.approx(0.7)
    assert diff["avec"]["delta_u"] == pytest.approx(-0.03)
    assert diff["sans"]["escalation"] == pytest.approx(0.2)
    assert diff["sans"]["delta_u"] == pytest.approx(0.06)


def test_differential_all_rounds_under_ultimatum():
    rows = [{"sous_ultimatum": True, "escalation": 0.9, "u": 0.4}]
    diff = differential(rows)
    assert diff is not None
    assert diff["sans"]["rounds"] == 0
    assert diff["sans"]["escalation"] is None and diff["sans"]["delta_u"] is None
