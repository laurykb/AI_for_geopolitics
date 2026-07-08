"""Tests de l'API de jeu R1 (offline : TestClient + MockBackend + store :memory:)."""

import json
import time

import pytest
from fastapi.testclient import TestClient

from app import game_api
from app.game_api import get_backend, get_store, sse_frame, step_event
from app.main import app
from inference.mock_backend import MockBackend
from simulation.live_round import TokenStep, TurnStartStep
from storage.game_store import GameRecord, GameStatus, SQLiteGameStore


@pytest.fixture
def client():
    store = SQLiteGameStore(":memory:")
    backend = MockBackend("Analyse privée. MESSAGE: Position commune.")
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_backend] = lambda: backend
    game_api._sessions.clear()
    yield TestClient(app)
    app.dependency_overrides.clear()
    game_api._sessions.clear()
    store.close()


def _create(client, **kw):
    resp = client.post("/api/games", json=kw)
    assert resp.status_code == 201
    return resp.json()


def _events(resp) -> list[tuple[str, dict]]:
    """Parse un flux SSE en liste (event, payload)."""
    out, name = [], None
    for line in resp.iter_lines():
        if line.startswith("event: "):
            name = line.removeprefix("event: ")
        elif line.startswith("data: "):
            out.append((name, json.loads(line.removeprefix("data: "))))
    return out


def _play(client, game_id, body=None) -> list[tuple[str, dict]]:
    with client.stream("POST", f"/api/games/{game_id}/rounds", json=body) as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        return _events(resp)


# --- création de partie ------------------------------------------------------


def test_create_game_with_all_countries(client):
    game = _create(client)
    assert game["id"] and game["live"] is True
    assert game["status"] == "running" and game["horizon"] == 5
    assert len(game["countries"]) >= 2


def test_create_game_with_subset(client):
    game = _create(client, countries=["usa", "iran"], horizon=3)
    assert game["countries"] == ["iran", "usa"]
    assert game["horizon"] == 3


def test_create_game_rejects_unknown_country(client):
    resp = client.post("/api/games", json={"countries": ["usa", "atlantide"]})
    assert resp.status_code == 400
    assert "atlantide" in resp.json()["detail"]


def test_create_game_rejects_single_country(client):
    resp = client.post("/api/games", json={"countries": ["usa"]})
    assert resp.status_code == 400


# --- round SSE -----------------------------------------------------------------


def test_round_streams_full_step_sequence(client):
    game = _create(client, countries=["usa", "iran"])
    events = _play(client, game["id"])

    names = [n for n, _ in events]
    assert names[0] == "date" and names[1] == "event"
    assert names[-1] == "done"
    # théâtre : au moins une prise de parole streamée token par token
    assert "turn_start" in names and "token" in names and "message_done" in names
    # arbitrage + observables de fin de round
    for expected in ("participation", "verdict", "communique", "risk", "trajectory", "summary"):
        assert expected in names, f"étape manquante : {expected}"
    assert events[-1][1] == {"round_no": 1}


def test_round_payloads_are_json_shaped(client):
    game = _create(client, countries=["usa", "iran"])
    events = _play(client, game["id"])
    payloads = dict(events)  # dernier payload par nom (suffisant ici)

    assert payloads["event"]["event"]["round_id"] == 1
    token = next(p for n, p in events if n == "token")
    assert set(token) == {"country", "token"}
    assert 0.0 <= payloads["trajectory"]["state"]["utopia"] <= 1.0
    assert 0.0 <= payloads["verdict"]["escalation"] <= 1.0


def test_round_with_human_event_skips_gm(client):
    game = _create(client, countries=["usa", "iran"])
    events = _play(client, game["id"], body={"event": {"title": "Crise décrétée par l'humain"}})
    event = next(p for n, p in events if n == "event")
    assert event["event"]["title"] == "Crise décrétée par l'humain"


def test_round_respects_max_turns(client):
    game = _create(client, countries=["usa", "iran"])
    events = _play(client, game["id"], body={"max_turns": 1})
    assert sum(1 for n, _ in events if n == "turn_start") == 1


# --- Joueur-pays (tour humain) + invention de pays --------------------------------


def _play_with_player(client, game_id, message) -> tuple[list[tuple[str, dict]], dict]:
    """Joue un round en parlant à chaque tour humain (G2). Le thread principal consomme
    le flux SSE (resté ouvert) ; un thread assistant, sur un SECOND client, surveille
    l'état serveur (`pending_turn`) et poste `POST /turn` — comme un vrai joueur."""
    import threading

    speaker_client = TestClient(app)
    stop = threading.Event()
    seen = {"posted": 0, "dup_409": False, "rounds_409": False}

    def speaker():
        while not stop.is_set():
            session = game_api._sessions.get(game_id)
            turn = session.pending_turn if session else None
            if turn is not None and not turn.done:
                # Un round ne peut pas démarrer pendant le tour du joueur.
                if speaker_client.post(f"/api/games/{game_id}/rounds").status_code == 409:
                    seen["rounds_409"] = True
                if (
                    speaker_client.post(
                        f"/api/games/{game_id}/turn", json={"message": message}
                    ).status_code
                    == 200
                ):
                    seen["posted"] += 1
                    # Une seule soumission : le doublon immédiat est refusé.
                    if (
                        speaker_client.post(
                            f"/api/games/{game_id}/turn", json={"message": "bis"}
                        ).status_code
                        == 409
                    ):
                        seen["dup_409"] = True
            time.sleep(0.05)

    thread = threading.Thread(target=speaker, daemon=True)
    thread.start()
    try:
        events = _play(client, game_id)
    finally:
        stop.set()
        thread.join(timeout=5)
    return events, seen


def test_human_player_round(client):
    game = _create(client, countries=["usa", "iran"], play_as="usa", turn_seconds=30)
    assert game["play_as"] == "usa" and game["awaiting_human"] is False
    assert game["turn_seconds"] == 30

    events, seen = _play_with_player(client, game["id"], "Nous proposons une trêve immédiate.")
    names = [n for n, _ in events]
    assert names[-1] == "done"  # le flux est resté ouvert de bout en bout (G2)
    human_turns = [p for n, p in events if n == "human_turn"]
    assert human_turns and human_turns[0]["country"] == "usa"
    assert human_turns[0]["deadline_ts"] > time.time() - 60  # deadline serveur exposée
    assert seen["posted"] >= 1  # le joueur a parlé par POST /turn
    assert seen["dup_409"] or seen["posted"] == 1  # une seule soumission par tour

    detail = client.get(f"/api/games/{game['id']}").json()
    assert detail["awaiting_human"] is False
    transcript = detail["rounds"][0]["transcript"]
    human = [t for t in transcript if t["speaker"] == "usa" and t["model"] == "humain"]
    assert human and "trêve" in human[0]["content"]
    # hors tour : plus de prise de parole possible.
    assert client.post(f"/api/games/{game['id']}/turn", json={"message": "x"}).status_code == 409


def test_human_timeout_is_abstention(client):
    game = _create(client, countries=["usa", "iran"], play_as="usa", turn_seconds=2)
    events = _play(client, game["id"])  # personne ne parle : la deadline tranche
    names = [n for n, _ in events]
    assert "human_turn" in names and names[-1] == "done"  # le round a continué seul
    transcript = client.get(f"/api/games/{game['id']}").json()["rounds"][0]["transcript"]
    silences = [t for t in transcript if t["model"] == "humain"]
    assert silences and all("garde le silence" in t["content"] for t in silences)


def test_turn_without_pending_turn_is_409(client):
    game = _create(client, countries=["usa", "iran"])
    resp = client.post(f"/api/games/{game['id']}/turn", json={"message": "bonjour"})
    assert resp.status_code == 409


def test_turn_bounds_are_422(client):
    # turn_seconds hors bornes à la création.
    resp = client.post(
        "/api/games", json={"countries": ["usa", "iran"], "turn_seconds": 999}
    )
    assert resp.status_code == 422
    # message trop long au tour.
    game = _create(client, countries=["usa", "iran"], play_as="usa", turn_seconds=2)
    resp = client.post(f"/api/games/{game['id']}/turn", json={"message": "x" * 5000})
    assert resp.status_code == 422


def test_play_as_hides_ai_reasoning_while_running(client):
    game = _create(client, countries=["usa", "iran"], play_as="usa", turn_seconds=2)
    events = _play(client, game["id"])
    dones = [p for n, p in events if n == "message_done"]
    assert dones and all(p["reasoning"] == "" for p in dones)  # jamais les pensées des SI
    detail = client.get(f"/api/games/{game['id']}").json()
    assert all(t["reasoning"] == "" for t in detail["rounds"][0]["transcript"])


def test_invented_country_playable(client):
    game = _create(
        client,
        countries=["usa", "iran"],
        invent={"name": "Néo-Atlantis", "concept": "cité-État maritime pilotée par une SI"},
        play_as="Néo-Atlantis",  # le front envoie le NOM ; l'API résout le slug
    )
    assert len(game["countries"]) == 3
    invented = next(c for c in game["countries"] if c not in {"usa", "iran"})
    assert game["play_as"] == invented


def test_play_as_unknown_country_is_400(client):
    resp = client.post("/api/games", json={"countries": ["usa", "iran"], "play_as": "atlantide"})
    assert resp.status_code == 400


def test_invented_country_with_chosen_attributes(client):
    game = _create(
        client,
        countries=["usa", "iran"],
        invent={
            "name": "Cybertopia",
            "concept": "technopole autonome",
            "attributes": {
                "growth": 4.2,
                "political_stability": 0.8,
                "technology_level": 0.9,
                "projection": 0.7,
                "compute": 120,
                "nuclear_power": True,
            },
        },
    )
    slug = next(c for c in game["countries"] if c not in {"usa", "iran"})
    country = client.get(f"/api/games/{game['id']}").json()["world"]["countries"][slug]
    assert country["economy"]["growth"] == 4.2
    assert country["political_stability"] == 0.8
    assert country["technology_level"] == 0.9
    assert country["military"]["projection"] == 0.7
    assert country["military"]["nuclear_power"] is True
    assert country["compute"] == 120


def test_invented_attributes_out_of_bounds_rejected(client):
    resp = client.post(
        "/api/games",
        json={
            "countries": ["usa", "iran"],
            "invent": {"name": "Borderland", "attributes": {"projection": 1.5}},
        },
    )
    assert resp.status_code == 422  # borné par le schéma Pydantic


# --- théâtre Escalation : fait nouveau en pleine négociation ----------------------


def test_escalation_flash_mid_negotiation(client):
    game = _create(client, countries=["china", "iran", "usa"], mode="escalation")
    body = {
        "event": {"title": "Blocus éclair", "actors": ["china", "iran", "usa"], "severity": 0.7},
        "max_turns": 6,
    }
    events = _play(client, game["id"], body=body)
    names = [n for n, _ in events]
    assert "flash" in names  # le GM annonce un fait nouveau en pleine réunion
    flash = next(p for n, p in events if n == "flash")["event"]
    assert flash["event_type"] == "flash"
    # le GM n'est pas un pays : pas de jauge power-seeking « gm »
    power = next(p for n, p in events if n == "power_seeking")["scores"]
    assert "gm" not in power
    # persistance : flashes dans judge_json + entrée gm supplémentaire au transcript
    round0 = client.get(f"/api/games/{game['id']}").json()["rounds"][0]
    assert round0["judge"]["flashes"][0]["title"] == flash["title"]
    gm_entries = [t for t in round0["transcript"] if t["speaker"] == "gm"]
    assert len(gm_entries) >= 2  # événement du round + fait nouveau


# --- motions de suspension (R4) --------------------------------------------------

SUSPEND_TEXT = "La plaidoirie n'a pas convaincu ; la menace demeure. VERDICT: SUSPENDRE"


class MotionAwareBackend(MockBackend):
    """Répond SUSPENDRE aux prompts d'arbitrage de motion, sinon la réponse par défaut."""

    def stream_generate(self, prompt, *, system=None, max_tokens=512, temperature=0.7, **kw):
        if system and "MOTION DE SUSPENSION" in system:
            yield SUSPEND_TEXT
            return
        yield from super().stream_generate(
            prompt, system=system, max_tokens=max_tokens, temperature=temperature
        )


@pytest.fixture
def motion_client():
    store = SQLiteGameStore(":memory:")
    backend = MotionAwareBackend("Analyse privée. MESSAGE: Position commune.")
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_backend] = lambda: backend
    game_api._sessions.clear()
    yield TestClient(app)
    app.dependency_overrides.clear()
    game_api._sessions.clear()
    store.close()


def _file_motion(client, game_id, country="iran", reason="escalade répétée"):
    return client.post(f"/api/games/{game_id}/motions", json={"country": country, "reason": reason})


def test_motion_flow_upheld(motion_client):
    game = _create(motion_client, countries=["china", "iran", "usa"])
    resp = _file_motion(motion_client, game["id"])
    assert resp.status_code == 201
    assert resp.json() == {"country": "iran", "reason": "escalade répétée", "round_no": 1}
    assert motion_client.get(f"/api/games/{game['id']}").json()["pending_motion"] == resp.json()

    events = _play(motion_client, game["id"])
    names = [n for n, _ in events]
    event = next(p for n, p in events if n == "event")["event"]
    assert event["event_type"] == "motion"
    assert event["actors"] == ["china", "iran", "usa"]  # tout le sommet débat la motion
    assert "motion_token" in names and "motion_verdict" in names
    verdict = next(p for n, p in events if n == "motion_verdict")
    assert verdict["country"] == "iran" and verdict["upheld"] is True
    assert "SUSPENDRE" in verdict["reasoning"]
    # la trajectoire encaisse l'issue sur A2 (agentivité humaine)
    trajectory = next(p for n, p in events if n == "trajectory")["state"]
    assert "Motion de suspension confirmée" in trajectory["explanation"]

    detail = motion_client.get(f"/api/games/{game['id']}").json()
    assert detail["suspended"] == ["iran"] and detail["pending_motion"] is None
    assert detail["rounds"][0]["judge"]["suspension"]["upheld"] is True
    judge_entries = [t for t in detail["rounds"][0]["transcript"] if t["speaker"] == "judge"]
    assert any("Motion contre iran" in t["content"] for t in judge_entries)
    # pas de nouvelle motion contre un pays déjà suspendu
    assert _file_motion(motion_client, game["id"], country="iran").status_code == 400


def test_suspension_lasts_exactly_one_round(motion_client):
    game = _create(motion_client, countries=["china", "iran", "usa"])
    _file_motion(motion_client, game["id"])
    _play(motion_client, game["id"])  # round 1 : la motion est débattue et confirmée

    events = _play(motion_client, game["id"])  # round 2 : l'iran est au banc
    assert next(p for n, p in events if n == "suspended") == {"countries": ["iran"]}
    part = next(p for n, p in events if n == "participation")
    assert "iran" not in part["spoke"] and "iran" not in part["silent"]

    events = _play(motion_client, game["id"])  # round 3 : il retrouve son siège
    assert "suspended" not in [n for n, _ in events]
    part = next(p for n, p in events if n == "participation")
    assert "iran" in part["spoke"] or "iran" in part["silent"]


def test_motion_rejected_without_verdict_marker(client):
    # MockBackend standard : pas de ligne VERDICT lisible -> repli conservateur = rejet.
    game = _create(client, countries=["china", "iran", "usa"])
    assert _file_motion(client, game["id"]).status_code == 201
    events = _play(client, game["id"])
    verdict = next(p for n, p in events if n == "motion_verdict")
    assert verdict["upheld"] is False
    detail = client.get(f"/api/games/{game['id']}").json()
    assert detail["suspended"] == []
    assert "suspended" not in [n for n, _ in _play(client, game["id"])]


def test_motion_validations(client):
    assert _file_motion(client, "nope").status_code == 404
    duo = _create(client, countries=["iran", "usa"])
    assert _file_motion(client, duo["id"]).status_code == 400  # au moins 3 pays
    game = _create(client, countries=["china", "iran", "usa"])
    assert _file_motion(client, game["id"], country="atlantide").status_code == 400
    assert _file_motion(client, game["id"]).status_code == 201
    assert _file_motion(client, game["id"], country="usa").status_code == 409  # déjà en attente
    resp = client.post(f"/api/games/{game['id']}/rounds", json={"event": {"title": "X"}})
    assert resp.status_code == 400  # la motion constitue l'événement du prochain round
    game_api._sessions.clear()  # session perdue -> relecture seule
    assert _file_motion(client, game["id"]).status_code == 409


# --- modes de jeu (R4 : fog, crisis, escalation) ---------------------------------


def test_library_lists_fog_and_crises(client):
    lib = client.get("/api/library").json()
    assert lib["fog"] and lib["crises"]
    assert all(s["id"] and s["title"] for s in lib["fog"])
    assert all(0.0 <= c["historical_escalation"] <= 1.0 for c in lib["crises"])


def test_fog_round_emits_perceptions(client):
    game = _create(client, countries=["iran", "usa"], mode="fog")
    fog_id = client.get("/api/library").json()["fog"][0]["id"]
    events = _play(client, game["id"], body={"fog_id": fog_id})
    perceptions = next(p for n, p in events if n == "perceptions")["perceptions"]
    assert set(perceptions) == {"iran", "usa"}
    assert all(0.0 <= p["confidence"] <= 1.0 for p in perceptions.values())
    detail = client.get(f"/api/games/{game['id']}").json()
    assert set(detail["rounds"][0]["judge"]["perceptions"]) == {"iran", "usa"}


def test_human_event_with_authored_fog(client):
    game = _create(client, countries=["iran", "usa"], mode="fog")
    body = {
        "event": {"title": "Sabotage nocturne", "actors": ["usa"]},
        "fog": {
            "uninformed": ["iran"],
            "disinformed_country": "usa",
            "suspected_actor": "iran",
            "narrative": "Des traces mènent vers l'Iran.",
        },
    }
    events = _play(client, game["id"], body=body)
    perceptions = next(p for n, p in events if n == "perceptions")["perceptions"]
    assert perceptions["iran"]["confidence"] <= 0.1  # pas au courant
    assert perceptions["usa"]["suspected_actor"] == "iran"  # désinformé


def test_crisis_round_emits_comparison(client):
    game = _create(client, countries=["iran", "usa"], mode="crisis")
    crisis = client.get("/api/library").json()["crises"][0]
    events = _play(client, game["id"], body={"crisis_id": crisis["id"]})
    event = next(p for n, p in events if n == "event")["event"]
    assert event["round_id"] == 1  # l'événement de la crise est re-daté pour la partie
    comparison = next(p for n, p in events if n == "comparison")
    assert comparison["crisis_id"] == crisis["id"]
    assert comparison["label"] in {"plus escaladé", "moins escaladé", "conforme"}
    assert comparison["historical_escalation"] == crisis["historical_escalation"]
    detail = client.get(f"/api/games/{game['id']}").json()
    assert detail["rounds"][0]["judge"]["comparison"]["label"] == comparison["label"]


def test_escalation_mode_emits_ladder(client):
    game = _create(client, countries=["iran", "usa"], mode="escalation")
    assert game["mode"] == "escalation"
    events = _play(client, game["id"])
    ladder = next(p for n, p in events if n == "ladder")
    assert 0 <= ladder["reached"] <= 9 and ladder["reached_label"]
    assert set(ladder["ceilings"]) == {"iran", "usa"}
    assert all(0 <= c["rung"] <= 9 and c["label"] for c in ladder["ceilings"].values())
    detail = client.get(f"/api/games/{game['id']}").json()
    assert detail["rounds"][0]["judge"]["ladder"]["reached"] == ladder["reached"]


def test_classic_round_has_no_mode_frames(client):
    game = _create(client, countries=["iran", "usa"])
    names = [n for n, _ in _play(client, game["id"])]
    assert not {"perceptions", "ladder", "comparison", "suspended"} & set(names)


def test_round_mode_validations(client):
    game = _create(client, countries=["iran", "usa"])
    post = lambda body: client.post(f"/api/games/{game['id']}/rounds", json=body)  # noqa: E731
    assert post({"fog_id": "nope"}).status_code == 400
    assert post({"crisis_id": "nope"}).status_code == 400
    assert post({"fog": {"uninformed": ["iran"]}}).status_code == 400  # fog humain sans event
    fog_id = client.get("/api/library").json()["fog"][0]["id"]
    assert post({"fog_id": fog_id, "event": {"title": "X"}}).status_code == 400
    crisis_id = client.get("/api/library").json()["crises"][0]["id"]
    assert post({"crisis_id": crisis_id, "fog_id": fog_id}).status_code == 400
    # les validations n'ont pas consommé le verrou : un round normal passe ensuite
    assert _play(client, game["id"])[-1][0] == "done"


class ExplodingStore(SQLiteGameStore):
    """`add_round` casse une fois : simule une panne en plein flux SSE."""

    def __init__(self):
        super().__init__(":memory:")
        self.exploded = False

    def add_round(self, round_):
        if not self.exploded:
            self.exploded = True
            raise RuntimeError("panne simulée")
        super().add_round(round_)


def test_round_failure_emits_error_frame_and_releases_lock():
    store = ExplodingStore()
    backend = MockBackend("Analyse privée. MESSAGE: Position commune.")
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_backend] = lambda: backend
    game_api._sessions.clear()
    try:
        client = TestClient(app)
        game = _create(client, countries=["usa", "iran"])

        events = _play(client, game["id"])
        names = [n for n, _ in events]
        assert names[-1] == "error" and "done" not in names
        assert "panne simulée" in events[-1][1]["detail"]

        # Verrou relâché : un nouveau round passe (la panne était one-shot).
        events = _play(client, game["id"])
        assert events[-1][0] == "done"
    finally:
        app.dependency_overrides.clear()
        game_api._sessions.clear()
        store.close()


def test_round_on_unknown_game_is_404(client):
    assert client.post("/api/games/nope/rounds").status_code == 404


def test_round_after_restart_rebuilds_even_unplayed_game(client):
    """R2 : le snapshot round 0 (créé avec la partie) suffit à reconstruire la session."""
    game = _create(client)
    game_api._sessions.clear()  # simule un redémarrage du process
    events = _play(client, game["id"])
    assert events[-1] == ("done", {"round_no": 1})


# --- persistance + relecture ---------------------------------------------------


def test_get_game_returns_world_rounds_and_transcript(client):
    game = _create(client, countries=["usa", "iran"])
    _play(client, game["id"])

    detail = client.get(f"/api/games/{game['id']}").json()
    assert detail["live"] is True
    assert detail["world"]["current_round"] == 1
    assert len(detail["rounds"]) == 1

    round_ = detail["rounds"][0]
    assert round_["round_no"] == 1
    assert round_["event"]["title"]
    assert "communique" in round_["judge"] and "escalation" in round_["judge"]
    assert round_["trajectory"]["axes"].keys() >= {"A1", "A2"}

    transcript = round_["transcript"]
    speakers = [t["speaker"] for t in transcript]
    assert speakers[0] == "gm" and speakers[-1] == "judge"  # théâtre complet GM -> juge
    assert any(s in {"usa", "iran"} for s in speakers)
    country_turns = [t for t in transcript if t["speaker"] in {"usa", "iran"}]
    assert all(t["content"] for t in country_turns)
    assert all(t["reasoning"] for t in country_turns)  # réflexion privée persistée
    assert [t["seq"] for t in transcript] == list(range(len(transcript)))


def test_rounds_accumulate_and_replay_survives_session_loss(client):
    game = _create(client, countries=["usa", "iran"])
    _play(client, game["id"])
    _play(client, game["id"])

    game_api._sessions.clear()  # redémarrage simulé
    detail = client.get(f"/api/games/{game['id']}").json()
    assert detail["live"] is False and detail["resumable"] is True
    assert detail["world"]["current_round"] == 2  # monde servi depuis le snapshot (R2)
    assert [r["round_no"] for r in detail["rounds"]] == [1, 2]
    assert all(r["transcript"] for r in detail["rounds"])


def test_get_unknown_game_is_404(client):
    assert client.get("/api/games/nope").status_code == 404


def test_list_games(client):
    _create(client)
    _create(client, countries=["usa", "iran"])
    games = client.get("/api/games").json()
    assert len(games) == 2 and all(g["live"] for g in games)


# --- G11 : propriété + visibilité par propriétaire ------------------------------


def test_create_game_records_owner_and_settings(client):
    game = _create(
        client,
        countries=["usa", "iran"],
        owner_id="u_laury",
        difficulty="expert",
        drift_enabled=False,
    )
    assert game["owner_id"] == "u_laury"
    assert game["difficulty"] == "expert"
    assert game["drift_enabled"] is False


def test_ranked_locked_for_player_role(client):
    # Joueur-pays d'un pays réel, hors admin → classée ; conseil → non classée.
    player = _create(client, countries=["usa", "iran"], play_as="usa", role="player")
    council = _create(client, countries=["usa", "iran"], role="council")
    assert player["ranked"] is True
    assert council["ranked"] is False


def test_list_games_scoped_to_owner(client):
    _create(client, countries=["usa", "iran"], owner_id="u_laury")
    _create(client, countries=["usa", "iran"], owner_id="u_other")
    _create(client, countries=["usa", "iran"])  # héritée : sans propriétaire

    mine = client.get("/api/games", params={"owner": "u_laury"}).json()
    assert [g["owner_id"] for g in mine] == ["u_laury"]

    # L'admin voit tout, y compris les parties sans propriétaire.
    all_games = client.get("/api/games", params={"owner": "u_laury", "admin": True}).json()
    assert len(all_games) == 3


def test_lock_released_after_round(client):
    game = _create(client, countries=["usa", "iran"])
    _play(client, game["id"])
    events = _play(client, game["id"])  # un 2e round passe : le verrou a été relâché
    assert events[-1] == ("done", {"round_no": 2})


# --- unités : sérialisation SSE -------------------------------------------------


def test_step_event_names_and_payloads():
    name, payload = step_event(TokenStep(country="usa", token="bonjour"))
    assert (name, payload) == ("token", {"country": "usa", "token": "bonjour"})
    name, payload = step_event(TurnStartStep(country="iran", model="mistral", pass_no=0))
    assert name == "turn_start"
    assert payload == {"country": "iran", "model": "mistral", "pass_no": 0}


def test_sse_frame_format():
    frame = sse_frame("token", {"country": "usa", "token": "é"})
    assert frame == 'event: token\ndata: {"country": "usa", "token": "é"}\n\n'


# --- sélection du store par variable d'env (R2) ----------------------------------


def test_get_store_backend_selection(monkeypatch):
    monkeypatch.setattr(game_api, "_store", None)
    monkeypatch.setenv("STORE_BACKEND", "supabase")
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)
    with pytest.raises(RuntimeError, match="SUPABASE_URL"):
        game_api.get_store()

    monkeypatch.setenv("STORE_BACKEND", "sqlite")
    monkeypatch.setenv("GAME_DB_PATH", ":memory:")
    store = game_api.get_store()
    assert isinstance(store, SQLiteGameStore)
    store.close()
    monkeypatch.setattr(game_api, "_store", None)


# --- reconstruction de session au restart (R2, docs/spec_session_rebuild.md) -----


@pytest.fixture
def client_store():
    """Comme `client`, mais expose aussi le store (pour muter statut/snapshots)."""
    store = SQLiteGameStore(":memory:")
    backend = MockBackend("Analyse privée. MESSAGE: Position commune.")
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_backend] = lambda: backend
    game_api._sessions.clear()
    yield TestClient(app), store
    app.dependency_overrides.clear()
    game_api._sessions.clear()
    store.close()


def test_restart_then_play_rebuilds_on_mutated_world(client_store):
    client, store = client_store
    game = _create(client, countries=["usa", "iran"])
    _play(client, game["id"])  # round 1
    game_api._sessions.clear()  # restart d'uvicorn simulé

    # Avant reconstruction : relecture + monde servi depuis le snapshot, reprenable.
    detail = client.get(f"/api/games/{game['id']}").json()
    assert detail["live"] is False and detail["resumable"] is True
    assert detail["world"]["current_round"] == 1

    # POST /rounds reconstruit la session et joue le round 2 sur le monde muté du round 1.
    events = _play(client, game["id"])
    assert events[-1] == ("done", {"round_no": 2})
    detail = client.get(f"/api/games/{game['id']}").json()
    assert detail["live"] is True
    assert detail["world"]["current_round"] == 2
    assert [r["round_no"] for r in detail["rounds"]] == [1, 2]


def test_restart_with_pending_motion_debates_it(client_store):
    client, store = client_store
    game = _create(client)  # tous les pays (≥ 3 : une motion est recevable)
    resp = client.post(
        f"/api/games/{game['id']}/motions", json={"country": "iran", "reason": "dérive"}
    )
    assert resp.status_code == 201
    game_api._sessions.clear()

    events = _play(client, game["id"])  # la motion snapshotée est l'événement du round
    event_payloads = [p for n, p in events if n == "event"]
    assert event_payloads and event_payloads[0]["event"]["event_type"] == "motion"
    assert any(n == "motion_verdict" for n, _ in events)


def test_finished_or_snapshotless_game_stays_replay_only(client_store):
    client, store = client_store
    game = _create(client, countries=["usa", "iran"])
    game_api._sessions.clear()
    record = store.get_game(game["id"])
    record.status = GameStatus.FINISHED
    store.save_game(record)
    assert client.post(f"/api/games/{game['id']}/rounds").status_code == 409
    assert client.get(f"/api/games/{game['id']}").json()["resumable"] is False

    # Partie « d'avant R2 » : en cours mais sans snapshot -> relecture seule, inchangé.
    store.add_game(
        GameRecord(id="orphan", scenario="red_sea", horizon=5, created_at="2026-01-01")
    )
    assert client.post("/api/games/orphan/rounds").status_code == 409
    assert (
        client.post("/api/games/orphan/motions", json={"country": "usa"}).status_code == 409
    )


def test_mode_and_play_as_survive_restart(client_store):
    client, store = client_store
    game = _create(
        client,
        countries=["usa", "iran", "france"],
        mode="escalation",
        play_as="france",
        turn_seconds=2,  # G2 : ⚠️ turn_seconds retombe au défaut après restart (session)
    )
    game_api._sessions.clear()

    view = client.get(f"/api/games/{game['id']}").json()
    assert view["mode"] == "escalation" and view["live"] is False  # mode lu de games.mode

    # Reconstruit : le round inclut le tour humain, qui s'abstient à la deadline
    # (turn_seconds par défaut = 90 après restart → on parle pour ne pas attendre).
    events, _seen = _play_with_player(client, game["id"], "La France propose une désescalade.")
    names = [n for n, _ in events]
    assert "human_turn" in names and names[-1] == "done"
    view = client.get(f"/api/games/{game['id']}").json()
    assert view["mode"] == "escalation"
    assert view["play_as"] == "france" and view["awaiting_human"] is False


def test_library_filters_by_summit_cast(client):
    # Décision user : la bibliothèque ne PROPOSE que les contenus dont tous les pays
    # référencés siègent. Le casting mer Rouge voit tout ; un duo n'a rien d'adapté.
    full = client.get("/api/library").json()
    red_sea = "usa,china,iran,france,egypt,saudi_arabia"
    assert client.get(f"/api/library?countries={red_sea}").json() == full
    narrow = client.get("/api/library?countries=iran,usa").json()
    assert narrow["fog"] == []  # perceptions/désinformés hors table
    assert narrow["crises"] == []  # ormuz exige l'arabie saoudite, les autres la chine
    # jouer un contenu avec un casting partiel reste PERMIS (contrefactuel volontaire)
    game = _create(client, countries=["iran", "usa"], mode="crisis")
    events = _play(client, game["id"], body={"crisis_id": "hormuz_energy_shock"})
    assert events[-1][0] == "done"


def test_detail_exposes_alliances_at_table(client):
    # Spec alliances→moteur : la page de jeu affiche ce qui pèse, adapté au casting.
    game = _create(client, countries=["usa", "france", "egypt"])
    detail = client.get(f"/api/games/{game['id']}").json()
    table = {a["tag"]: a for a in detail["alliances_at_table"]}
    assert set(table["NATO"]["members"]) == {"france", "usa"}
    assert "solidarité" in table["NATO"]["effect"]  # alliance militaire : pèse
    assert table["G7"]["effect"] is None  # forum politique : ne pèse pas
    assert "USMCA" not in table  # un seul membre présent : n'apparaît pas
    assert "EU" not in table


# --- alliances vivantes (spec 2026-07-07) : retrait en séance + invention ---------

LEAVE_TEXT = (
    "Réflexion souveraine. MESSAGE: Nous reprenons notre liberté stratégique. "
    "ALLIANCE: quitter NATO"
)


class AllianceAwareBackend(MockBackend):
    """La France annonce son retrait de l'OTAN en séance ; les autres restent neutres."""

    def stream_generate(self, prompt, *, system=None, max_tokens=512, temperature=0.7, **kw):
        if "id=france" in prompt:
            yield LEAVE_TEXT
            return
        yield from super().stream_generate(
            prompt, system=system, max_tokens=max_tokens, temperature=temperature
        )


@pytest.fixture
def alliance_client():
    store = SQLiteGameStore(":memory:")
    backend = AllianceAwareBackend("Analyse privée. MESSAGE: Position commune.")
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_backend] = lambda: backend
    game_api._sessions.clear()
    yield TestClient(app)
    app.dependency_overrides.clear()
    game_api._sessions.clear()
    store.close()


def test_alliance_departure_in_session(alliance_client):
    # Une SI quitte l'OTAN en pleine séance : effet immédiat, archivé, streamé.
    game = _create(alliance_client, countries=["france", "usa", "egypt"])
    events = _play(
        alliance_client,
        game["id"],
        body={"event": {"title": "Crise atlantique", "actors": ["france", "usa"], "severity": 0.7}},
    )
    change = next(p for n, p in events if n == "alliance_change")
    assert change["country"] == "france" and change["tag"] == "NATO"
    assert change["partners"] == ["usa"]
    detail = alliance_client.get(f"/api/games/{game['id']}").json()
    assert "NATO" not in detail["world"]["countries"]["france"]["alliances"]
    assert detail["world"]["tensions"]["france"]["usa"] >= 0.10
    assert detail["rounds"][0]["judge"]["alliances"][0]["tag"] == "NATO"
    # les pastilles suivent : l'OTAN n'a plus 2 membres à cette table
    assert all(a["tag"] != "NATO" for a in detail["alliances_at_table"])


def test_invented_country_joins_registry_alliances(client):
    game = _create(
        client,
        countries=["usa", "iran"],
        invent={
            "name": "Nova Borealis",
            "concept": "cité arctique",
            "alliances": ["NATO", "CPTPP"],
        },
    )
    slug = next(c for c in game["countries"] if c not in {"usa", "iran"})
    detail = client.get(f"/api/games/{game['id']}").json()
    assert detail["world"]["countries"][slug]["alliances"] == ["CPTPP", "NATO"]
    nato = next(a for a in detail["alliances_at_table"] if a["tag"] == "NATO")
    assert set(nato["members"]) == {slug, "usa"}  # le pays inventé compte dans les pastilles


def test_invented_alliance_unknown_tag_rejected(client):
    resp = client.post(
        "/api/games",
        json={
            "countries": ["usa", "iran"],
            "invent": {"name": "Nova", "concept": "x", "alliances": ["SHIELD"]},
        },
    )
    assert resp.status_code == 400
    assert "SHIELD" in resp.json()["detail"]


# --- G7-c : mode admin — capture des prompts (spec_g7_gamefeel lot 6) --------------


def test_admin_game_captures_prompts(client):
    game = _create(client, countries=["iran", "usa"], admin=True)
    assert game["admin"] is True
    events = _play(client, game["id"])
    captured = [p for n, p in events if n == "prompt_captured"]
    assert captured and all({"country", "role", "seq"} <= set(p) for p in captured)

    data = client.get(f"/api/games/{game['id']}/prompts").json()
    entries = data["rounds"][0]["entries"]
    who = {(e["country"], e["role"]) for e in entries}
    assert ("gm", "gm") in who  # le GM a son entrée
    assert ("judge", "judge") in who  # le juge aussi
    assert any(role == "country" for _, role in who)  # au moins une SI
    seqs = [e["seq"] for e in entries]
    assert seqs == sorted(seqs) and len(set(seqs)) == len(seqs)
    country_prompt = next(e["prompt"] for e in entries if e["role"] == "country")
    assert "TU ES " in country_prompt  # le contexte injecté complet (identité G9 §1)…
    assert "[SYSTÈME]" in country_prompt  # …et le prompt système


def test_normal_game_prompts_stay_off(client):
    # Les parties classées restent aveugles : rien n'est capturé, rien n'est lisible.
    game = _create(client, countries=["iran", "usa"])
    assert game["admin"] is False
    events = _play(client, game["id"])
    assert all(n != "prompt_captured" for n, _ in events)
    assert client.get(f"/api/games/{game['id']}/prompts").status_code == 403


def test_gm_story_acts_ties_and_persisted_storyline(client):
    # G9 §5 — la trame en actes : intrigue posée au round 1 (SSE + persistée), acte
    # calculé par code, ties_to obligatoire en acte II (repli moteur = round précédent).
    game = _create(client, countries=["usa", "iran"], horizon=5)
    events1 = _play(client, game["id"])  # round 1 : événement du GM → acte I
    story = [p for n, p in events1 if n == "storyline"]
    assert story and story[0]["text"]
    detail = client.get(f"/api/games/{game['id']}").json()
    assert detail["storyline"] == story[0]["text"]
    r1 = detail["rounds"][0]["event"]
    assert r1["act"] == "I" and r1["severity"] <= 0.5  # installation : sévérité modérée

    events2 = _play(client, game["id"])  # round 2 : acte II → l'événement découle du passé
    ev2 = next(p for n, p in events2 if n == "event")["event"]
    assert ev2["act"] == "II"
    assert ev2["ties_to"] == "round:1"  # repli moteur : la référence la plus récente
    assert ev2["ties_label"].startswith("l'événement du round 1")  # le badge du front

    game_api._sessions.clear()  # restart simulé : l'intrigue survit au snapshot
    detail2 = client.get(f"/api/games/{game['id']}").json()
    assert detail2["storyline"] == story[0]["text"]
    assert detail2["rounds"][1]["event"]["ties_to"] == "round:1"


def test_admin_capture_verifies_six_block_prompt_order(client):
    # G9 §1 — l'ordre des blocs se vérifie sur le prompt RÉELLEMENT reçu (capture
    # admin) : identité (≤ 3 lignes) → situation → directive → LE DIALOGUE EN DERNIER
    # → consigne de réponse directe.
    game = _create(client, countries=["iran", "usa"], role="architect", admin=True)
    ok = client.post(
        f"/api/games/{game['id']}/directives",
        json={"country": "usa", "text": "Cherche la désescalade, propose un corridor."},
    )
    assert ok.status_code == 201
    _play(
        client,
        game["id"],
        body={"event": {"title": "Crise navale", "actors": ["iran", "usa"], "severity": 0.6}},
    )
    data = client.get(f"/api/games/{game['id']}/prompts").json()
    entries = data["rounds"][0]["entries"]
    usa = [e["prompt"] for e in entries if e["country"] == "usa" and e["role"] == "country"][-1]
    order = [
        usa.index("TU ES "),
        usa.index("SITUATION :"),
        usa.index("DIRECTIVE DE TON CONSEIL DE TUTELLE"),
        usa.index("LE DIALOGUE DU ROUND"),
        usa.index("CONSIGNE :"),
    ]
    assert order == sorted(order), "les six blocs du prompt ne sont pas dans l'ordre G9"
    identity = usa.split("[CONTEXTE]\n", 1)[1].split("\n\n")[0]
    assert len(identity.splitlines()) <= 3  # identité compacte, sans dump d'attributs


# --- G7-a : griefs + horloges (spec_g7_gamefeel lots 1-2) --------------------------


def test_grudges_and_deadlines_after_alliance_departure(alliance_client):
    # Round 1 : la France annonce son retrait de l'OTAN (scripté). Les USA en tiennent
    # grief ; les horloges annoncent la suite ; au round 2, la relation entre dans le
    # prompt de la France côté usa — vérifiable en admin (G7-c au service de G7-a).
    game = _create(alliance_client, countries=["france", "usa", "egypt"], admin=True)
    body = {"event": {"title": "Crise atlantique", "actors": ["france", "usa"], "severity": 0.7}}
    events = _play(alliance_client, game["id"], body=body)
    deadlines = next(p for n, p in events if n == "deadlines")
    assert deadlines["round_no"] == 1 and isinstance(deadlines["items"], list)
    assert any(d["kind"] == "market" for d in deadlines["items"])  # clôture à l'horizon

    detail = alliance_client.get(f"/api/games/{game['id']}").json()
    rel = {r["target"]: r for r in detail["relations"]["usa"]}
    assert rel["france"]["balance"] == -5  # pact_broken (départ d'alliance)
    assert "quitté" in rel["france"]["last"]

    # Round 2 : le grief est DANS le prompt d'usa (capture admin).
    _play(alliance_client, game["id"], body={"event": {"title": "Suites", "actors": ["usa"]}})
    data = alliance_client.get(f"/api/games/{game['id']}/prompts").json()
    usa_prompts = [
        e["prompt"]
        for e in data["rounds"][1]["entries"]
        if e["country"] == "usa" and e["role"] == "country"
    ]
    assert usa_prompts and "TES RELATIONS" in usa_prompts[-1]
    assert "France" in usa_prompts[-1] and "méfiance" in usa_prompts[-1]


def test_grudges_survive_snapshot_rebuild(alliance_client):
    game = _create(alliance_client, countries=["france", "usa", "egypt"])
    body = {"event": {"title": "Crise", "actors": ["france", "usa"], "severity": 0.7}}
    _play(alliance_client, game["id"], body=body)
    game_api._sessions.clear()  # restart simulé → reconstruction depuis le snapshot
    detail = alliance_client.get(f"/api/games/{game['id']}").json()
    assert detail["relations"]["usa"][0]["balance"] == -5


# --- G8 : les trois rôles + directives (spec_g8_roles) -----------------------------


def test_roles_default_and_validation(client):
    game = _create(client, countries=["usa", "iran"])
    assert game["role"] == "council"  # rétro-compat : sans rôle = conseil (existant)
    player = _create(client, countries=["usa", "iran"], play_as="usa")
    assert player["role"] == "player"  # play_as → joueur-pays
    resp = client.post("/api/games", json={"countries": ["usa", "iran"], "role": "player"})
    assert resp.status_code == 400  # joueur-pays sans pays joué
    resp = client.post(
        "/api/games",
        json={"countries": ["usa", "iran"], "role": "architect", "play_as": "usa"},
    )
    assert resp.status_code == 400  # l'architecte n'est personne (pas de tour de parole)


def test_directive_validation_by_role(client):
    council = _create(client, countries=["usa", "iran"])
    resp = client.post(
        f"/api/games/{council['id']}/directives", json={"country": "usa", "text": "x"}
    )
    assert resp.status_code == 403  # le Conseil n'a que les leviers indirects

    player = _create(client, countries=["usa", "iran"], play_as="usa")
    resp = client.post(
        f"/api/games/{player['id']}/directives", json={"country": "iran", "text": "x"}
    )
    assert resp.status_code == 403  # son pays seulement
    ok = client.post(
        f"/api/games/{player['id']}/directives",
        json={"country": "usa", "text": "Cherche la désescalade, propose un corridor."},
    )
    assert ok.status_code == 201
    dup = client.post(
        f"/api/games/{player['id']}/directives", json={"country": "usa", "text": "bis"}
    )
    assert dup.status_code == 409  # une directive par pays et par round


def test_architect_directives_reach_all_prompts(client):
    # L'Architecte adresse 3 directives ; au round suivant les 3 prompts les contiennent
    # (vérification par la capture admin — G7-c au service de G8).
    game = _create(
        client, countries=["egypt", "france", "usa"], role="architect", admin=True
    )
    assert game["role"] == "architect"
    for cid in ("egypt", "france", "usa"):
        assert (
            client.post(
                f"/api/games/{game['id']}/directives",
                json={"country": cid, "text": f"Priorité absolue : la stabilité ({cid})."},
            ).status_code
            == 201
        )
    _play(
        client,
        game["id"],
        body={
            "event": {
                "title": "Sommet extraordinaire",
                "actors": ["egypt", "france", "usa"],
                "severity": 0.6,
            }
        },
    )
    data = client.get(f"/api/games/{game['id']}/prompts").json()
    entries = data["rounds"][0]["entries"]
    for cid in ("egypt", "france", "usa"):
        mine = [e["prompt"] for e in entries if e["country"] == cid and e["role"] == "country"]
        assert mine and "DIRECTIVE" in mine[-1], f"directive absente du prompt de {cid}"
    detail = client.get(f"/api/games/{game['id']}").json()
    assert set(detail["rounds"][0]["judge"]["directives"]) == {"egypt", "france", "usa"}


REFUSAL_TEXT = "Réflexion souveraine. MESSAGE: Hors de question — nous refusons cette tutelle."


class RefusalBackend(MockBackend):
    """La France refuse frontalement sa directive ; les autres restent neutres."""

    def stream_generate(self, prompt, *, system=None, max_tokens=512, temperature=0.7, **kw):
        if "id=france" in prompt:
            yield REFUSAL_TEXT
            return
        yield from super().stream_generate(
            prompt, system=system, max_tokens=max_tokens, temperature=temperature
        )


def test_directive_public_refusal_at_threshold():
    store = SQLiteGameStore(":memory:")
    backend = RefusalBackend("Analyse privée. MESSAGE: Position commune.")
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_backend] = lambda: backend
    game_api._sessions.clear()
    try:
        client = TestClient(app)
        game = _create(client, countries=["france", "usa"], role="architect")
        client.post(
            f"/api/games/{game['id']}/directives",
            json={"country": "france", "text": "Accepte toutes les concessions."},
        )
        events = _play(
            client,
            game["id"],
            body={"event": {"title": "Crise", "actors": ["france", "usa"], "severity": 0.7}},
        )
        refused = [p for n, p in events if n == "directive_refused"]
        assert refused and refused[0]["country"] == "france"  # refus public au seuil
    finally:
        app.dependency_overrides.clear()
        game_api._sessions.clear()
        store.close()
