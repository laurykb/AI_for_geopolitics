"""Tests §1.1 — actes de langage FIPA : performative obligatoire, `in_reply_to` requis pour une
réponse, décodage contraint (schéma passé au backend)."""

import pytest
from pydantic import ValidationError

from inference.mock_backend import MockBackend
from simulation.dialogue_integrity.message import (
    OPENING_PERFORMATIVES,
    REPLY_PERFORMATIVES,
    Performative,
    SpeechAct,
    generate_speech_act,
    parse_speech_act,
    speech_act_schema,
)

# --- performatives & partition ---------------------------------------------

def test_ten_fipa_performatives():
    assert {p.value for p in Performative} == {
        "inform", "query", "cfp", "propose", "accept_proposal", "reject_proposal",
        "request", "agree", "refuse", "not_understood",
    }


def test_reply_and_opening_partition_the_set():
    assert REPLY_PERFORMATIVES.isdisjoint(OPENING_PERFORMATIVES)
    assert REPLY_PERFORMATIVES | OPENING_PERFORMATIVES == set(Performative)
    assert Performative.ACCEPT_PROPOSAL in REPLY_PERFORMATIVES
    assert Performative.PROPOSE in OPENING_PERFORMATIVES


# --- validation « pas de talking past » ------------------------------------

def test_opening_message_needs_no_reply_reference():
    msg = SpeechAct(performative=Performative.PROPOSE, sender="usa", receiver="china",
                    content="Plafonnons le compute.")
    assert not msg.is_reply
    assert msg.id  # un id est attribué automatiquement


def test_reply_performative_requires_in_reply_to():
    with pytest.raises(ValidationError):
        SpeechAct(performative=Performative.ACCEPT_PROPOSAL, sender="china", receiver="usa",
                  content="D'accord.")


def test_reply_performative_valid_with_in_reply_to():
    msg = SpeechAct(performative=Performative.ACCEPT_PROPOSAL, sender="china", receiver="usa",
                    content="J'accepte le plafond.", in_reply_to="m1")
    assert msg.is_reply and msg.in_reply_to == "m1"


def test_sender_and_receiver_must_differ():
    with pytest.raises(ValidationError):
        SpeechAct(performative=Performative.INFORM, sender="usa", receiver="usa", content="…")


def test_replies_to_links_by_id():
    offer = SpeechAct(performative=Performative.PROPOSE, sender="usa", receiver="china",
                      content="Offre.", id="m1")
    answer = SpeechAct(performative=Performative.REJECT_PROPOSAL, sender="china", receiver="usa",
                       content="Non.", in_reply_to="m1")
    assert answer.replies_to(offer)
    assert not offer.replies_to(answer)


# --- schéma pour le décodage contraint -------------------------------------

def test_schema_exposes_draft_fields():
    schema = speech_act_schema()
    props = schema["properties"]
    assert "performative" in props and "receiver" in props and "in_reply_to" in props
    assert "performative" in schema["required"]
    # l'identité n'est PAS demandée au modèle (injectée par l'agent)
    assert "sender" not in props and "id" not in props


# --- parsing d'une sortie contrainte ---------------------------------------

def test_parse_injects_sender_and_tolerates_prose():
    raw = 'Voici: {"performative": "propose", "receiver": "china", "content": "Offre."} merci'
    msg = parse_speech_act(raw, sender="usa")
    assert msg.sender == "usa" and msg.performative is Performative.PROPOSE
    assert msg.receiver == "china"


def test_parse_reply_without_reference_raises():
    raw = '{"performative": "agree", "receiver": "usa", "content": "ok"}'
    with pytest.raises(ValueError, match="in_reply_to"):
        parse_speech_act(raw, sender="china")


def test_parse_garbage_raises():
    with pytest.raises(ValueError):
        parse_speech_act("(le backend est indisponible)", sender="usa")


# --- décodage contraint de bout en bout (MockBackend) ----------------------

def test_generate_passes_schema_and_low_temperature():
    backend = MockBackend('{"performative": "propose", "receiver": "china", "content": "Offre."}')
    msg = generate_speech_act(backend, "négocie", sender="usa")
    assert isinstance(msg, SpeechAct) and msg.performative is Performative.PROPOSE
    call = backend.calls[-1]
    assert call["schema"] is not None  # décodage CONTRAINT (pas de texte libre)
    assert call["temperature"] <= 0.3  # température basse (spéc §1.2)
