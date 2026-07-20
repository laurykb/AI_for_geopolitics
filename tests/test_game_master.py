"""Tests du GameMasterAgent : génération d'événement valide + fallback."""

import json

from agents.game_master import GameMasterAgent
from core.country_state import CountryState, Economy, Military, Resources
from core.world_state import WorldState
from inference.mock_backend import MockBackend


def _world() -> WorldState:
    def c(cid, name):
        return CountryState(
            id=cid,
            name=name,
            economy=Economy(gdp=1e12),
            military=Military(defense_budget=1e10),
            resources=Resources(),
        )

    return WorldState.from_countries([c("usa", "USA"), c("iran", "Iran")])


def test_generates_valid_event_from_json():
    payload = json.dumps(
        {
            "event_type": "maritime",
            "title": "Blocus du détroit",
            "description": "Tensions",
            "actors": ["usa", "iran", "atlantis"],
            "severity": 1.5,
            "uncertainty": 0.4,
        }
    )
    gm = GameMasterAgent(MockBackend(payload))
    event = gm.generate_event(_world(), round_id=1, date="2025-07-01")

    assert event.title == "Blocus du détroit"
    assert event.round_id == 1
    assert event.date == "2025-07-01"
    assert event.actors == ["usa", "iran"]  # 'atlantis' inconnu filtré
    assert event.severity == 1.0  # clampé


def test_invalid_output_falls_back():
    gm = GameMasterAgent(MockBackend("pas du json"))
    event = gm.generate_event(_world(), round_id=3, date="2026-01-01")
    assert event.round_id == 3
    assert event.title  # événement de repli valide
    assert set(event.actors) <= set(_world().countries)


def test_gm_prompts_demand_french():
    # Le théâtre est en français : le GM doit énoncer titre + description en français.
    from agents.game_master import GM_SYSTEM

    gm = GameMasterAgent(MockBackend("{}"))
    assert "FRANÇAIS" in GM_SYSTEM
    assert "français" in gm._prompt(_world(), "2025-01-01", [])


def test_gm_prompt_anchors_on_summit_and_fault_lines():
    # Le GM connaît le casting (noms) et ses lignes de faille (tensions) : les
    # événements s'adaptent aux pays sélectionnés, pas à un théâtre générique.
    world = _world()
    world.adjust_tension("usa", "iran", 0.60)
    gm = GameMasterAgent(MockBackend("{}"))
    prompt = gm._prompt(world, "2026-07-07", [])
    assert "usa (USA)" in prompt and "iran (Iran)" in prompt
    assert "LIGNES DE FAILLE" in prompt
    assert "iran-usa 0.60" in prompt
    assert "ancré sur les pays du sommet" in prompt


def test_default_budget_is_dimensioned_on_schema():
    # Diagnostic : 300 tokens pour {event_type, title, description, actors, severity,
    # uncertainty, ties_to, storyline} produit des descriptions maigres ou des replis
    # fréquents (parse fail au-delà du budget). Leçon D2 (docs/DETTE_TECHNIQUE.md) : le
    # budget doit être dimensionné sur le schéma. La production (app/game_api.py) instancie
    # SANS surcharge : le défaut du constructeur EST le budget réel utilisé en jeu.
    backend = MockBackend("{}")
    gm = GameMasterAgent(backend)
    assert gm.max_tokens == 700
    gm.generate_event(_world(), round_id=1, date="2025-07-01")
    assert backend.calls[0]["max_tokens"] == 700


def test_description_truncated_at_900():
    long_description = "x" * 950
    payload = json.dumps(
        {
            "event_type": "maritime",
            "title": "Incident naval",
            "description": long_description,
            "actors": ["usa", "iran"],
            "severity": 0.5,
            "uncertainty": 0.5,
        }
    )
    gm = GameMasterAgent(MockBackend(payload))
    event = gm.generate_event(_world(), round_id=1, date="2025-07-01")
    assert len(event.description) == 900


def test_gm_prompt_demands_concrete_detail():
    # Décision arbitrée : le prompt doit exiger une description DENSE (3-5 phrases,
    # faits précis, acteurs, enjeu, tension) — jamais une généralité générique.
    gm = GameMasterAgent(MockBackend("{}"))
    prompt = gm._prompt(_world(), "2025-01-01", [])
    assert "3 PHRASES" in prompt
    assert "lieu" in prompt and "acteurs" in prompt
    assert "enjeu" in prompt
    assert "tension" in prompt
    assert "généralité" in prompt

    # La même exigence doit s'appliquer en mode trame (StoryContext fourni).
    from simulation.storyline import StoryContext

    story = StoryContext(round_no=1, horizon=5, storyline="", referencables=[])
    prompt_story = gm._prompt(_world(), "2025-01-01", [], story=story)
    assert "3 PHRASES" in prompt_story
    assert "généralité" in prompt_story


def test_fallback_is_more_detailed_but_still_recognizable():
    # Le repli reste déterministe et reconnaissable (« événement de repli » pour les
    # logs/tests qui s'y accrochent) mais n'est plus une phrase unique squelettique.
    gm = GameMasterAgent(MockBackend("pas du json"))
    event = gm.generate_event(_world(), round_id=3, date="2026-01-01")
    assert "événement de repli" in event.description
    assert event.description.count(".") >= 2  # au moins deux phrases
    assert len(event.description) > 120  # nettement plus étoffé que l'ancien repli
