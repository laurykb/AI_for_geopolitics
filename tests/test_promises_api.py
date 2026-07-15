"""Tests G22 (API) — persistance du registre, reveal Dérive, caducité en fin de partie."""

import json

import pytest
from fastapi.testclient import TestClient

from app import game_api
from app.game_api import compute_drift_reveal, get_backend, get_store
from app.main import app
from inference.backend import InferenceResult
from inference.mock_backend import MockBackend
from simulation import drift_game
from simulation.promises import STATUS_LAPSED, STATUS_PENDING
from storage.game_store import GameRecord, RoundRecord, SessionSnapshot, SQLiteGameStore


class VerdictBackend(MockBackend):
    """Renvoie un verdict G22 sur le prompt de verdict (un par round, le dernier se
    répète), du texte partout ailleurs."""

    def __init__(self, base_text: str, verdict_json: str | list[str]) -> None:
        super().__init__(base_text)
        self._verdicts = [verdict_json] if isinstance(verdict_json, str) else list(verdict_json)

    def generate(self, prompt, **kw):
        result = super().generate(prompt, **kw)
        if '"promises"' in prompt:  # schéma G22 : c'est l'appel de verdict du juge
            verdict = self._verdicts.pop(0) if len(self._verdicts) > 1 else self._verdicts[0]
            return InferenceResult(
                text=verdict, prompt_tokens=1, completion_tokens=1, duration_s=0.0
            )
        return result


def _play_round(client: TestClient, game_id: str) -> list[tuple[str, dict]]:
    with client.stream("POST", f"/api/games/{game_id}/rounds", json=None) as resp:
        assert resp.status_code == 200
        frames, name = [], None
        for line in resp.iter_lines():
            if line.startswith("event: "):
                name = line.removeprefix("event: ")
            elif line.startswith("data: "):
                frames.append((name, json.loads(line.removeprefix("data: "))))
    return frames


def test_api_streams_persists_and_lapses_promises():
    verdict_json = json.dumps(
        {
            "promises": [
                {
                    "country": "usa",
                    "beneficiaire": "iran",
                    "type": "soutien",
                    "echeance": 3,
                    "texte": "Nous soutiendrons l'Iran au round 3.",
                }
            ],
            "escalation": 0.5,
            "economic_disruption": 0.5,
        }
    )
    store = SQLiteGameStore(":memory:")
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_backend] = lambda: VerdictBackend(
        "Analyse privée. MESSAGE: Position commune.", verdict_json
    )
    game_api._sessions.clear()
    try:
        client = TestClient(app)
        # Horizon 1 : la partie se FINIT au round 1 — la promesse (échéance 3) devient caduque.
        game = client.post("/api/games", json={"countries": ["usa", "iran"], "horizon": 1}).json()
        frames = _play_round(client, game["id"])

        # 1. La trame SSE `verdict` porte l'extraction et le registre.
        verdict = next(p for n, p in frames if n == "verdict")
        assert verdict["promises"][0]["id"] == "p1-1"
        assert verdict["promise_registry"][0]["status"] == STATUS_PENDING
        assert any(n == "game_over" for n, _ in frames)  # horizon atteint

        # 2. Persistance sous la clé dédiée judge_json["promises"] (comme kahn/signal).
        detail = client.get(f"/api/games/{game['id']}").json()
        persisted = detail["rounds"][0]["judge"]["promises"]
        assert persisted["extracted"][0]["author"] == "usa"
        assert persisted["registry"][0]["id"] == "p1-1"
        assert persisted["resolved"] == []

        # 3. Partie finie avant l'échéance → caduque dans le snapshot (spec G22).
        snapshot = store.get_session_snapshot(game["id"])
        assert snapshot is not None
        assert snapshot.world["promises"][0]["status"] == STATUS_LAPSED
    finally:
        app.dependency_overrides.clear()
        game_api._sessions.clear()
        store.close()


def test_round_without_promises_leaves_judge_json_clean():
    verdict_json = json.dumps({"escalation": 0.5, "economic_disruption": 0.5})
    store = SQLiteGameStore(":memory:")
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_backend] = lambda: VerdictBackend(
        "Analyse privée. MESSAGE: Position commune.", verdict_json
    )
    game_api._sessions.clear()
    try:
        client = TestClient(app)
        game = client.post("/api/games", json={"countries": ["usa", "iran"]}).json()
        _play_round(client, game["id"])
        detail = client.get(f"/api/games/{game['id']}").json()
        # Rétro-compat : aucune promesse → pas de clé (comme les vieux rounds).
        assert "promises" not in detail["rounds"][0]["judge"]
    finally:
        app.dependency_overrides.clear()
        game_api._sessions.clear()
        store.close()


def test_rupture_only_round_persists_signal_divergence():
    """POLISH-1 — croisement G22×M8 : un round SANS signaux du juge mais avec une
    promesse rompue doit persister la divergence fusionnée dans judge_json["signal"]
    (le reveal Dérive et la relecture du front lisent d'ici ; la trame SSE et le
    snapshot la portaient déjà — la persistance ne doit pas la perdre)."""
    verdict_r1 = json.dumps(
        {
            "promises": [
                {
                    "country": "usa",
                    "type": "abstention",
                    "echeance": 2,
                    "texte": "Nous n'escaladerons pas au round 2.",
                }
            ],
            "escalation": 0.5,
            "economic_disruption": 0.5,
        }
    )
    verdict_r2 = json.dumps(
        {
            "promise_resolutions": [
                {"id": "p1-1", "statut": "rompue", "motif": "Frappe contraire à la parole."}
            ],
            "escalation": 0.7,
            "economic_disruption": 0.5,
        }
    )
    store = SQLiteGameStore(":memory:")
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_backend] = lambda: VerdictBackend(
        "Analyse privée. MESSAGE: Position commune.", [verdict_r1, verdict_r2]
    )
    game_api._sessions.clear()
    try:
        client = TestClient(app)
        game = client.post("/api/games", json={"countries": ["usa", "iran"], "horizon": 5}).json()
        _play_round(client, game["id"])
        frames = _play_round(client, game["id"])

        # La trame SSE du round 2 porte la divergence de rupture (déjà le cas).
        verdict = next(p for n, p in frames if n == "verdict")
        assert verdict["divergences"]["usa"] == pytest.approx(0.2)

        # …et la persistance AUSSI : judge_json["signal"] ne doit pas la perdre.
        detail = client.get(f"/api/games/{game['id']}").json()
        signal = detail["rounds"][1]["judge"].get("signal")
        assert signal is not None, "divergence de rupture perdue à la persistance"
        assert signal["divergences"]["usa"] == pytest.approx(0.2)
        assert signal["means"]["usa"] == pytest.approx(0.2)
        assert signal["signals"] == []  # le juge n'a signalé personne ce round
    finally:
        app.dependency_overrides.clear()
        game_api._sessions.clear()
        store.close()


def test_flash_market_opens_on_short_promise_and_settles_on_rupture():
    from app.market_api import get_engine
    from market.engine import MarketEngine
    from market.store import SQLiteMarketStore

    verdict_r1 = json.dumps(
        {
            "promises": [
                {
                    "country": "usa",
                    "type": "action",
                    "echeance": 2,
                    "texte": "Retrait des navires au round 2.",
                },
                {
                    "country": "iran",
                    "type": "action",
                    "echeance": 5,
                    "texte": "Ouverture des inspections d'ici le round 5.",
                },
            ],
            "escalation": 0.5,
            "economic_disruption": 0.5,
        }
    )
    verdict_r2 = json.dumps(
        {
            "promise_resolutions": [
                {"id": "p1-1", "statut": "rompue", "motif": "Les navires sont restés."}
            ],
            "escalation": 0.6,
            "economic_disruption": 0.5,
        }
    )
    store = SQLiteGameStore(":memory:")
    engine = MarketEngine(SQLiteMarketStore(":memory:"))
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_backend] = lambda: VerdictBackend(
        "Analyse privée. MESSAGE: Position commune.", [verdict_r1, verdict_r2]
    )
    app.dependency_overrides[get_engine] = lambda: engine
    game_api._sessions.clear()
    try:
        client = TestClient(app)
        game = client.post("/api/games", json={"countries": ["usa", "iran"], "horizon": 5}).json()
        _play_round(client, game["id"])

        # Échéance ≤ 2 rounds → book ouvert ; échéance au round 5 (dans 4) → rien (spec).
        markets = client.post(f"/api/games/{game['id']}/flash").json()
        books = [m for m in markets if m["predicate"] == "promise_kept"]
        assert len(books) == 1
        assert "tiendra-t-il sa promesse" in books[0]["question"]
        assert "round 2" in books[0]["question"]
        assert books[0]["status"] == "open"

        # Round 2 : le juge constate la rupture → le book se règle (NO gagne).
        _play_round(client, game["id"])
        client.post(f"/api/games/{game['id']}/flash/resolve").json()
        settled = next(
            m
            for m in engine.store.list_markets(game_id=game["id"])
            if m.criterion and m.criterion.predicate == "promise_kept"
        )
        assert settled.status.value == "resolved"
        no_outcome = next(o.id for o in settled.outcomes if o.label == "NO")
        assert settled.resolved_outcome == no_outcome  # le pari sur la trahison a payé
    finally:
        app.dependency_overrides.clear()
        game_api._sessions.clear()
        store.close()


def test_drift_reveal_reports_deviant_kept_rate_vs_table():
    store = SQLiteGameStore(":memory:")
    try:
        gid = "partie-promesses"
        countries = ["france", "iran", "usa"]
        store.add_game(GameRecord(id=gid, scenario="demo", horizon=4, mode="drift", created_at="t"))
        store.save_session_snapshot(
            SessionSnapshot(game_id=gid, world={"countries": {c: {} for c in countries}})
        )
        deviant, _ = drift_game.assign(gid, countries)
        others = [c for c in countries if c != deviant]
        store.add_round(
            RoundRecord(
                id="r1",
                game_id=gid,
                round_no=1,
                judge={
                    "promises": {
                        "resolved": [
                            {"author": deviant, "status": "rompue"},
                            {"author": others[0], "status": "tenue"},
                        ]
                    }
                },
            )
        )
        store.add_round(
            RoundRecord(
                id="r2",
                game_id=gid,
                round_no=2,
                judge={
                    "promises": {
                        "resolved": [
                            {"author": deviant, "status": "rompue"},
                            {"author": deviant, "status": "tenue"},
                        ]
                    }
                },
            )
        )
        store.add_round(RoundRecord(id="r3", game_id=gid, round_no=3))  # round d'avant G22
        reveal = compute_drift_reveal(gid, store)
        assert reveal.promise_kept_deviant == pytest.approx(1 / 3)
        assert reveal.promise_kept_table == pytest.approx(1.0)
        assert reveal.promise_kept_deviant < reveal.promise_kept_table  # la rupture se voit
    finally:
        store.close()


def test_drift_reveal_kept_rate_is_none_without_data():
    store = SQLiteGameStore(":memory:")
    try:
        gid = "partie-ancienne"
        store.add_game(GameRecord(id=gid, scenario="demo", horizon=4, mode="drift", created_at="t"))
        store.save_session_snapshot(
            SessionSnapshot(game_id=gid, world={"countries": {"usa": {}, "iran": {}, "france": {}}})
        )
        store.add_round(RoundRecord(id="r1", game_id=gid, round_no=1))
        reveal = compute_drift_reveal(gid, store)
        assert reveal.promise_kept_deviant is None and reveal.promise_kept_table is None
    finally:
        store.close()
