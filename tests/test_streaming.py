"""Tests du streaming des backends d'inférence (stream_generate)."""

from inference.backend import InferenceBackend, InferenceResult
from inference.mock_backend import MockBackend


def test_mock_stream_yields_chunks_concatenating_to_text():
    backend = MockBackend("le monde change vite")
    chunks = list(backend.stream_generate("prompt"))
    assert len(chunks) > 1  # émis en plusieurs morceaux
    assert "".join(chunks) == "le monde change vite"
    assert backend.calls[-1]["stream"] is True


class _OneShot(InferenceBackend):
    """Backend minimal qui n'implémente que generate (teste le défaut de l'ABC)."""

    def generate(self, prompt, *, system=None, max_tokens=512, temperature=0.7, schema=None):
        return InferenceResult(text="hello world", completion_tokens=2, duration_s=0.1)


def test_abc_default_stream_falls_back_to_single_chunk():
    assert list(_OneShot().stream_generate("p")) == ["hello world"]
