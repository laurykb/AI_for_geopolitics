"""Tests des modèles de domaine (validation, chargement JSON)."""

import pytest
from pydantic import ValidationError

from core.country_state import CountryState


def test_load_from_json_seed():
    country = CountryState.from_json_file("data/countries/usa.json")
    assert country.id == "usa"
    assert country.economy.gdp > 0
    assert country.military.nuclear_power is True
    assert "NATO" in country.alliances


def test_bounds_validation_rejects_out_of_range():
    with pytest.raises(ValidationError):
        CountryState(
            id="x",
            name="X",
            economy={"gdp": 1.0},
            military={"defense_budget": 1.0},
            resources={"oil_dependency": 2.0},  # > 1.0 -> invalide
        )


def test_defaults_are_applied():
    country = CountryState(
        id="y",
        name="Y",
        economy={"gdp": 1.0},
        military={"defense_budget": 1.0},
        resources={},
    )
    assert country.political_stability == 0.5
    assert country.alliances == []
    assert country.mandate == {}  # fiche de comportement surchargeable, vide par défaut
