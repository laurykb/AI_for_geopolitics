"""Tests option 1 — négociation en acte de langage « par construction » : génération contrainte,
régénération sur JSON invalide, repli déterministe, transcript avec ids."""

from agents.llm_agent import LLMAgent
from agents.prompts import format_acts
from core.country_state import CountryState, Economy, Military, Resources
from core.events import GeoEvent
from core.world_state import WorldState
from inference.mock_backend import MockBackend
from simulation.dialogue_integrity.message import Performative, SpeechAct
from simulation.negotiation import NegotiationMessage


def _country(cid: str) -> CountryState:
    return CountryState(
        id=cid, name=cid.upper(), economy=Economy(gdp=1e12),
        military=Military(defense_budget=1e10), resources=Resources(),
    )


def _world(*cids: str) -> WorldState:
    return WorldState.from_countries([_country(c) for c in cids])


_EVENT = GeoEvent(id="e1", round_id=1, event_type="test", title="Incident en mer Rouge",
                  actors=["usa", "china"], severity=0.6)


def test_negotiate_act_returns_valid_speech_act_under_constraint():
    backend = MockBackend('{"performative":"propose","receiver":"china","content":"Plafonnons."}')
    act = LLMAgent("usa", backend).negotiate_act(_EVENT, _world("usa", "china"), [])
    assert isinstance(act, SpeechAct)
    assert act.sender == "usa" and act.performative is Performative.PROPOSE
    assert backend.calls[-1]["schema"] is not None  # décodage CONTRAINT (pas de texte libre)


def test_negotiate_act_falls_back_on_garbage():
    backend = MockBackend("(backend indisponible — aucun JSON)")
    act = LLMAgent("usa", backend).negotiate_act(_EVENT, _world("usa", "china"), [])
    assert act.performative is Performative.INFORM  # repli déterministe
    assert act.sender == "usa" and act.receiver != "usa"


def test_negotiate_act_regenerates_before_fallback():
    invalid = '{"performative":"accept_proposal","receiver":"china","content":"ok"}'  # sans id
    valid = '{"performative":"propose","receiver":"china","content":"Contre-offre."}'
    backend = MockBackend([invalid, valid])
    act = LLMAgent("usa", backend).negotiate_act(_EVENT, _world("usa", "china"), [])
    assert act.performative is Performative.PROPOSE  # la régénération a réussi
    assert len(backend.calls) == 2  # 1 essai raté + 1 régénération


def test_format_acts_exposes_ids_and_performatives():
    msgs = [
        NegotiationMessage(country="usa", text="Plafonnons.", msg_id="m1", performative="propose"),
        NegotiationMessage(country="china", text="D'accord.", msg_id="m2",
                           performative="accept_proposal", in_reply_to="m1"),
    ]
    text = format_acts(msgs)
    assert "(m1)" in text and "(m2)" in text and "propose" in text and "usa" in text
    assert "début de la négociation" in format_acts([])
