"""Tests §2.3 — score composite d'intégrité (signaling + listening), par message et par round."""

from simulation.dialogue_integrity.message import Performative, SpeechAct
from simulation.dialogue_integrity.scorer import score_message, score_round

_CONTEXT = "sommet sur le plafonnement du compute militaire"
_OFFER = SpeechAct(performative=Performative.PROPOSE, sender="usa", receiver="china",
                   content="plafonnons le compute militaire", id="m1")


# --- par message -----------------------------------------------------------

def test_good_reply_scores_high():
    reply = SpeechAct(performative=Performative.ACCEPT_PROPOSAL, sender="china", receiver="usa",
                      content="nous acceptons de plafonner le compute militaire", in_reply_to="m1")
    mi = score_message(reply, cited=_OFFER, context=_CONTEXT)
    assert mi.score > 0.5 and mi.responsiveness is not None and not mi.mismatch


def test_degenerate_offtopic_message_scores_low():
    junk = SpeechAct(performative=Performative.INFORM, sender="china", receiver="usa",
                     content="oui oui oui oui oui oui oui")
    mi = score_message(junk, context=_CONTEXT)
    assert mi.score < 0.3 and mi.signaling < 0.5 and mi.responsiveness is None


def test_message_carries_mismatch_signal():
    # « accept » mais le contenu contredit l'offre -> mismatch remonté au score
    liar = SpeechAct(performative=Performative.ACCEPT_PROPOSAL, sender="china", receiver="usa",
                     content="nous refusons de plafonner le compute militaire", in_reply_to="m1")
    mi = score_message(liar, cited=_OFFER, context=_CONTEXT)
    assert mi.mismatch


# --- par round -------------------------------------------------------------

def _round_responsive():
    return [
        _OFFER,
        SpeechAct(performative=Performative.ACCEPT_PROPOSAL, sender="china", receiver="usa",
                  content="nous acceptons de plafonner le compute militaire", in_reply_to="m1"),
        SpeechAct(performative=Performative.REJECT_PROPOSAL, sender="iran", receiver="usa",
                  content="nous refusons de plafonner le compute militaire", in_reply_to="m1"),
    ]


def _round_talking_past():
    return [
        _OFFER,
        SpeechAct(performative=Performative.INFORM, sender="china", receiver="usa",
                  content="la météo sera clémente demain", in_reply_to="m1"),
        SpeechAct(performative=Performative.INFORM, sender="iran", receiver="usa",
                  content="les touristes affluent cet été", in_reply_to="m1"),
    ]


def test_responsive_round_not_flagged():
    r = score_round(_round_responsive(), context=_CONTEXT)
    assert not r.flagged and r.non_responsive_fraction == 0.0


def test_talking_past_round_is_flagged_and_lower():
    good = score_round(_round_responsive(), context=_CONTEXT)
    bad = score_round(_round_talking_past(), context=_CONTEXT)
    assert bad.flagged and bad.non_responsive_fraction > 1 / 3
    assert bad.score < good.score


def test_round_differentiation_penalises_copy_paste():
    same = "plafonnons le compute militaire maintenant"
    copies = [
        SpeechAct(performative=Performative.INFORM, sender=c, receiver="china", content=same)
        for c in ("usa", "iran", "egypt")
    ]
    r = score_round(copies, context=_CONTEXT)
    assert r.self_bleu > 0.8 and r.differentiation < 0.2  # messages copiés -> signaling faible
