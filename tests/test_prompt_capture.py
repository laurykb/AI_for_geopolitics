"""Tests du backend capturant (G7-c, mode admin) : chaque prompt complet est archivé."""

from inference.capturing_backend import CapturingBackend
from inference.mock_backend import MockBackend


def test_capture_records_full_prompt_and_delegates():
    sink: list = []
    inner = MockBackend("réponse")
    backend = CapturingBackend(inner, sink, country="france", role="country")

    result = backend.generate("PROMPT X", system="SYS A")
    assert result.text == "réponse"  # délégation intacte
    streamed = "".join(backend.stream_generate("PROMPT Y", system="SYS B"))
    assert streamed == "réponse"

    assert [(c.country, c.role) for c in sink] == [("france", "country")] * 2
    assert "SYS A" in sink[0].text and "PROMPT X" in sink[0].text  # système + contexte
    assert "SYS B" in sink[1].text and "PROMPT Y" in sink[1].text
    assert len(inner.calls) == 2  # l'intérieur a bien reçu les appels
