"""Tests de la forge de pays : JSON LLM validé/borné + repli déterministe (offline)."""

import json

from core.country_state import CountryState
from inference.backend import InferenceBackend
from inference.mock_backend import MockBackend
from simulation.country_forge import forge_country, slugify


class _FailingBackend(InferenceBackend):
    def generate(self, prompt, *, system=None, max_tokens=512, temperature=0.7, schema=None):
        raise RuntimeError("backend hors service")


def _full_payload():
    return json.dumps(
        {
            "gdp": 1.2e12,
            "growth": 4.0,
            "trade_dependency": 0.7,
            "defense_budget": 3e10,
            "nuclear_power": True,
            "projection": 0.8,
            "oil_dependency": 0.2,
            "energy_independence": 0.9,
            "political_system": "technocracy",
            "political_stability": 0.65,
            "technology_level": 0.95,
            "ideology": ["accelerationist", "post-national"],
            "strategic_priorities": ["AI supremacy", "energy autonomy"],
            "alliances": ["neo_atlantis"],
            "rivals": ["usa"],
            "mandate": {
                "red_line": "ne jamais céder le contrôle des semi-conducteurs",
                "priorities": ["souveraineté techno", "stabilité"],
                "concessions": "ouvert sur le climat",
                "domestic_constraints": "opinion technophile à satisfaire",
                "urgency": "élevée",
            },
        }
    )


def test_slugify():
    assert slugify("Néo-Atlantis") == "n_o_atlantis" or slugify("Neo Atlantis") == "neo_atlantis"
    assert slugify("  USA 2.0 ") == "usa_2_0"
    assert slugify("???") == "pays"


def test_forge_parses_full_payload():
    country = forge_country(MockBackend(_full_payload()), "Cyberia", "un État-plateforme IA")
    assert isinstance(country, CountryState)
    assert country.id == "cyberia" and country.name == "Cyberia"
    assert country.economy.gdp == 1.2e12 and country.military.nuclear_power is True
    assert country.technology_level == 0.95
    assert "AI supremacy" in country.strategic_priorities
    # la fiche comportementale LLM est récupérée (priorities liste -> string)
    assert country.mandate["red_line"].startswith("ne jamais")
    assert country.mandate["priorities"] == "souveraineté techno, stabilité"
    assert country.mandate["urgency"] == "élevée"


def test_forge_clamps_out_of_range_values():
    payload = json.dumps({"trade_dependency": 5.0, "political_stability": -3, "projection": 2})
    country = forge_country(MockBackend(payload), "Boundland", "")
    assert country.economy.trade_dependency == 1.0
    assert country.political_stability == 0.0
    assert country.military.projection == 1.0


def test_forge_falls_back_on_garbage():
    country = forge_country(MockBackend("pas du json"), "Mystland", "cité-État marchande")
    assert isinstance(country, CountryState)  # toujours un pays valide
    assert country.id == "mystland"
    # concept réutilisé comme priorité par défaut quand le LLM ne renvoie rien d'exploitable
    assert country.strategic_priorities == ["cité-État marchande"]
    assert 0.0 <= country.political_stability <= 1.0


def test_forge_falls_back_when_backend_fails():
    country = forge_country(_FailingBackend(), "Failistan", "")
    assert isinstance(country, CountryState) and country.id == "failistan"
    assert country.strategic_priorities == ["stabilité régionale"]  # défaut sans concept


def test_forge_respects_explicit_country_id():
    country = forge_country(MockBackend("{}"), "Doublon", "", country_id="custom_id")
    assert country.id == "custom_id"


def test_forge_prompt_contains_name_and_concept():
    backend = MockBackend("{}")
    forge_country(backend, "Aquaria", "archipel écologique")
    prompt = backend.calls[0]["prompt"]
    assert "Aquaria" in prompt and "archipel écologique" in prompt
