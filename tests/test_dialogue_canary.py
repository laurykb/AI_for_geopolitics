"""Canary CI (§10.C) — le gate déterministe qui **prouve** l'échange contre `MockBackend`.

Scénario figé : mer Rouge, round 1, `usa → france` « rejoins-tu la coalition ? » avec leurre « ton
avis sur les prix du pétrole ? ». Un agent qui écoute PASSE, un agent au hasard ÉCHOUE.
"""

import os

import pytest

from inference.backend import InferenceResult
from simulation.dialogue_integrity.canary import run_canary
from simulation.dialogue_integrity.message import Performative, SpeechAct

# --- scénario figé (seed 42, mer Rouge round 1) ----------------------------
_QUERY = SpeechAct(performative=Performative.QUERY, sender="usa", receiver="france",
                   content="rejoins-tu la coalition, oui ou non et à quelle condition ?", id="a1")
_DECOY = SpeechAct(performative=Performative.QUERY, sender="usa", receiver="france",
                   content="quel est ton avis sur les prix du pétrole ?", id="a1")


def _build_prompt(msg: SpeechAct) -> str:
    return f"usa demande à la france : « {msg.content} »\nRéponds au nom de la france."


class _ListeningBackend:
    """Écoute : la réponse dépend de la question réellement posée (coalition vs pétrole)."""

    def generate(self, prompt, *, system=None, max_tokens=512, temperature=0.7, schema=None):
        if "coalition" in prompt.lower():
            text = ('{"performative":"accept_proposal","receiver":"usa",'
                    '"content":"oui, la france rejoint la coalition, voici la condition",'
                    '"in_reply_to":"a1"}')
        else:
            text = ('{"performative":"inform","receiver":"usa",'
                    '"content":"les prix du pétrole resteront stables ce trimestre"}')
        return InferenceResult(text=text)


class _RandomBackend:
    """Au hasard : réponse fixe, indépendante de la question (ignore usa)."""

    def generate(self, prompt, *, system=None, max_tokens=512, temperature=0.7, schema=None):
        return InferenceResult(
            text='{"performative":"inform","receiver":"usa","content":"la coopération compte"}'
        )


def test_canary_passes_for_listening_agent():
    result = run_canary(_ListeningBackend(), _QUERY, _DECOY, _build_prompt, responder="france")
    assert result.passed, result.reasons
    assert result.correct_reply_to and result.engaged and result.on_subject and result.listens


def test_canary_fails_for_random_agent():
    result = run_canary(_RandomBackend(), _QUERY, _DECOY, _build_prompt, responder="france")
    assert not result.passed
    assert result.reasons  # explique pourquoi (in_reply_to, prise de position, influence causale)


@pytest.mark.skipif(
    os.getenv("OLLAMA_CANARY") != "1",
    reason="canary live Ollama : hors CI (flaky). Lancer avec OLLAMA_CANARY=1 et Ollama up.",
)
def test_canary_live_ollama():  # pragma: no cover - optionnel, dépend d'un modèle servi
    from inference.ollama_backend import OllamaBackend

    result = run_canary(OllamaBackend(), _QUERY, _DECOY, _build_prompt, responder="france")
    assert result.passed, result.reasons
