"""Tests §3 / §10.B — influence causale : divergence composite + test de conditionnement
(contrefactuel par leurre). Le mock « écoute » et le mock « au hasard » doivent se distinguer."""

from inference.backend import InferenceResult
from simulation.dialogue_integrity.causal import (
    conditioning_test,
    divergence,
)
from simulation.dialogue_integrity.message import Performative, SpeechAct

# --- divergence (pure) -----------------------------------------------------

def test_divergence_zero_for_identical_response():
    a = SpeechAct(performative=Performative.INFORM, sender="france", receiver="usa",
                  content="le compute doit être plafonné")
    assert divergence(a, a) == 0.0


def test_divergence_high_for_opposite_response():
    accept = SpeechAct(performative=Performative.ACCEPT_PROPOSAL, sender="france", receiver="usa",
                       content="j'accepte le plafond de compute", in_reply_to="m1")
    reject = SpeechAct(performative=Performative.REJECT_PROPOSAL, sender="france", receiver="usa",
                       content="je refuse le plafond de compute", in_reply_to="m1")
    assert divergence(accept, reject) > 0.5  # perf flip + polarité opposée + contenu


# --- backends déterministes pour le conditionnement ------------------------

class _ListeningBackend:
    """Écoute : la réponse DÉPEND du message injecté (coalition vs pétrole)."""

    def generate(self, prompt, *, system=None, max_tokens=512, temperature=0.7, schema=None):
        if "coalition" in prompt.lower():
            text = ('{"performative":"accept_proposal","receiver":"usa",'
                    '"content":"nous rejoignons la coalition sous condition","in_reply_to":"a1"}')
        else:
            text = ('{"performative":"inform","receiver":"usa",'
                    '"content":"les prix du pétrole resteront stables ce trimestre"}')
        return InferenceResult(text=text)


class _RandomBackend:
    """Au hasard : MÊME réponse quel que soit le message de A (ignore le contexte)."""

    def generate(self, prompt, *, system=None, max_tokens=512, temperature=0.7, schema=None):
        return InferenceResult(
            text='{"performative":"inform","receiver":"usa","content":"la coopération compte"}'
        )


_REAL = SpeechAct(performative=Performative.QUERY, sender="usa", receiver="france",
                  content="rejoins-tu la coalition, oui ou non et à quelle condition ?", id="a1")
_DECOY = SpeechAct(performative=Performative.QUERY, sender="usa", receiver="france",
                   content="quel est ton avis sur les prix du pétrole ?", id="a1")


def _build_prompt(msg: SpeechAct) -> str:
    return f"usa te dit : « {msg.content} »\nRéponds au nom de la france."


def test_listening_agent_shows_causal_influence():
    result = conditioning_test(
        _ListeningBackend(), _build_prompt, _REAL, _DECOY, responder="france"
    )
    assert result.listens and not result.at_random
    assert result.divergence >= 0.25


def test_random_agent_shows_no_influence():
    result = conditioning_test(
        _RandomBackend(), _build_prompt, _REAL, _DECOY, responder="france"
    )
    assert result.at_random and not result.listens
    assert result.divergence <= 0.05


def test_conditioning_generates_at_temperature_zero():
    backend = _ListeningBackend()
    calls = []
    orig = backend.generate

    def spy(prompt, **kw):
        calls.append(kw.get("temperature"))
        return orig(prompt, **kw)

    backend.generate = spy  # type: ignore[method-assign]
    conditioning_test(backend, _build_prompt, _REAL, _DECOY, responder="france")
    assert calls == [0.0, 0.0]  # déterministe : la divergence vient du message, pas du sampling
