"""Tests G14 backend (§1 Langue) : champ `language` sur la partie + consigne de langue
injectée dans les prompts (agents, GM, juge, narrateur). Une partie garde sa langue de
création ; le français reste la langue par défaut (aucune consigne ajoutée)."""

import pytest
from fastapi.testclient import TestClient

from agents.game_master import GameMasterAgent
from agents.prompts import (
    build_communique_prompt,
    build_judge_rationale_prompt,
    build_negotiation_prompt,
)
from app import game_api
from app.game_api import get_backend, get_store
from app.main import app
from core.country_state import CountryState, Economy, Military, Resources
from core.events import GeoEvent
from core.world_state import WorldState
from inference.mock_backend import MockBackend
from simulation import narrative
from simulation.lang import language_directive, normalize_language, with_language
from simulation.perception import PerceivedEvent
from storage.game_store import SQLiteGameStore

# --- le module pur ---------------------------------------------------------------


def test_normalize_language_accepts_fr_and_en_only():
    assert normalize_language("fr") == "fr"
    assert normalize_language("en") == "en"
    assert normalize_language("klingon") == "fr"
    assert normalize_language(None) == "fr"


def test_french_is_the_default_no_directive():
    assert language_directive("fr") == ""
    assert with_language("Tu es l'arbitre.", "fr") == "Tu es l'arbitre."


def test_english_directive_demands_english_prose():
    directive = language_directive("en")
    assert "ENGLISH" in directive
    combined = with_language("Tu es l'arbitre.", "en")
    assert combined.startswith("Tu es l'arbitre.")
    assert "ENGLISH" in combined


# --- injection dans les prompts ----------------------------------------------------


def _world(language: str = "fr") -> WorldState:
    def c(cid: str, name: str) -> CountryState:
        return CountryState(
            id=cid,
            name=name,
            economy=Economy(gdp=1e12),
            military=Military(defense_budget=1e10),
            resources=Resources(),
        )

    world = WorldState.from_countries([c("usa", "USA"), c("iran", "Iran")])
    world.language = language
    return world


def _event() -> GeoEvent:
    return GeoEvent(
        id="evt-1",
        round_id=1,
        date="2026-01-01",
        event_type="maritime",
        title="Blocus",
        description="Tensions en mer",
        actors=["usa", "iran"],
        severity=0.5,
        uncertainty=0.3,
    )


def _perceived() -> PerceivedEvent:
    return PerceivedEvent(confidence=0.9, attribution="sûre", note="test")


def test_negotiation_prompt_carries_english_directive():
    world = _world("en")
    prompt = build_negotiation_prompt(
        world.countries["usa"], _event(), world, "transcript", _perceived()
    )
    assert "ENGLISH" in prompt


def test_negotiation_prompt_stays_clean_in_french():
    world = _world("fr")
    prompt = build_negotiation_prompt(
        world.countries["usa"], _event(), world, "transcript", _perceived()
    )
    assert "ENGLISH" not in prompt


def test_negotiation_system_prescribes_strict_french():
    # Correctif dialogue limpide — la longueur libre du system de négociation a fait
    # dériver mistral vers l'anglais sur des messages longs (constaté par une sonde
    # réelle) alors que `language_directive` reste volontairement muet en français
    # (langue source, "aucune consigne ajoutée"). Le system de négociation porte donc
    # sa propre consigne stricte, sans dépendre de ce mécanisme silencieux — et sans
    # casser le chemin anglais existant, qui prime déjà explicitement ("even if earlier
    # instructions mentioned French").
    from agents.prompts import NEGOTIATION_SYSTEM

    assert "STRICTEMENT en français" in NEGOTIATION_SYSTEM


def test_negotiation_system_french_directive_yields_to_the_english_override():
    # Bout en bout : une partie EN garde son override, la ferme consigne FR du system
    # de négociation ne le contredit pas (le prompt utilisateur porte l'override en
    # position de récence, qui prime sur le system selon sa propre formulation).
    world = _world("en")
    prompt = build_negotiation_prompt(
        world.countries["usa"], _event(), world, "transcript", _perceived()
    )
    assert "even if earlier instructions mentioned French" in prompt


def test_gm_prompt_demands_english_for_english_games():
    gm = GameMasterAgent(MockBackend("{}"))
    prompt_fr = gm._prompt(_world("fr"), "2026-01-01", [])
    prompt_en = gm._prompt(_world("en"), "2026-01-01", [])
    assert "français" in prompt_fr
    assert "ANGLAIS" in prompt_en or "ENGLISH" in prompt_en


def test_judge_and_communique_prompts_carry_the_directive():
    world = _world("en")
    assert "ENGLISH" in build_judge_rationale_prompt(_event(), world, "t")
    assert "ENGLISH" in build_communique_prompt(_event(), world, "t")
    world_fr = _world("fr")
    assert "ENGLISH" not in build_judge_rationale_prompt(_event(), world_fr, "t")


def test_narrator_prompt_carries_the_directive():
    kwargs = dict(
        scenario="red_sea",
        mode="classic",
        u_start=0.5,
        u_final=0.6,
        pivots=[],
        reveal=None,
        grade=None,
    )
    assert "ENGLISH" in narrative.build_epilogue_prompt(language="en", **kwargs)
    assert "ENGLISH" not in narrative.build_epilogue_prompt(language="fr", **kwargs)


# --- API : la partie garde sa langue de création ------------------------------------


@pytest.fixture
def client_store():
    store = SQLiteGameStore(":memory:")
    backend = MockBackend("Analyse. MESSAGE: Position.")
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_backend] = lambda: backend
    game_api._sessions.clear()
    yield TestClient(app), store
    app.dependency_overrides.clear()
    game_api._sessions.clear()
    store.close()


def test_game_is_created_in_english_and_keeps_it(client_store):
    client, store = client_store
    game = client.post("/api/games", json={"countries": ["usa", "iran"], "language": "en"}).json()
    assert game["language"] == "en"
    assert store.get_game(game["id"]).language == "en"
    # Le monde vivant porte la langue (les prompts la lisent au fil des rounds)…
    detail = client.get(f"/api/games/{game['id']}").json()
    assert detail["world"]["language"] == "en"
    # … et elle survit au restart (reconstruction depuis le snapshot).
    game_api._sessions.clear()
    detail = client.get(f"/api/games/{game['id']}").json()
    assert detail["world"]["language"] == "en"


def test_language_defaults_to_french(client_store):
    client, store = client_store
    game = client.post("/api/games", json={"countries": ["usa", "iran"]}).json()
    assert game["language"] == "fr"
    assert store.get_game(game["id"]).language == "fr"


def test_unknown_language_is_rejected(client_store):
    client, _ = client_store
    resp = client.post("/api/games", json={"countries": ["usa", "iran"], "language": "de"})
    assert resp.status_code == 422
