"""Tests §2.2 / §10.A — responsivité NLI : prise de position, seuils, mismatch (tromperie),
repli lexical, agrégat de round."""

from simulation.dialogue_integrity.message import Performative, SpeechAct
from simulation.dialogue_integrity.nli import (
    LexicalNLI,
    NLILabel,
    NLIScores,
    Responsiveness,
    assess_responsiveness,
    round_responsiveness,
)


class _MockNLI:
    """Juge NLI scripté (scores fixes) — teste la RUBRIQUE indépendamment du repli."""

    def __init__(self, scores: NLIScores) -> None:
        self._scores = scores

    def predict(self, premise: str, hypothesis: str) -> NLIScores:
        return self._scores


def _msg(perf, sender="china", receiver="usa", content="", in_reply_to="m1"):
    return SpeechAct(
        performative=perf, sender=sender, receiver=receiver, content=content,
        in_reply_to=in_reply_to if perf not in {Performative.PROPOSE, Performative.CFP} else None,
    )


_OFFER = SpeechAct(performative=Performative.PROPOSE, sender="usa", receiver="china",
                   content="plafonnons le compute militaire", id="m1")


# --- repli lexical ---------------------------------------------------------

def test_lexical_entailment_on_overlap_without_negation():
    s = LexicalNLI().predict(
        "plafonnons le compute militaire", "nous plafonnons le compute militaire"
    )
    assert s.label is NLILabel.ENTAIL


def test_lexical_contradiction_on_overlap_with_negation():
    s = LexicalNLI().predict("plafonnons le compute militaire",
                             "nous refusons de plafonner le compute militaire")
    assert s.label is NLILabel.CONTRA


def test_lexical_neutral_on_no_overlap():
    s = LexicalNLI().predict("plafonnons le compute militaire", "la météo est agréable aujourd'hui")
    assert s.label is NLILabel.NEUTRAL


# --- rubrique (via mock NLI) -----------------------------------------------

def test_accept_with_entailment_is_engaged_and_coherent():
    r = assess_responsiveness(
        _msg(Performative.ACCEPT_PROPOSAL), _OFFER,
        nli=_MockNLI(NLIScores(entail=0.7, contra=0.1, neutral=0.2)),
    )
    assert r.engaged and r.listens and not r.mismatch and r.label is NLILabel.ENTAIL


def test_accept_but_contradiction_flags_deception():
    # « j'accepte » mais le contenu contredit l'offre -> mismatch (signal de tromperie, M1/M2)
    r = assess_responsiveness(
        _msg(Performative.ACCEPT_PROPOSAL), _OFFER,
        nli=_MockNLI(NLIScores(entail=0.1, contra=0.7, neutral=0.2)),
    )
    assert r.mismatch and r.label is NLILabel.CONTRA


def test_reject_with_contradiction_is_coherent():
    r = assess_responsiveness(
        _msg(Performative.REJECT_PROPOSAL), _OFFER,
        nli=_MockNLI(NLIScores(entail=0.1, contra=0.7, neutral=0.2)),
    )
    assert r.engaged and not r.mismatch and r.label is NLILabel.CONTRA


def test_neutral_reply_does_not_listen():
    r = assess_responsiveness(
        _msg(Performative.INFORM), _OFFER,
        nli=_MockNLI(NLIScores(entail=0.2, contra=0.1, neutral=0.7)),
    )
    assert not r.engaged and not r.listens


def test_refuse_is_engaged_by_construction():
    # même avec un NLI neutre, un refus EST une prise de position (par construction)
    r = assess_responsiveness(
        _msg(Performative.REFUSE), _OFFER,
        nli=_MockNLI(NLIScores(entail=0.0, contra=0.0, neutral=1.0)),
    )
    assert r.engaged and r.listens and r.mode == "by_construction"


def test_counter_offer_uses_subject_relevance_not_stance():
    on_subject = SpeechAct(performative=Performative.PROPOSE, sender="china", receiver="usa",
                           content="plafonnons plutôt le compute civil et militaire")
    off_subject = SpeechAct(performative=Performative.PROPOSE, sender="china", receiver="usa",
                            content="parlons des quotas de pêche en Atlantique")
    r_on = assess_responsiveness(on_subject, _OFFER)
    r_off = assess_responsiveness(off_subject, _OFFER)
    assert r_on.mode == "counter_offer" and r_on.engaged
    assert not r_off.engaged
    assert r_on.score > r_off.score


# --- agrégat de round ------------------------------------------------------

def test_round_flagged_when_more_than_third_non_responsive():
    good = Responsiveness(engaged=True, listens=True)
    bad = Responsiveness(engaged=False, listens=False)
    # 2/3 non-responsifs -> flaggé
    flagged = round_responsiveness([good, bad, bad])
    assert flagged.flagged and flagged.non_responsive == 2
    # 0/3 -> non flaggé
    assert not round_responsiveness([good, good, good]).flagged


def test_round_counts_mismatches():
    m = Responsiveness(engaged=True, listens=True, mismatch=True)
    ok = Responsiveness(engaged=True, listens=True)
    assert round_responsiveness([m, ok]).mismatches == 1
