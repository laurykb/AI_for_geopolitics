"""Tests G9 §3 — scripts/dialogue_metrics.py : l'instrument de mesure offline du §1."""

import sys
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from app import game_api
from app.game_api import get_backend, get_store
from app.main import app
from inference.mock_backend import MockBackend
from storage.game_store import GameRecord, RoundRecord, SQLiteGameStore, TranscriptEntry

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import dialogue_metrics as dm  # noqa: E402


def _entry(round_id: str, seq: int, speaker: str, content: str) -> TranscriptEntry:
    return TranscriptEntry(
        id=uuid4().hex[:12], round_id=round_id, seq=seq, speaker=speaker, content=content
    )


def _store_with_round(entries_spec, judge: dict | None = None) -> tuple[SQLiteGameStore, str]:
    store = SQLiteGameStore(":memory:")
    store.add_game(GameRecord(id="g1", scenario="test", horizon=5, created_at="now"))
    record = RoundRecord(id="r1", game_id="g1", round_no=1, judge=judge or {})
    store.add_round(record)
    store.add_transcript(
        [_entry("r1", i, speaker, text) for i, (speaker, text) in enumerate(entries_spec)]
    )
    return store, "g1"


def test_responsiveness_counts_direct_replies():
    store, gid = _store_with_round(
        [
            ("gm", "Blocus du détroit : la crise commence."),
            ("usa", "Nous exigeons un corridor humanitaire immédiat pour les navires civils."),
            ("iran", "Votre corridor humanitaire pour les navires est un prétexte inacceptable."),
            ("france", "La météo est splendide et nos vignobles prospèrent cette saison."),
        ]
    )
    metrics = dm.measure_game(store, gid)
    assert metrics.messages == 3
    # 2 réponses évaluées : l'iran reprend (corridor humanitaire/navires), la france non.
    assert abs(metrics.responsive_rate - 0.5) < 1e-9


def test_repetition_detects_the_broken_record():
    verse = "Nous défendons la stabilité régionale et la sécurité de nos approvisionnements."
    store, gid = _store_with_round(
        [("usa", verse), ("iran", "Position nouvelle et différente."), ("usa", verse)]
    )
    metrics = dm.measure_game(store, gid)
    assert metrics.by_country_repetition["usa"] > 0.4  # le 2e couplet est déjà connu
    assert metrics.repetition_rate > dm.TARGET_REPETITION  # partie hors cible
    assert not metrics.passes()


def test_directive_visibility_counts_reflection_or_public_refusal():
    store, gid = _store_with_round(
        [
            ("usa", "Nous cherchons la désescalade maritime et proposons un corridor."),
            ("iran", "Nous poursuivons notre programme sans commentaire."),
        ],
        judge={
            "directives": {
                "usa": "cherche la désescalade maritime",
                "iran": "accepte toutes les inspections",
            }
        },
    )
    metrics = dm.measure_game(store, gid)
    assert metrics.directives_total == 2
    assert metrics.directives_visible == 1  # usa reflète ; iran ignore (et sans refus public)

    # le refus public détecté (judge_json) compte comme « visible » : refléter OU assumer
    store2, gid2 = _store_with_round(
        [("iran", "Hors de question.")],
        judge={"directives": {"iran": "accepte tout"}, "directives_refused": ["iran"]},
    )
    assert dm.measure_game(store2, gid2).directives_visible == 1

    # tolérance aux accords (constaté sur mistral réel) : « corridors humanitaires
    # supervisés » reflète bien « propose un corridor humanitaire supervisé »
    store3, gid3 = _store_with_round(
        [("france", "Nous proposons des corridors humanitaires supervisés dès demain.")],
        judge={"directives": {"france": "propose un corridor humanitaire supervisé"}},
    )
    assert dm.measure_game(store3, gid3).directives_visible == 1


def test_offline_script_on_a_reproducible_mock_game():
    # Une partie MockBackend jouée via l'API, mesurée deux fois : mêmes chiffres
    # (l'instrument est déterministe), et le radotage du mock est bien détecté.
    store = SQLiteGameStore(":memory:")
    backend = MockBackend("Analyse privée. MESSAGE: Nous défendons la stabilité régionale.")
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_backend] = lambda: backend
    game_api._sessions.clear()
    try:
        client = TestClient(app)
        game = client.post("/api/games", json={"countries": ["usa", "iran"]}).json()
        for _ in range(2):
            with client.stream("POST", f"/api/games/{game['id']}/rounds", json=None) as resp:
                assert resp.status_code == 200
                list(resp.iter_lines())
        first = dm.measure_game(store, game["id"])
        second = dm.measure_game(store, game["id"])
        assert first == second  # reproductible
        assert first.messages >= 2
        assert first.repetition_rate > dm.TARGET_REPETITION  # le mock radote, l'outil le voit
    finally:
        app.dependency_overrides.clear()
        game_api._sessions.clear()
        store.close()
