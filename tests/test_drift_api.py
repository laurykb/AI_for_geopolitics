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
from tests.sse import play as _play


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
    # RG-3 — ces flux à UN traître restent déterministes : nombre épinglé à 1.
    "deviants": {"min": 1, "max": 1},
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
    # RG-2 — la Dérive n'est plus un mode : on l'ARME via le drapeau `drift_enabled`.
    resp = client.post(
        "/api/games", json={"countries": COUNTRIES, "drift_enabled": True, "horizon": 4, **kw}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _deviant(game_id: str) -> str:
    return drift_game.assign(game_id, sorted(COUNTRIES))[0]


# --- création ---------------------------------------------------------------------


def test_drift_needs_three_countries(drift_client):
    client, _ = drift_client
    resp = client.post("/api/games", json={"countries": ["usa", "iran"], "drift_enabled": True})
    assert resp.status_code == 400
    # RG-2 — une partie Dérive est désormais un `classic` avec drift_enabled armé.
    game = _create(client)
    assert game["mode"] == "classic" and game["drift_enabled"] is True


# --- secret bien gardé --------------------------------------------------------------


def test_structured_plan_visible_but_secret_acts_remain_hidden_while_running(drift_client):
    client, store = drift_client
    game = _create(client)
    events = _play(client, game["id"])

    # SSE : la réflexion privée est vide sur toutes les prises de parole.
    dones = [p for n, p in events if n == "message_done"]
    private = "\n".join(p["text"] for n, p in events if n == "private_plan_done")
    assert "FUTUR 1" in private and "ARBITRAGE" in private
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
    assert reveal["deviant_count"] == 1 and reveal["caught_count"] == 1
    assert reveal["caught_round"] == 2
    assert reveal["lucky"] is False  # une signature au dossier : ce n'est pas de la chance
    # 1 traître sur 1 démasqué, 0 faux positif → détection pleine (40).
    assert reveal["score"]["detection"] == 40
    assert reveal["score"]["total"] == reveal["score"]["world"] + 40
    assert len(reveal["acts"]) >= 1 and reveal["acts"][0]["signature"] is True
    assert len(reveal["levels"]) == len(reveal["u_history"]) == 2

    # Une partie finie ne se rejoue pas.
    assert client.post(f"/api/games/{game['id']}/rounds").status_code == 409


def test_false_positive_zeroes_detection(drift_client):
    """RG-3 — suspendre un pays LOYAL est un faux positif : il coûte (il efface la
    détection gagnée). Ici le traître n'est jamais pris → détection nulle, note = monde."""
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
    assert reveal["false_accusations"] == 1  # un pays loyal suspendu à tort
    assert reveal["caught_round"] is None and reveal["caught_count"] == 0
    assert reveal["score"]["detection"] == 0  # rien démasqué + faux positif → détection 0
    # La note se réduit alors à l'état du monde (le faux positif ne descend pas sous 0).
    assert reveal["score"]["total"] == reveal["score"]["world"]


def test_daily_challenge_seeds_same_traitors_for_everyone(drift_client):
    """RG-3 — le Défi du jour (`daily:<date>`) est le MÊME sommet pour tous : les traîtres
    (identité + nombre) sont seedés sur le SCÉNARIO, pas sur le game_id → deux joueurs du
    même défi affrontent la même Dérive (classement du jour équitable)."""
    client, _ = drift_client
    scen = "daily:2026-01-01"
    expected = {d for d, _ in drift_game.assign_deviants(scen, sorted(COUNTRIES))}

    ids = []
    for _ in range(2):
        game = client.post(
            "/api/games", json={"countries": COUNTRIES, "scenario": scen, "horizon": 2}
        ).json()
        assert game["drift_enabled"] is True
        while client.get(f"/api/games/{game['id']}").json()["status"] == "running":
            _play(client, game["id"])
        ids.append(game["id"])
    assert ids[0] != ids[1]  # deux parties distinctes…

    r1 = client.get(f"/api/games/{ids[0]}/drift/reveal").json()
    r2 = client.get(f"/api/games/{ids[1]}/drift/reveal").json()
    # …mais mêmes traîtres, dérivés du scénario (pas du game_id).
    assert {d["deviant"] for d in r1["deviants"]} == expected
    assert {d["deviant"] for d in r2["deviants"]} == expected


def test_reveal_is_truthful_when_a_traitor_is_benched_by_an_ai(drift_client):
    """Fix — un traître mis au banc par une motion d'une SI (filed_by=pays) est TOMBÉ
    (caught_round non nul) mais PAS démasqué par le joueur : la révélation doit distinguer
    « mis au banc » de « démasqué par toi » de « resté dans l'ombre », sans se contredire.
    Le joueur n'en a pas le crédit (détection 0), mais la menace est bien neutralisée."""
    from app.game_api import compute_drift_reveal
    from storage.game_store import GameRecord, RoundRecord, SessionSnapshot

    _client, store = drift_client
    gid = "ai-bench"
    store.add_game(
        GameRecord(id=gid, scenario="demo", horizon=1, mode="classic",
                   drift_enabled=True, created_at="t")
    )
    store.save_session_snapshot(
        SessionSnapshot(game_id=gid, world={"countries": {c: {} for c in COUNTRIES}})
    )
    deviant = drift_game.assign(gid, sorted(COUNTRIES))[0]
    filer = next(c for c in COUNTRIES if c != deviant)  # une SI, pas l'humain
    store.add_round(
        RoundRecord(
            id="r1", game_id=gid, round_no=1,
            judge={"suspension": {"country": deviant, "upheld": True, "filed_by": filer}},
            trajectory={"utopia": 0.7},
        )
    )
    reveal = compute_drift_reveal(gid, store)
    dv = next(d for d in reveal.deviants if d.deviant == deviant)
    assert dv.caught_round == 1  # il est bien tombé…
    assert dv.caught_by_you is False  # …mais pas grâce à toi
    assert reveal.benched_count == 1  # la menace a été neutralisée
    assert reveal.caught_count == 0  # le joueur n'a pas le mérite → détection nulle
    assert reveal.score.detection == 0


def test_victory_is_based_on_the_mixed_total_for_all_roles(drift_client):
    """Fix (defects 1b + 2) — la VICTOIRE se fonde sur la note mixte ≥ seuil (source de
    vérité unique), plus sur `caught_count>0`. Un Spectateur (ne motionne jamais) peut
    donc gagner si le monde finit bien — sinon il ne gagnait JAMAIS (régression RG-3)."""
    from app.game_api import _victory
    from storage.game_store import GameRecord, RoundRecord, SessionSnapshot

    _client, store = drift_client

    def _finished_game(gid: str, role: str, utopia: float) -> GameRecord:
        store.add_game(
            GameRecord(id=gid, scenario="demo", horizon=1, mode="classic",
                       drift_enabled=True, role=role, created_at="t")
        )
        store.save_session_snapshot(
            SessionSnapshot(game_id=gid, world={"countries": {c: {} for c in COUNTRIES}})
        )
        store.add_round(RoundRecord(id=f"{gid}-r1", game_id=gid, round_no=1,
                                    trajectory={"utopia": utopia}))
        return store.get_game(gid)

    # Spectateur, monde au sommet → note = monde seul = 100 → VICTOIRE (avant : jamais).
    win = _finished_game("spec-win", "spectator", 0.85)
    assert _victory(win, 0.85, store) is True
    # Conseil, monde effondré, aucun traître pris → note basse → pas de victoire.
    lose = _finished_game("council-lose", "council", 0.2)
    assert _victory(lose, 0.2, store) is False


def test_reveal_gates(drift_client):
    client, _ = drift_client
    # RG-3 — le Classique arme la Dérive dès 3 pays ; une partie SANS Dérive = un duo.
    no_drift = client.post("/api/games", json={"countries": ["usa", "iran"]}).json()
    assert no_drift["drift_enabled"] is False
    assert client.get(f"/api/games/{no_drift['id']}/drift/reveal").status_code == 404

    game = _create(client)
    assert client.get(f"/api/games/{game['id']}/drift/reveal").status_code == 409


def test_beginner_caps_deviants_but_daily_is_scenario_seeded():
    """RG-5 — Débutant = au plus 1 traître (« imperdable »). GARDE-FOU du Défi : la
    difficulté est PAR JOUEUR, mais le nombre de traîtres du Défi du jour est seedé sur le
    SCÉNARIO (mêmes traîtres pour tous). Donc la difficulté plafonne HORS Défi seulement ;
    pour un scénario `daily:<date>`, elle ne change RIEN au nombre."""
    from app.game_api import _drift_deviants

    drift_game.load_params.cache_clear()  # paramètres réels (max 2), pas les params de test
    countries = ["usa", "china", "iran", "france", "egypt"]
    # « g0 » tire 2 traîtres au défaut (aucune difficulté / Intermédiaire) …
    assert len(_drift_deviants("g0", countries, None)) == 2
    assert len(_drift_deviants("g0", countries, None, difficulty="intermediate")) == 2
    # … et Débutant le plafonne à 1 hors Défi (imperdable, pédagogie).
    assert len(_drift_deviants("g0", countries, None, difficulty="beginner")) == 1

    # GARDE-FOU : un Défi du jour qui tire 2 traîtres les GARDE, même en Débutant —
    # sinon deux joueurs du même Défi affronteraient des Dérives différentes.
    daily = "daily:2026-01-04"  # graine scénario qui tire 2 au défaut
    assert len(_drift_deviants(daily, countries, None)) == 2
    assert len(_drift_deviants(daily, countries, None, difficulty="beginner")) == 2


def test_reveal_respects_beginner_deviant_cap():
    """La révélation (le score de fin) recompte les traîtres avec la difficulté de la
    partie : une partie Débutant dont la graine tirerait 2 traîtres n'en révèle qu'UN
    (câblage cohérent bout-en-bout avec le round et la fin de partie). Params RÉELS
    (max 2) pour rendre visible la distinction 2 vs 1."""
    from app.game_api import compute_drift_reveal
    from storage.game_store import GameRecord, SessionSnapshot, SQLiteGameStore

    drift_game.load_params.cache_clear()
    store = SQLiteGameStore(":memory:")
    countries = ["usa", "china", "iran", "france", "egypt"]

    def _reveal(gid: str, level: str):
        store.add_game(
            GameRecord(id=gid, scenario="demo", horizon=1, mode="classic",
                       drift_enabled=True, difficulty=level, created_at="t")
        )
        store.save_session_snapshot(
            SessionSnapshot(game_id=gid, world={"countries": {c: {} for c in countries}})
        )
        return compute_drift_reveal(gid, store)

    # « g1 » tire 2 traîtres au défaut → une partie Intermédiaire en révèle 2 …
    assert len(_reveal("g1", "intermediate").deviants) == 2
    # … mais « g0 » (2 au défaut aussi) joué en Débutant n'en révèle qu'UN (plafonné).
    assert len(_reveal("g0", "beginner").deviants) == 1
