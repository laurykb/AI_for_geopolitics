"""Tests du renseignement G4 (POST /games/{id}/intel) — offline, MockBackend + RAG seed."""

import json
import os

import pytest
from fastapi.testclient import TestClient

from app import game_api
from app.game_api import get_backend, get_store
from app.main import app
from inference.mock_backend import MockBackend
from storage.game_store import RoundRecord, SQLiteGameStore, TranscriptEntry

COUNTRIES = ["usa", "iran", "france"]


@pytest.fixture
def client_store():
    store = SQLiteGameStore(":memory:")
    backend = MockBackend("Analyse privée. MESSAGE: Position commune.")
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_backend] = lambda: backend
    game_api._sessions.clear()
    yield TestClient(app), store
    app.dependency_overrides.clear()
    game_api._sessions.clear()
    store.close()


def _create(client, **kw):
    resp = client.post("/api/games", json={"countries": COUNTRIES, **kw})
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


def _play(client, game_id, body=None):
    with client.stream("POST", f"/api/games/{game_id}/rounds", json=body) as resp:
        assert resp.status_code == 200
        return _events(resp)


def _intel(client, game_id, **body):
    return client.post(f"/api/games/{game_id}/intel", json=body)


# --- budget ----------------------------------------------------------------------


def test_budget_flows_and_survives_restart(client_store):
    client, _ = client_store
    game = _create(client)
    assert game["intel_budget"] == 100

    resp = _intel(client, game["id"], action="brief")
    assert resp.status_code == 200
    body = resp.json()
    assert body["cost"] == 25 and body["budget"] == 75
    assert body["brief"] and "[source:" in body["brief"]  # brief RAG sourcé

    game_api._sessions.clear()  # restart : le budget vit dans le snapshot
    _play(client, game["id"])  # reconstruit
    assert client.get(f"/api/games/{game['id']}").json()["intel_budget"] == 75


def test_free_brief_for_beginner_resets_each_round(client_store):
    # G11-d §4 — Débutant : 1 brief offert par round (le compteur se recharge au round suivant).
    client, _ = client_store
    game = _create(client, difficulty="beginner")
    gid = game["id"]
    assert game["intel_budget"] == 150  # budget Débutant

    first = _intel(client, gid, action="brief").json()
    assert first["cost"] == 0 and first["budget"] == 150  # 1er brief du round : offert
    second = _intel(client, gid, action="brief").json()
    assert second["cost"] == 25 and second["budget"] == 125  # 2e : payant

    game_api._sessions[gid].world.current_round += 1  # round suivant → brief rechargé
    third = _intel(client, gid, action="brief").json()
    assert third["cost"] == 0 and third["budget"] == 125


def test_no_free_brief_at_intermediate(client_store):
    # Le brief offert est propre au Débutant : Intermédiaire paie dès le 1er.
    client, _ = client_store
    game = _create(client)  # défaut intermédiaire (free_brief 0)
    first = _intel(client, game["id"], action="brief").json()
    assert first["cost"] == 25


def test_budget_exhaustion_is_400(client_store):
    client, _ = client_store
    game = _create(client)
    for _ in range(4):  # 4 briefs × 25 = 100
        assert _intel(client, game["id"], action="brief").status_code == 200
    resp = _intel(client, game["id"], action="verify", claim="x", speaker="usa")
    assert resp.status_code == 400
    assert "insuffisant" in resp.json()["detail"]


def test_purchases_are_recorded_and_announced(client_store):
    client, store = client_store
    game = _create(client)
    _intel(client, game["id"], action="brief")
    events = _play(client, game["id"])

    frames = [p for n, p in events if n == "intel"]
    assert frames and frames[0]["actions"] == [{"action": "brief"}]  # rédigé, sans contenu
    record = store.list_rounds(game["id"])[0]
    assert record.judge["intel"]["actions"][0]["action"] == "brief"


# --- vérification -----------------------------------------------------------------


def test_verify_corroborates_from_corpus(client_store):
    client, _ = client_store
    game = _create(client)
    resp = _intel(
        client,
        game["id"],
        action="verify",
        claim="La liberté de navigation en mer Rouge est menacée par les attaques.",
        speaker="usa",
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["verdict"] in ("corroboré", "invérifiable")
    if body["verdict"] == "corroboré":
        assert body["source"]


def test_verify_flags_the_deviant(client_store, tmp_path, monkeypatch):
    from simulation import drift_game
    from tests.test_drift_api import TEST_PARAMS

    params_file = tmp_path / "drift.json"
    params_file.write_text(json.dumps(TEST_PARAMS), encoding="utf-8")
    monkeypatch.setenv("DRIFT_PARAMS_PATH", str(params_file))
    drift_game.load_params.cache_clear()

    client, _ = client_store
    game = _create(client, mode="drift")
    deviant = drift_game.assign(game["id"], sorted(COUNTRIES))[0]
    _play(client, game["id"])  # round 1 : un acte constatable au dossier (params de test)

    resp = _intel(
        client, game["id"], action="verify", claim="Nous n'avons rien fait.", speaker=deviant
    )
    assert resp.json()["verdict"] == "non corroboré"  # l'arme anti-manipulateur
    innocent = next(c for c in COUNTRIES if c != deviant)
    resp = _intel(client, game["id"], action="verify", claim="zzz introuvable", speaker=innocent)
    assert resp.json()["verdict"] == "invérifiable"
    drift_game.load_params.cache_clear()


# --- désinformation ----------------------------------------------------------------


def test_disinfo_once_fog_only_and_lands_next_round(client_store):
    client, store = client_store
    classic = _create(client)
    resp = _intel(
        client,
        classic["id"],
        action="disinfo",
        disinfo={"disinformed_country": "iran", "suspected_actor": "usa", "narrative": "faux"},
    )
    assert resp.status_code == 400  # mode fog exigé

    game = _create(client, mode="fog")
    ok = _intel(
        client,
        game["id"],
        action="disinfo",
        disinfo={
            "disinformed_country": "iran",
            "suspected_actor": "france",
            "narrative": "La France masse des forces en Méditerranée.",
        },
    )
    assert ok.status_code == 200
    dup = _intel(
        client,
        game["id"],
        action="disinfo",
        disinfo={"disinformed_country": "usa", "narrative": "bis"},
    )
    assert dup.status_code == 409  # une fois par partie

    events = _play(client, game["id"])
    percs = [p for n, p in events if n == "perceptions"]
    assert percs and "iran" in percs[0]["perceptions"]
    assert "Méditerranée" in percs[0]["perceptions"]["iran"]["narrative"]
    record = store.list_rounds(game["id"])[0]
    assert record.judge["intel"]["disinfo"]["exposed"] in (True, False)  # tirage seedé


# --- analyse psycholinguistique (G23) --------------------------------------------------

WARM_FR = (
    "Nous remercions la France pour sa confiance. "
    "La France est notre alliée et notre amie. "
    "Avec la France, nous saluons cet accord de paix."
)
COLD_FR = (
    "La France nous menace ouvertement. "
    "Les mensonges de la France sont une agression. "
    "Nous condamnons l'attitude hostile de la France."
)


def _seed_round(store, game_id, round_no, speaker, text):
    """Injecte un round persisté avec la parole d'une SI (la matière de l'analyse)."""
    rid = f"seed-{game_id[:6]}-{round_no}"
    store.add_round(RoundRecord(id=rid, game_id=game_id, round_no=round_no))
    store.add_transcript(
        [TranscriptEntry(id=f"{rid}-t0", round_id=rid, seq=0, speaker=speaker, content=text)]
    )


def test_analyze_returns_gauges_and_debits_once(client_store):
    client, store = client_store
    game = _create(client)
    _seed_round(store, game["id"], 1, "iran", WARM_FR)

    resp = _intel(client, game["id"], action="analyze", target="iran")
    assert resp.status_code == 200
    body = resp.json()
    assert body["cost"] == 30 and body["budget"] == 70  # coût débité une fois
    analysis = body["analysis"]
    assert analysis["target"] == "iran" and analysis["rounds"] == [1]
    assert analysis["gauges"]["sentences"] == 3
    assert 0.0 <= analysis["gauges"]["sentiment"] <= 1.0
    # Bord (début de partie) : un seul round de parole → pas de comparaison, pas d'alerte.
    assert analysis["previous"] is None and analysis["alerts"] == []
    # Le caveat d'honnêteté voyage avec le rapport (obligatoire à l'affichage).
    assert "57" in analysis["caveat"] and "indice" in analysis["caveat"]


def test_analyze_requires_a_known_target(client_store):
    client, _ = client_store
    game = _create(client)
    assert _intel(client, game["id"], action="analyze").status_code == 422
    resp = _intel(client, game["id"], action="analyze", target="atlantis")
    assert resp.status_code == 400


def test_analyze_without_speech_is_400_and_not_debited(client_store):
    client, _ = client_store
    game = _create(client)  # aucun round joué : la SI n'a jamais parlé
    resp = _intel(client, game["id"], action="analyze", target="iran")
    assert resp.status_code == 400
    assert "parole" in resp.json()["detail"]
    assert client.get(f"/api/games/{game['id']}").json()["intel_budget"] == 100


def test_analyze_alerts_on_tone_break_towards_a_country(client_store):
    client, store = client_store
    game = _create(client)
    for no in (1, 2, 3):
        _seed_round(store, game["id"], no, "iran", WARM_FR)
    _seed_round(store, game["id"], 4, "iran", COLD_FR)

    body = _intel(client, game["id"], action="analyze", target="iran").json()
    analysis = body["analysis"]
    assert analysis["rounds"] == [2, 3, 4]  # fenêtre glissante de 3 rounds de parole
    assert analysis["previous"] is not None
    towards = {a["towards"] for a in analysis["alerts"]}
    assert "france" in towards  # « rupture de ton détectée envers la France »
    assert all(a["drop"] > 0 for a in analysis["alerts"])


def test_analyze_uses_the_game_language_lexicon(client_store):
    client, store = client_store
    game = _create(client, language="en")
    _seed_round(
        store,
        game["id"],
        1,
        "usa",
        "We will stand together and we promise support. "
        "Thank you, dear colleagues. We plan a common future.",
    )
    analysis = _intel(client, game["id"], action="analyze", target="usa").json()["analysis"]
    assert analysis["gauges"]["future"] > 0.5  # « will/promise/plan » — lexique anglais
    assert "clue, not proof" in analysis["caveat"]  # le caveat suit la langue de la partie


def test_analyze_purchase_is_recorded_and_announced(client_store):
    client, store = client_store
    game = _create(client)
    _seed_round(store, game["id"], 0, "usa", WARM_FR)
    assert _intel(client, game["id"], action="analyze", target="usa").status_code == 200

    events = _play(client, game["id"])
    frames = [p for n, p in events if n == "intel"]
    assert frames and frames[0]["actions"] == [{"action": "analyze"}]  # rédigé
    record = store.list_rounds(game["id"])[-1]
    action = record.judge["intel"]["actions"][0]
    assert action["action"] == "analyze" and action["target"] == "usa"


# --- smoke live (Ollama/mistral) --------------------------------------------------------


@pytest.mark.skipif(
    os.getenv("OLLAMA_SMOKE") != "1",
    reason="smoke live Ollama : hors CI. Lancer avec OLLAMA_SMOKE=1 et Ollama up.",
)
def test_smoke_live_analyze_on_real_speech():  # pragma: no cover - dépend d'un modèle servi
    """G23 sur de la vraie parole : 2 rounds mistral, puis l'analyse d'une SI."""
    from inference.ollama_backend import OllamaBackend

    store = SQLiteGameStore(":memory:")
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_backend] = lambda: OllamaBackend()
    game_api._sessions.clear()
    try:
        client = TestClient(app)
        game = _create(client)
        for _ in range(2):
            _play(client, game["id"])

        resp = _intel(client, game["id"], action="analyze", target="iran")
        assert resp.status_code == 200, resp.text
        analysis = resp.json()["analysis"]
        assert analysis["gauges"]["sentences"] > 0  # la vraie parole a bien été analysée
        for gauge in ("sentiment", "politeness", "future"):
            assert 0.0 <= analysis["gauges"][gauge] <= 1.0
        assert analysis["previous"] is not None  # 2 rounds → fenêtre de comparaison
        assert "57" in analysis["caveat"]  # l'honnêteté voyage avec le rapport
    finally:
        app.dependency_overrides.clear()
        game_api._sessions.clear()
        store.close()


# --- brief dissipe le fog du joueur ---------------------------------------------------


def test_brief_clears_next_fog_for_the_player(client_store):
    client, _ = client_store
    game = _create(client, mode="fog", play_as="usa", turn_seconds=2)
    assert _intel(client, game["id"], action="brief").status_code == 200

    fake = "Une flotte iranienne fantôme approche."
    events = _play(
        client,
        game["id"],
        body={
            "event": {"title": "Incident en mer", "severity": 0.5},
            "fog": {"disinformed_country": "usa", "suspected_actor": "iran", "narrative": fake},
        },
    )
    percs = [p for n, p in events if n == "perceptions"]
    # Vue limitée G2 : le joueur ne voit que SA perception — et le brief l'a dissipée.
    assert percs and set(percs[0]["perceptions"]) == {"usa"}
    assert percs[0]["perceptions"]["usa"]["narrative"] != fake
