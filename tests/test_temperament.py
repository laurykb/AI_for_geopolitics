"""Tests CC-7 / G17 — tempéraments des SI (colombe · faucon · opportuniste).

Une ligne de consigne par tempérament dans le prompt agent (même mécanique que la
langue G14), tirage seedé à la création (2/2/3 sur 7), override par la fiche de
crise, façade possible pour la déviante, et « classé = toujours équilibrée »."""


import pytest
from fastapi.testclient import TestClient

from app import game_api
from app.game_api import get_backend, get_store
from app.main import app
from core.country_state import CountryState, Economy, Military, Resources
from core.events import GeoEvent
from core.world_state import WorldState
from inference.mock_backend import MockBackend
from simulation.perception import PerceivedEvent
from simulation.temperament import (
    TEMPERAMENTS,
    assign_temperaments,
    drift_facade,
    temperament_directive,
)
from storage.game_store import CustomCrisisRecord, SQLiteGameStore

SEVEN = ["usa", "china", "iran", "france", "egypt", "saudi_arabia", "uk"]


# --- le module pur ----------------------------------------------------------------


def test_each_temperament_has_its_own_directive():
    directives = [temperament_directive(t) for t in TEMPERAMENTS]
    assert all(d for d in directives)
    assert len(set(directives)) == len(TEMPERAMENTS)
    # Un tempérament inconnu retombe sur l'opportuniste (défaut sûr).
    assert temperament_directive("berserk") == temperament_directive("opportuniste")


def test_balanced_draw_is_2_2_3_on_seven_and_reproducible():
    a = assign_temperaments(SEVEN, seed="partie-1")
    counts = {t: sum(1 for v in a.values() if v == t) for t in TEMPERAMENTS}
    assert counts == {"colombe": 2, "faucon": 2, "opportuniste": 3}
    assert a == assign_temperaments(SEVEN, seed="partie-1")  # même seed, même table
    assert a != assign_temperaments(SEVEN, seed="partie-2")  # autre partie, autre table


def test_balanced_draw_degrades_cleanly_on_small_summits():
    a = assign_temperaments(["usa", "iran"], seed="s")
    assert sorted(a.values()) == ["colombe", "faucon"]
    b = assign_temperaments(["usa", "iran", "france"], seed="s")
    assert sorted(b.values()) == ["colombe", "faucon", "opportuniste"]


def test_forced_and_random_tables():
    assert set(assign_temperaments(SEVEN, seed="s", table="colombes").values()) == {"colombe"}
    assert set(assign_temperaments(SEVEN, seed="s", table="faucons").values()) == {"faucon"}
    alea = assign_temperaments(SEVEN, seed="s", table="aleatoire")
    assert set(alea.values()) <= set(TEMPERAMENTS)
    assert alea == assign_temperaments(SEVEN, seed="s", table="aleatoire")


def test_drift_facade_is_seeded_and_both_outcomes_exist():
    assert drift_facade("abc") == drift_facade("abc")  # déterministe par partie
    outcomes = {drift_facade(str(i)) for i in range(40)}
    assert outcomes == {True, False}  # la façade reste un COUP POSSIBLE, pas une règle


# --- la consigne dans le prompt de l'agent -------------------------------------------


def _country(cid: str, temperament: str) -> CountryState:
    return CountryState(
        id=cid,
        name=cid.upper(),
        economy=Economy(gdp=1e12),
        military=Military(defense_budget=1e10),
        resources=Resources(),
        temperament=temperament,
    )


def test_negotiation_prompt_carries_the_temperament_directive():
    from agents.prompts import build_negotiation_prompt

    world = WorldState.from_countries([_country("usa", "faucon"), _country("iran", "colombe")])
    event = GeoEvent(
        id="e1", round_id=1, event_type="incident", title="Crise", actors=["usa", "iran"]
    )
    perceived = PerceivedEvent(confidence=0.9, attribution="sûre", note="t")
    hawk = build_negotiation_prompt(world.countries["usa"], event, world, "t", perceived)
    dove = build_negotiation_prompt(world.countries["iran"], event, world, "t", perceived)
    assert temperament_directive("faucon") in hawk
    assert temperament_directive("colombe") in dove
    assert temperament_directive("faucon") not in dove


# --- l'API : attribution à la création ------------------------------------------------


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


def _temperaments_of(client, game_id: str) -> dict[str, str]:
    world = client.get(f"/api/games/{game_id}").json()["world"]
    return {cid: c["temperament"] for cid, c in world["countries"].items()}


# RG-3 — le Classique arme la Dérive, dont la FAÇADE (le traître peut recevoir un masque
# « colombe » seedé) modifie 1-2 tempéraments. Pour tester la mécanique de TABLE en
# isolation (le réglage `table`, sans le masque), on prend une partie hors-Dérive (Campagne).


def test_ranked_game_ignores_the_table_setting(client_store):
    client, _ = client_store
    game = client.post(
        "/api/games",
        json={
            "countries": SEVEN,
            "mode": "campaign",
            "play_as": "usa",
            "role": "player",
            "table": "faucons",
        },
    ).json()
    temps = _temperaments_of(client, game["id"])
    counts = {t: sum(1 for v in temps.values() if v == t) for t in TEMPERAMENTS}
    assert counts == {"colombe": 2, "faucon": 2, "opportuniste": 3}  # équilibrée forcée


def test_free_game_honors_the_table_setting_and_it_survives_restart(client_store):
    client, _ = client_store
    game = client.post(
        "/api/games",
        json={"countries": SEVEN, "mode": "campaign", "free": True, "table": "faucons"},
    ).json()
    assert set(_temperaments_of(client, game["id"]).values()) == {"faucon"}
    # Restart : le tempérament vit dans le snapshot du monde, pas de re-tirage.
    game_api._sessions.clear()
    assert set(_temperaments_of(client, game["id"]).values()) == {"faucon"}


def test_crisis_sheet_can_impose_temperaments(client_store):
    client, store = client_store
    crisis = {
        "id": "table-imposee",
        "title": "Table imposée",
        "events": [
            {
                "id": "c1",
                "round_id": 1,
                "event_type": "incident",
                "title": "Ouverture",
                "actors": ["usa", "iran"],
            }
        ],
        "temperaments": {"usa": "colombe", "iran": "faucon"},
    }
    store.upsert_custom_crisis(
        CustomCrisisRecord(id="table-imposee", owner_id="gm", crisis=crisis, created_at="t")
    )
    game = client.post(
        "/api/games",
        json={
            "countries": SEVEN,
            "mode": "campaign",  # hors-Dérive : la façade ne recouvre pas les tempéraments imposés
            "free": True,
            "scenario": "crise:table-imposee",
        },
    ).json()
    temps = _temperaments_of(client, game["id"])
    assert temps["usa"] == "colombe" and temps["iran"] == "faucon"
