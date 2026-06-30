"""Tests de l'abstraction d'inférence et du backend mock (sans GPU)."""

from inference.backend import InferenceResult
from inference.mock_backend import MockBackend


def test_tokens_per_second_computed_from_duration():
    res = InferenceResult(text="x", completion_tokens=40, duration_s=2.0)
    assert res.tokens_per_second == 20.0


def test_tokens_per_second_zero_when_no_duration():
    res = InferenceResult(text="x", completion_tokens=40, duration_s=0.0)
    assert res.tokens_per_second == 0.0


def test_mock_returns_single_response_and_records_calls():
    backend = MockBackend('{"ok": true}', completion_tokens=10, duration_s=0.5)
    res = backend.generate("hello", system="sys", max_tokens=128, schema={"type": "object"})

    assert res.text == '{"ok": true}'
    assert res.tokens_per_second == 20.0
    assert len(backend.calls) == 1
    call = backend.calls[0]
    assert call["prompt"] == "hello"
    assert call["system"] == "sys"
    assert call["max_tokens"] == 128
    assert call["schema"] == {"type": "object"}


def test_mock_consumes_queue_then_repeats_last():
    backend = MockBackend(["a", "b"])
    assert backend.generate("p").text == "a"
    assert backend.generate("p").text == "b"
    assert backend.generate("p").text == "b"  # file épuisée -> répète la dernière
