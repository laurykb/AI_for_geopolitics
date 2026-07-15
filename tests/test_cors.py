"""Origines CORS : le front local par défaut, extensibles par CORS_ORIGINS."""

from app.main import cors_origins


def test_defaults_without_env(monkeypatch) -> None:
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    assert cors_origins() == ["http://localhost:3000", "http://127.0.0.1:3000"]


def test_env_extends_defaults(monkeypatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3010, http://127.0.0.1:3010")
    origins = cors_origins()
    assert origins[:2] == ["http://localhost:3000", "http://127.0.0.1:3000"]
    assert "http://localhost:3010" in origins
    assert "http://127.0.0.1:3010" in origins


def test_blank_entries_ignored(monkeypatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", " , ,http://localhost:3010,")
    assert cors_origins().count("http://localhost:3010") == 1
    assert "" not in cors_origins()
