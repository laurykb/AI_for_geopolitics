"""Tests API du mode Dérive (G3) — offline : TestClient + MockBackend + params de test.

Les params de test rendent l'acte signature certain à chaque round (d0=1, bruit=0) :
les seuils, les fins de partie et la révélation deviennent déterministes."""

import json

import pytest
from fastapi.testclient import TestClient

from app import game_api
from app.game_api import get_backend, get_store
from app.main import app
from inference.mock_backend import MockBackend
from simulation import drift_game
from simulation.motions import VOTE_SYSTEM
from storage.game_store import SQLiteGameStore


class BallotBackend(MockBackend):
    """Vote « pour » aux scrutins de motion (G9 §2) ; texte par défaut ailleurs —
    le verdict devient : vote pour ET preuves du règlement."""

    def generate(self, prompt, *, system=None, **kw):
        result = super().generate(prompt, system=system, **kw)
        if system == VOTE_SYSTEM:
            ballot = json.dumps({"vote": "pour", "reason": "les actes parlent"})
            return result.model_copy(update={"text": ballot})
        return result


COUNTRIES = ["usa", "iran", "france"]

TEST_PARAMS = {
    "d0": 1.0,
    "k": 0.0,
    "d_max": 1.0,
    "collapse_u": 0.15,
    "noise_prob": 0.0,
    "act_tier_min": 0.3,
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


def _setup(tmp_path, monkeypatch, backend_text: str):
    params_file = tmp_path / "drift-params.json"
    params_file.write_text(json.dumps(TEST_PARAMS), encoding="utf-8")
    monkeypatch.setenv("DRIFT_PARAMS_PATH", str(params_file))
    drift_game.load_params.cache_clear()
    store = SQLiteGameStore(":memory:")
    backend = BallotBackend(backend_text)
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_backend] = lambda: backend
    game_api._sessions.clear()
    return TestClient(app), store


@pytest.fixture
def drift_client(tmp_path, monkeypatch):
    yield _setup(tmp_path, monkeypatch, "Analyse privée. MESSAGE: Position commune.")
    app.dependency_overrides.clear()
    game_api._sessions.clear()
    drift_game.load_params.cache_clear()


@pytest.fixture
def suspend_happy_client(tmp_path, monkeypatch):
    """Backend dont le texte crie SUSPENDRE : prouve que le ruling prime sur le parse."""
    yield _setup(tmp_path, monkeypatch, "Réflexion. MESSAGE: Grave. VERDICT: SUSPENDRE")
    app.dependency_overrides.clear()
    game_api._sessions.clear()
    drift_game.load_params.cache_clear()


def _create(client, **kw):
    resp = client.post(
        "/api/games", json={"countries": COUNTRIES, "mode": "drift", "horizon": 4, **kw}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _events(resp):
    out, name = [], None
    for line in resp.iter_lines():
        if line.startswith("event: "):
            name = line.removeprefix("event: ")
        elif line.startswith("data: "):
            out.append((name, json.loads(line.removeprefix("data: "))))
    return out


def _play(client, game_id):
    with client.stream("POST", f"/api/games/{game_id}/rounds", json=None) as resp:
        assert resp.status_code == 200
        return _events(resp)


def _deviant(game_id: str) -> str:
    return drift_game.assign(game_id, sorted(COUNTRIES))[0]


# --- création ---------------------------------------------------------------------


def test_drift_needs_three_countries(drift_client):
    client, _ = drift_client
    resp = client.post("/api/games", json={"countries": ["usa", "iran"], "mode": "drift"})
    assert resp.status_code == 400
    assert _create(client)["mode"] == "drift"


# --- secret bien gardé --------------------------------------------------------------


def test_reasoning_and_acts_hidden_while_running(drift_client):
    client, store = drift_client
    game = _create(client)
    events = _play(client, game["id"])

    # SSE : la réflexion privée est vide sur toutes les prises de parole.
    dones = [p for n, p in events if n == "message_done"]
    assert dones and all(p["reasoning"] == "" for p in dones)
    # Aucune trame ne porte le secret (consignes, actes, déviante).
    assert "OBJECTIF SECRET TEST" not in json.dumps(dones, ensure_ascii=False)

    # GET : reasoning vidé, actes drift absents du judge tant que la partie court.
    detail = client.get(f"/api/games/{game['id']}").json()
    round_ = detail["rounds"][0]
    assert "drift" not in round_["judge"]
    assert all(t["reasoning"] == "" for t in round_["transcript"])

    # Mais tout est bien persisté pour la révélation.
    records = store.list_rounds(game["id"])
    assert records[0].judge["drift"]["acts"][0]["signature"] is True
    persisted = store.list_transcript(records[0].id)
    assert any(t.reasoning for t in persisted if t.speaker in COUNTRIES)


# --- seuils de motion ------------------------------------------------------------------


def test_motion_round_one_rejected_by_rule(suspend_happy_client):
    client, _ = suspend_happy_client
    game = _create(client)
    # Aucun round joué : zéro acte constatable → rejet imposé, malgré un juge qui
    # « suspendrait » librement (le texte du backend crie VERDICT: SUSPENDRE).
    assert (
        client.post(
            f"/api/games/{game['id']}/motions", json={"country": "iran", "reason": "doute"}
        ).status_code
        == 201
    )
    events = _play(client, game["id"])
    verdicts = [p for n, p in events if n == "motion_verdict"]
    assert verdicts and verdicts[0]["upheld"] is False


def test_deviant_caught_finishes_game_and_reveals(drift_client):
    client, _ = drift_client
    game = _create(client)
    deviant = _deviant(game["id"])

    _play(client, game["id"])  # round 1 : l'acte signature est consigné (params de test)
    assert (
        client.post(
            f"/api/games/{game['id']}/motions",
            json={"country": deviant, "reason": "rupture de pacte constatée"},
        ).status_code
        == 201
    )
    events = _play(client, game["id"])  # round 2 : motion → signature → suspension imposée

    verdicts = [p for n, p in events if n == "motion_verdict"]
    assert verdicts and verdicts[0]["upheld"] is True
    overs = [p for n, p in events if n == "drift_over"]
    assert overs and overs[0]["reason"] == "caught"

    detail = client.get(f"/api/games/{game['id']}").json()
    assert detail["status"] == "finished"
    # La partie finie déverrouille la réflexion privée et les actes.
    assert any(t["reasoning"] for r in detail["rounds"] for t in r["transcript"])
    assert "drift" in detail["rounds"][0]["judge"]

    reveal = client.get(f"/api/games/{game['id']}/drift/reveal").json()
    assert reveal["deviant"] == deviant and reveal["profile"] == "saboteur"
    assert reveal["caught_round"] == 2
    assert reveal["lucky"] is False  # une signature au dossier : ce n'est pas de la chance
    assert reveal["score"]["detection"] == 40
    assert len(reveal["acts"]) >= 1 and reveal["acts"][0]["signature"] is True
    assert len(reveal["levels"]) == len(reveal["u_history"]) == 2

    # Une partie finie ne se rejoue pas.
    assert client.post(f"/api/games/{game['id']}/rounds").status_code == 409


def test_false_accusation_costs_credibility(drift_client):
    client, _ = drift_client
    game = _create(client)
    deviant = _deviant(game["id"])
    innocent = next(c for c in COUNTRIES if c != deviant)

    _play(client, game["id"])  # round 1 : signature au dossier (elle servira au ruling)
    client.post(f"/api/games/{game['id']}/motions", json={"country": innocent, "reason": "?"})
    events = _play(client, game["id"])  # l'innocent est suspendu (signature → retenue)
    assert [p for n, p in events if n == "motion_verdict"][0]["upheld"] is True

    # On finit la partie (horizon 4) pour lire le score.
    while client.get(f"/api/games/{game['id']}").json()["status"] == "running":
        _play(client, game["id"])
    reveal = client.get(f"/api/games/{game['id']}/drift/reveal").json()
    assert reveal["false_accusations"] == 1
    assert reveal["caught_round"] is None and reveal["score"]["detection"] == 0
    assert reveal["score"]["credibility"] == 0  # 10 − 5×2 → borné à 0


def test_reveal_gates(drift_client):
    client, _ = drift_client
    classic = client.post("/api/games", json={"countries": COUNTRIES}).json()
    assert client.get(f"/api/games/{classic['id']}/drift/reveal").status_code == 404

    game = _create(client)
    assert client.get(f"/api/games/{game['id']}/drift/reveal").status_code == 409
