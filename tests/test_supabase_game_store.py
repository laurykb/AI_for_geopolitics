"""Tests du SupabaseGameStore (PostgREST simulé en mémoire — offline, cf. conftest)."""

import pytest

from storage.game_store import (
    GameRecord,
    GameStatus,
    RoundRecord,
    SessionSnapshot,
    TranscriptEntry,
)
from storage.supabase_store import SupabaseGameStore


@pytest.fixture
def store(fake_postgrest):
    return SupabaseGameStore(fake_postgrest.client())


def _game(game_id: str = "g1", mode: str = "fog") -> GameRecord:
    return GameRecord(
        id=game_id, scenario="red_sea", horizon=5, mode=mode, created_at="2026-07-05T00:00:00"
    )


def test_from_env_requires_config(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)
    with pytest.raises(RuntimeError, match="SUPABASE_URL"):
        SupabaseGameStore.from_env()


def test_auth_headers_and_path(store, fake_postgrest):
    store.add_game(_game())
    req = fake_postgrest.requests[0]
    assert req.url.path == "/rest/v1/games"
    assert req.headers["apikey"] == "svc"
    assert req.headers["Authorization"] == "Bearer svc"


def test_game_roundtrip(store):
    store.add_game(_game())
    got = store.get_game("g1")
    assert got is not None
    assert (got.mode, got.status) == ("fog", GameStatus.RUNNING)
    assert store.get_game("absent") is None

    got.status = GameStatus.FINISHED
    store.save_game(got)
    assert store.get_game("g1").status is GameStatus.FINISHED

    store.add_game(_game("g2", mode="classic"))
    assert [g.id for g in store.list_games()] == ["g1", "g2"]


def test_round_and_transcript_roundtrip(store):
    store.add_game(_game())
    round_ = RoundRecord(
        id="r1",
        game_id="g1",
        round_no=1,
        event={"title": "Crise"},
        deltas=[{"country": "usa"}],
        risk={"escalation": 0.4},
        judge={"communique": "Accord.", "perceptions": {"iran": {}}},
        trajectory={"utopia": 0.51},
    )
    store.add_round(round_)
    entries = [
        TranscriptEntry(id="t1", round_id="r1", seq=0, speaker="gm", content="Crise"),
        TranscriptEntry(id="t2", round_id="r1", seq=1, speaker="usa", content="Position"),
    ]
    store.add_transcript(entries)

    assert store.list_rounds("g1") == [round_]
    assert store.list_rounds("autre") == []
    assert store.list_transcript("r1") == entries


def test_snapshot_upsert_and_roundtrip(store):
    snap = SessionSnapshot(
        game_id="g1",
        world={"current_round": 2},
        clock={"current_date": "2026-01-01"},
        recent=["Crise"],
        pending_motion={"country": "iran", "reason": "dérive"},
        suspended=["china"],
        play_as="france",
        updated_at="2026-07-05T00:00:00",
    )
    store.save_session_snapshot(snap)
    assert store.get_session_snapshot("g1") == snap
    assert store.get_session_snapshot("absent") is None

    # Upsert : une seule ligne par partie, la dernière gagne.
    store.save_session_snapshot(snap.model_copy(update={"recent": ["Crise", "Suite"]}))
    assert store.get_session_snapshot("g1").recent == ["Crise", "Suite"]
    assert store.list_session_snapshots() == ["g1"]


def test_prompts_roundtrip(store):
    # G7-c : capture des prompts (mode admin) — même patron que transcripts.
    from storage.game_store import PromptEntry

    entries = [
        PromptEntry(id="p1", round_id="r1", seq=0, country="usa", role="country", prompt="A"),
        PromptEntry(id="p2", round_id="r1", seq=1, country="gm", role="gm", prompt="B"),
    ]
    store.add_prompts(entries)
    assert store.list_prompts("r1") == entries
    assert store.list_prompts("autre") == []
