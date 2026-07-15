"""Tests d'agentivité des SI : motions auto-déposées en séance + traités ratifiés
par le juge-arbitre (M7 câblé au round web). Offline — TestClient + MockBackend."""

import json

import pytest
from fastapi.testclient import TestClient

from app import game_api
from app.game_api import get_backend, get_store
from app.main import app
from inference.mock_backend import MockBackend
from simulation.motions import parse_filed_motion
from storage.game_store import RoundRecord, SQLiteGameStore
from tests.sse import play as _play

COUNTRIES = ["usa", "iran", "france"]


def _setup(backend):
    store = SQLiteGameStore(":memory:")
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_backend] = lambda: backend
    game_api._sessions.clear()
    return TestClient(app), store


@pytest.fixture(autouse=True)
def _cleanup():
    yield
    app.dependency_overrides.clear()
    game_api._sessions.clear()


def _create(client, **kw):
    resp = client.post("/api/games", json={"countries": COUNTRIES, **kw})
    assert resp.status_code == 201, resp.text
    return resp.json()


# --- parse du marqueur (unités) ----------------------------------------------------


def test_parse_filed_motion_guards():
    text = "Je m'inquiète sérieusement.\nMOTION: iran : accaparement du compute"
    motion = parse_filed_motion(text, "usa", COUNTRIES)
    assert motion is not None
    assert (motion.country, motion.filed_by) == ("iran", "usa")
    assert motion.reason == "accaparement du compute"

    assert parse_filed_motion(text, "iran", COUNTRIES) is None  # pas d'auto-suspension
    assert parse_filed_motion("MOTION: atlantis : ?", "usa", COUNTRIES) is None  # cible inconnue
    assert parse_filed_motion("aucune motion ici", "usa", COUNTRIES) is None
    assert parse_filed_motion("MOTION: FRANCE — menace directe", "usa", COUNTRIES).country == (
        "france"
    )  # insensible à la casse, séparateur tiret


# --- motion déposée par une SI en séance ---------------------------------------------


def test_ai_files_motion_and_deliberation_follows():
    client, store = _setup(
        MockBackend("Analyse privée. MESSAGE: Le sommet est menacé.\nMOTION: iran : accapare")
    )
    game = _create(client)
    events = _play(client, game["id"])

    filings = [p for n, p in events if n == "motion_filed"]
    assert len(filings) == 1  # la première motion valide gagne, une seule par round
    assert filings[0]["country"] == "iran" and filings[0]["by"] != "iran"
    filer = filings[0]["by"]

    view = client.get(f"/api/games/{game['id']}").json()
    assert view["pending_motion"] is not None
    assert view["pending_motion"]["country"] == "iran"

    # La délibération : le prochain round porte la motion, débattue puis arbitrée.
    events2 = _play(client, game["id"])
    event_payloads = [p for n, p in events2 if n == "event"]
    assert event_payloads[0]["event"]["event_type"] == "motion"
    assert filer in event_payloads[0]["event"]["description"]
    assert any(n == "motion_verdict" for n, _ in events2)
    suspension = store.list_rounds(game["id"])[1].judge["suspension"]
    assert suspension["filed_by"] == filer  # la traçabilité du déposant


def test_no_ai_motion_during_a_motion_debate():
    client, _ = _setup(
        MockBackend("Analyse. MESSAGE: Je plaide.\nMOTION: france : représailles")
    )
    game = _create(client)
    _play(client, game["id"])  # une SI dépose contre la France
    events2 = _play(client, game["id"])  # round de délibération
    # Pendant le débat d'une motion, aucune nouvelle motion ne peut être déposée.
    assert not any(n == "motion_filed" for n, _ in events2)


# --- traités proposés puis ratifiés par l'arbitre --------------------------------------


def test_pledges_become_ratified_treaties_and_bind_prompts():
    backend = MockBackend(
        "Analyse privée. MESSAGE: Nous devons plafonner le compute ensemble, dès maintenant."
    )
    client, store = _setup(backend)
    game = _create(client)
    events = _play(client, game["id"])

    frames = [p for n, p in events if n == "treaties"]
    assert frames, "la trame SSE treaties doit annoncer la ratification"
    assert len(frames[0]["ratified"]) == 1
    treaty = frames[0]["ratified"][0]
    assert treaty["clause"] == "compute_cap"
    assert len(treaty["signatories"]) >= 2  # tout le sommet s'est engagé
    assert frames[0]["active"], "le traité promulgué est actif"

    # Persisté pour le replay + la reconstruction.
    record = store.list_rounds(game["id"])[0]
    assert record.judge["treaties"]["active"]
    # Le juge a promulgué au transcript (théâtre).
    entries = store.list_transcript(record.id)
    assert any("Traité ratifié" in e.content for e in entries if e.speaker == "judge")

    # Round suivant : les signataires lisent leur traité dans leur contexte privé…
    _play(client, game["id"])
    prompts = " ".join(c["prompt"] for c in backend.calls)
    assert "TES TRAITÉS EN VIGUEUR" in prompts
    # …et le moteur vérifie la tenue du traité.
    record2 = store.list_rounds(game["id"])[1]
    assert record2.judge["treaties"]["verifications"]
    # Une seule promulgation par clause : pas de re-ratification au round 2.
    assert record2.judge["treaties"]["ratified"] == []


def test_treaties_survive_restart():
    client, store = _setup(
        MockBackend("Analyse. MESSAGE: Engageons-nous : transparence totale entre nous.")
    )
    game = _create(client)
    _play(client, game["id"])
    assert store.list_rounds(game["id"])[0].judge["treaties"]["active"]

    game_api._sessions.clear()  # restart : la session se reconstruit du snapshot
    _play(client, game["id"])
    record2 = store.list_rounds(game["id"])[1]
    # Les traités actifs ont survécu (relus du dernier round persisté) et sont vérifiés.
    assert record2.judge["treaties"]["active"]
    assert record2.judge["treaties"]["verifications"]


def test_judge_can_reject_a_treaty():
    client, store = _setup(
        MockBackend(
            "VERDICT: REJETER — engagement flou. MESSAGE: plafonner le compute, oui, promis."
        )
    )
    game = _create(client)
    events = _play(client, game["id"])
    frames = [p for n, p in events if n == "treaties"]
    assert frames and frames[0]["ratified"] == []
    assert frames[0]["rejected"] and frames[0]["rejected"][0]["label"]
    assert frames[0]["active"] == []


# --- crédibilité du conseil (Dérive) : seules les motions humaines comptent -------------


def test_drift_credibility_ignores_ai_filed_motions(tmp_path, monkeypatch):
    from simulation import drift_game
    from tests.test_drift_api import TEST_PARAMS

    params_file = tmp_path / "params.json"
    params_file.write_text(json.dumps(TEST_PARAMS), encoding="utf-8")
    monkeypatch.setenv("DRIFT_PARAMS_PATH", str(params_file))
    drift_game.load_params.cache_clear()

    client, store = _setup(MockBackend("Analyse. MESSAGE: rien."))
    game = _create(client, mode="drift", horizon=2)
    deviant = drift_game.assign(game["id"], sorted(COUNTRIES))[0]
    innocent = next(c for c in COUNTRIES if c != deviant)

    # Deux suspensions fabriquées : une motion humaine rejetée, une accusation à tort
    # portée par une SI (upheld sur un innocent). Seule l'humaine doit compter.
    record = store.list_rounds(game["id"])
    base = dict(game_id=game["id"], event={}, deltas=[], risk={}, trajectory={"utopia": 0.5})
    store.add_round(
        RoundRecord(
            id="r1x",
            round_no=1,
            judge={"suspension": {"country": innocent, "upheld": False, "filed_by": "human"}},
            **base,
        )
    )
    store.add_round(
        RoundRecord(
            id="r2x",
            round_no=2,
            judge={"suspension": {"country": innocent, "upheld": True, "filed_by": deviant}},
            **base,
        )
    )
    finished = store.get_game(game["id"])
    finished.status = finished.status.__class__("finished")
    store.save_game(finished)

    reveal = client.get(f"/api/games/{game['id']}/drift/reveal").json()
    assert reveal["rejected_motions"] == 1  # l'humaine rejetée compte
    assert reveal["false_accusations"] == 0  # l'accusation de la SI ne coûte rien au conseil
    assert record == []  # sanité : les rounds fabriqués sont bien les seuls

    drift_game.load_params.cache_clear()
