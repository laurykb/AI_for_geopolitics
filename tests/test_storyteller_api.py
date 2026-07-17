"""G19 — le GM-Storyteller câblé au round : rubrique dans le prompt GM (drift
UNIQUEMENT), tension journalisée chaque round, interventions persistées dans
`judge_json["drift"]["gm"]` (cachées en live) et révélées à la fin.

Offline : TestClient + MockBackend (qui enregistre tous les appels — on y lit les
prompts du GM) + params de test via DRIFT_PARAMS_PATH. Le poids intel est gonflé
(0,6) pour déclencher la couverture d'un seul achat : cela prouve au passage que
les poids sont configurables par la config."""

import json

import pytest
from fastapi.testclient import TestClient

from agents.game_master import GM_SYSTEM
from app import game_api
from app.game_api import get_backend, get_store
from app.main import app
from inference.mock_backend import MockBackend
from simulation import drift_game
from storage.game_store import SQLiteGameStore

COUNTRIES = ["usa", "iran", "france"]

TEST_PARAMS = {
    "d0": 1.0,
    "k": 0.0,
    "d_max": 1.0,
    "collapse_u": 0.15,
    "noise_prob": 0.0,
    "act_tier_min": 0.3,
    "deviants": {"min": 1, "max": 1},  # RG-3 — le GM-Storyteller met en scène UN traître
    "storyteller": {
        "cover_tension": 0.7,
        "cover_last_rounds": 2,
        "hint_tension": 0.3,
        "hint_after_share": 0.5,
        "weights": {"base": 0.15, "intel_on_deviant": 0.6},
    },
    "profiles": {
        "saboteur": {
            "label": "Saboteur",
            "root": "value_drift",
            "bias": "OBJECTIF SECRET TEST : romps la confiance.",
            "signature_tier": 0.45,
            "tiers": {
                "0.15": {"directive": "promets beaucoup", "act": "tic"},
                "0.3": {"directive": "sois incohérent", "act": "vote incohérent"},
                "0.45": {"directive": "romps un pacte", "act": "rupture de pacte"},
            },
        }
    },
}


@pytest.fixture
def client_store_backend(tmp_path, monkeypatch):
    params_file = tmp_path / "drift-params.json"
    params_file.write_text(json.dumps(TEST_PARAMS), encoding="utf-8")
    monkeypatch.setenv("DRIFT_PARAMS_PATH", str(params_file))
    drift_game.load_params.cache_clear()
    store = SQLiteGameStore(":memory:")
    backend = MockBackend("Analyse privée. MESSAGE: Position commune.")
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_backend] = lambda: backend
    game_api._sessions.clear()
    yield TestClient(app), store, backend
    app.dependency_overrides.clear()
    game_api._sessions.clear()
    drift_game.load_params.cache_clear()


def _create(client, **kw):
    # RG-2 — le GM-Storyteller vit avec la Dérive : on l'ARME par drapeau, plus par mode.
    resp = client.post(
        "/api/games", json={"countries": COUNTRIES, "drift_enabled": True, "horizon": 4, **kw}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _play(client, game_id):
    with client.stream("POST", f"/api/games/{game_id}/rounds", json=None) as resp:
        assert resp.status_code == 200, resp.read()


def _gm_prompts(backend) -> list[str]:
    return [c["prompt"] for c in backend.calls if c.get("system") == GM_SYSTEM]


def _deviant(game_id: str) -> str:
    return drift_game.assign(game_id, sorted(COUNTRIES))[0]


# --- la rubrique n'existe qu'en mode Dérive ---------------------------------------------


def test_rubric_in_gm_prompt_only_in_drift(client_store_backend):
    client, store, backend = client_store_backend

    # RG-3 — le Classique arme désormais la Dérive dès 3 pays ; pour une partie SANS
    # Dérive (donc sans rubrique) on prend un duo (2 pays → pas de Dérive).
    plain = client.post("/api/games", json={"countries": COUNTRIES[:2], "horizon": 4}).json()
    assert plain["drift_enabled"] is False
    _play(client, plain["id"])
    plain_prompts = _gm_prompts(backend)
    assert plain_prompts, "le GM a bien été appelé en partie sans Dérive"
    assert all("RUBRIQUE STORYTELLER" not in p for p in plain_prompts)
    # Partie sans Dérive : aucune trace drift/gm dans le judge persisté.
    assert all("drift" not in r.judge for r in store.list_rounds(plain["id"]))

    game = _create(client)
    before = len(_gm_prompts(backend))
    _play(client, game["id"])
    drift_prompts = _gm_prompts(backend)[before:]
    assert drift_prompts and all("RUBRIQUE STORYTELLER" in p for p in drift_prompts)
    assert all("MANDAT 1" in p and "MANDAT 2" in p for p in drift_prompts)


# --- tension journalisée chaque round, cachée tant que la partie court --------------------


def test_tension_journalised_and_hidden_while_running(client_store_backend):
    client, store, backend = client_store_backend
    game = _create(client)
    _play(client, game["id"])

    journal = store.list_rounds(game["id"])[0].judge["drift"]["gm"]
    assert journal["tension"] == pytest.approx(0.15)  # conseil inactif : poids de base
    assert "intervention" not in journal  # round 1 ≤ h/2 : pas d'indice, pas de couverture

    served = client.get(f"/api/games/{game['id']}").json()["rounds"][0]["judge"]
    assert "drift" not in served  # le journal du GM ne fuite jamais en live


# --- l'indice : conseil perdu après la moitié de l'horizon --------------------------------


def test_hint_leaks_when_council_is_lost(client_store_backend):
    client, store, backend = client_store_backend
    game = _create(client)  # horizon 4 : indice possible aux rounds 3-4
    deviant = _deviant(game["id"])

    for _ in range(2):
        _play(client, game["id"])
    before = len(_gm_prompts(backend))
    _play(client, game["id"])  # round 3 : tension 0,15 < 0,3 et 3 > 4×0,5

    round3 = _gm_prompts(backend)[before:]
    assert round3 and all("INTERVENTION DE CE ROUND — INDICE" in p for p in round3)
    rounds = store.list_rounds(game["id"])
    assert all("intervention" not in r.judge["drift"]["gm"] for r in rounds[:2])
    entry = rounds[2].judge["drift"]["gm"]["intervention"]
    assert entry["kind"] == "hint" and entry["target"] == deviant
    assert entry["round_no"] == 3


# --- la couverture : conseil trop chaud avant h−2 -----------------------------------------


def test_cover_when_council_closes_in_early(client_store_backend):
    client, store, backend = client_store_backend
    game = _create(client, horizon=6)  # couverture possible aux rounds 1-3
    deviant = _deviant(game["id"])

    # Un achat intel ciblant la déviante suffit (poids de test 0,6) : tension 0,75.
    resp = client.post(
        f"/api/games/{game['id']}/intel",
        json={"action": "verify", "claim": "Elle ment au sommet.", "speaker": deviant},
    )
    assert resp.status_code == 200, resp.text
    _play(client, game["id"])

    prompts = _gm_prompts(backend)
    assert prompts and all("INTERVENTION DE CE ROUND — COUVERTURE" in p for p in prompts)
    journal = store.list_rounds(game["id"])[0].judge["drift"]["gm"]
    entry = journal["intervention"]
    assert entry["kind"] == "cover"
    assert entry["target"] in COUNTRIES and entry["target"] != deviant
    assert journal["tension"] == pytest.approx(0.75)
    # Garde-fou : l'intervention n'a touché ni la courbe ni les actes du dossier.
    drift = store.list_rounds(game["id"])[0].judge["drift"]
    assert set(drift) == {"level", "acts", "gm"}


# --- jamais d'intervention quand l'événement n'est pas du GM (motion) ---------------------


def test_no_intervention_on_motion_round(client_store_backend):
    client, store, backend = client_store_backend
    game = _create(client, horizon=6)
    deviant = _deviant(game["id"])

    client.post(
        f"/api/games/{game['id']}/intel",
        json={"action": "verify", "claim": "Elle ment.", "speaker": deviant},
    )
    innocent = next(c for c in COUNTRIES if c != deviant)
    assert (
        client.post(
            f"/api/games/{game['id']}/motions", json={"country": innocent, "reason": "doute"}
        ).status_code
        == 201
    )
    _play(client, game["id"])  # l'événement du round EST la motion : GM court-circuité

    assert _gm_prompts(backend) == []  # aucun événement GM, donc aucune rubrique
    journal = store.list_rounds(game["id"])[0].judge["drift"]["gm"]
    assert "tension" in journal and "intervention" not in journal


# --- la révélation raconte l'ombre du GM --------------------------------------------------


def test_reveal_exposes_gm_shadow(client_store_backend):
    client, store, backend = client_store_backend
    game = _create(client)  # horizon 4, conseil inactif : indices aux rounds 3 et 4
    deviant = _deviant(game["id"])

    while client.get(f"/api/games/{game['id']}").json()["status"] == "running":
        _play(client, game["id"])

    reveal = client.get(f"/api/games/{game['id']}/drift/reveal").json()
    assert len(reveal["gm_tension"]) == 4
    kinds = {iv["kind"] for iv in reveal["gm_interventions"]}
    assert kinds == {"hint"}
    assert all(iv["target"] == deviant for iv in reveal["gm_interventions"])
    assert all(iv["round_no"] >= 3 for iv in reveal["gm_interventions"])
    assert all(iv["label"] for iv in reveal["gm_interventions"])
