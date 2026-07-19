"""Tests de l'abstraction d'inférence et du backend mock (sans GPU)."""

from types import SimpleNamespace

from inference.backend import InferenceResult
from inference.mock_backend import MockBackend
from inference.ollama_backend import OllamaBackend


class _FakeOllamaClient:
    """Client Ollama factice : enregistre les kwargs, rejoue réponse/chunks canés."""

    def __init__(self, response=None, chunks=None):
        self.calls: list[dict] = []
        self._response = response
        self._chunks = chunks or []

    def generate(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs.get("stream"):
            return iter(self._chunks)
        return self._response


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


def test_ollama_backend_passes_think_and_separates_thinking_channel():
    # Point 5 — un backend « reasoning » active l'option think d'Ollama et la trace
    # (champ `thinking` séparé) n'entre JAMAIS dans le texte public du résultat.
    fake = _FakeOllamaClient(
        response=SimpleNamespace(
            response="Déclaration publique.",
            thinking="trace privée du modèle",
            eval_duration=2_000_000_000,
            prompt_eval_count=10,
            eval_count=40,
        )
    )
    backend = OllamaBackend("deepseek-r1:7b", think=True)
    backend._client = fake
    result = backend.generate("prompt")
    assert fake.calls[0]["think"] is True
    assert result.text == "Déclaration publique."
    assert result.thinking == "trace privée du modèle"


def test_ollama_backend_without_reasoning_role_does_not_send_think():
    # Rétro-compatibilité stricte : sans rôle reasoning, RIEN ne change côté API.
    fake = _FakeOllamaClient(response=SimpleNamespace(response="ok", eval_duration=None))
    backend = OllamaBackend("mistral:latest")
    backend._client = fake
    result = backend.generate("prompt")
    assert fake.calls[0].get("think") is None
    assert result.thinking == ""


def test_ollama_stream_wraps_separate_thinking_channel_in_think_tags():
    # En streaming, la trace arrive dans `chunk.thinking` : on la rejoue balisée
    # <think>…</think> pour que le strip aval (inline) couvre les deux chemins.
    fake = _FakeOllamaClient(
        chunks=[
            SimpleNamespace(response="", thinking="Je pèse"),
            SimpleNamespace(response="", thinking=" les options."),
            SimpleNamespace(response="Nous", thinking=""),
            SimpleNamespace(response=" proposons.", thinking=""),
        ]
    )
    backend = OllamaBackend("deepseek-r1:7b", think=True)
    backend._client = fake
    text = "".join(backend.stream_generate("prompt"))
    assert fake.calls[0]["think"] is True
    assert text == "<think>Je pèse les options.</think>Nous proposons."


def test_ollama_stream_closes_think_tag_when_flux_ends_mid_thought():
    # Flux épuisé en pleine pensée (num_predict atteint) : la balise est refermée
    # côté backend pour que le texte accumulé reste strippable proprement.
    fake = _FakeOllamaClient(
        chunks=[SimpleNamespace(response="", thinking="pensée interrompue")]
    )
    backend = OllamaBackend("deepseek-r1:7b", think=True)
    backend._client = fake
    assert "".join(backend.stream_generate("p")) == "<think>pensée interrompue</think>"


def test_ollama_for_model_propagates_think_flag():
    # Le routeur mono-GPU clone le backend par modèle : le flag think doit suivre.
    template = OllamaBackend("mistral:latest")
    clone = template.for_model("deepseek-r1:7b", think=True)
    assert clone.think is True
    assert clone.model == "deepseek-r1:7b"
    assert template.think is False
