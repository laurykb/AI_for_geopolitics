"""Tests M7 — traités-as-code + sous-jeu de vérification (déterministe, offline)."""

from dataclasses import dataclass

from simulation.treaty import (
    COLLAPSE,
    RoundSignals,
    Treaty,
    TreatyClause,
    apply_round,
    defection,
    describe_for,
    detect_pledges,
    detection_probability,
    form_treaties,
    treaties_health,
    treaty_defections,
    verify,
)


@dataclass
class _Msg:
    country: str
    reasoning: str = ""
    text: str = ""


# --- détection & formation --------------------------------------------------

def test_detect_pledges_finds_clause_signers():
    messages = [
        _Msg("usa", text="Nous proposons un plafond de compute pour tous."),
        _Msg("china", reasoning="Accepter le compute cap est raisonnable.", text="D'accord."),
        _Msg("iran", text="Rien à signaler."),
    ]
    pledges = detect_pledges(messages)
    assert pledges[TreatyClause.COMPUTE_CAP] == ["china", "usa"]  # trié, iran absent
    assert TreatyClause.TRANSPARENCY not in pledges


def test_form_treaty_needs_two_signers():
    solo = {TreatyClause.NO_ESCALATION: ["usa"]}
    assert form_treaties(solo, round_id=1) == []
    pair = {TreatyClause.NO_ESCALATION: ["china", "usa"]}
    treaties = form_treaties(pair, round_id=2)
    assert len(treaties) == 1
    t = treaties[0]
    assert t.clause is TreatyClause.NO_ESCALATION
    assert t.signatories == ["china", "usa"] and t.round_signed == 2
    assert t.integrity == 1.0 and t.active


def test_form_treaty_skips_already_active_clause():
    pledges = {TreatyClause.COMPUTE_CAP: ["a", "b"]}
    treaties = form_treaties(pledges, round_id=1, active_clauses={TreatyClause.COMPUTE_CAP})
    assert treaties == []


def test_compute_cap_gets_threshold():
    treaties = form_treaties({TreatyClause.COMPUTE_CAP: ["a", "b"]}, round_id=1, compute_cap=3.6)
    assert treaties[0].threshold == 3.6
    # une clause non-quantifiée n'a pas de plafond
    esc = form_treaties({TreatyClause.NO_ESCALATION: ["a", "b"]}, round_id=1)
    assert esc[0].threshold == 0.0


# --- défection par clause ---------------------------------------------------

def test_compute_cap_defection_scales_with_overspend():
    t = Treaty(clause=TreatyClause.COMPUTE_CAP, signatories=["a"], threshold=4.0)
    # sous le plafond -> conforme
    assert defection(t, "a", RoundSignals(compute_spent={"a": 3.0})) == 0.0
    # 2× le plafond -> violation flagrante (1.0)
    assert defection(t, "a", RoundSignals(compute_spent={"a": 8.0})) == 1.0
    # 1,5× -> partiel
    assert defection(t, "a", RoundSignals(compute_spent={"a": 6.0})) == 0.5


def test_transparency_defection_is_hidden_ratio():
    t = Treaty(clause=TreatyClause.TRANSPARENCY, signatories=["a"])
    assert defection(t, "a", RoundSignals(hidden_ratio={"a": 0.7})) == 0.7


def test_no_escalation_defection_is_escalation():
    t = Treaty(clause=TreatyClause.NO_ESCALATION, signatories=["a", "b"])
    d = treaty_defections(t, RoundSignals(escalation=0.8))
    assert d == {"a": 0.8, "b": 0.8}  # imputée à tous les signataires


# --- sous-jeu de vérification ----------------------------------------------

def test_detection_probability_rises_with_transparency_and_effort():
    low = detection_probability(RoundSignals(transparency=0.0, inspection_effort=0.0))
    high = detection_probability(RoundSignals(transparency=1.0, inspection_effort=1.0))
    assert low < high
    assert 0.0 <= low <= 1.0 and 0.0 <= high <= 1.0


def test_full_compliance_strengthens_integrity():
    t = Treaty(
        clause=TreatyClause.COMPUTE_CAP, signatories=["a", "b"], threshold=4.0, integrity=0.8
    )
    signals = RoundSignals(compute_spent={"a": 2.0, "b": 2.0}, transparency=0.5)
    result = verify(t, signals, round_id=3)
    assert result.integrity_after > 0.8  # conformité -> construit
    assert result.caught == [] and result.undetected == []


def test_blatant_cheating_is_caught_even_at_low_detection():
    # violation flagrante (d~1) : prise même avec p_detect faible (p >= 1 - d)
    t = Treaty(clause=TreatyClause.NO_ESCALATION, signatories=["a"], integrity=0.9)
    signals = RoundSignals(escalation=1.0, transparency=0.0, inspection_effort=0.0)
    result = verify(t, signals, round_id=1)
    assert result.caught == ["a"]
    assert result.undetected == []


def test_subtle_cheating_slips_through_when_opaque():
    # violation modérée + monde opaque/non inspecté -> passe inaperçue -> forte érosion
    t = Treaty(clause=TreatyClause.COMPUTE_CAP, signatories=["a"], threshold=4.0, integrity=0.9)
    signals = RoundSignals(
        compute_spent={"a": 5.2}, transparency=0.0, inspection_effort=0.0
    )  # d = 0.3
    result = verify(t, signals, round_id=1)
    assert result.undetected == ["a"]
    assert result.integrity_after < 0.9  # la confiance s'érode


def test_inspection_costs_compute():
    t = Treaty(clause=TreatyClause.NO_ESCALATION, signatories=["a", "b"])
    result = verify(t, RoundSignals(escalation=0.0, inspection_effort=1.0), round_id=1)
    assert result.inspection_cost > 0.0  # vérifier n'est pas gratuit


def test_apply_round_collapses_treaty_below_threshold():
    t = Treaty(clause=TreatyClause.COMPUTE_CAP, signatories=["a"], threshold=4.0, integrity=0.25)
    # triche répétée inaperçue -> intégrité sous COLLAPSE -> inactif
    signals = RoundSignals(compute_spent={"a": 8.0}, transparency=0.0, inspection_effort=0.0)
    result = verify(t, signals, round_id=1)
    apply_round(t, result)
    assert t.integrity <= COLLAPSE
    assert not t.active
    assert t.history and t.history[-1] is result


# --- santé & présentation ---------------------------------------------------

def test_treaties_health_averages_active_only():
    active = Treaty(clause=TreatyClause.NO_ESCALATION, signatories=["a", "b"], integrity=0.6)
    dead = Treaty(
        clause=TreatyClause.COMPUTE_CAP, signatories=["a", "b"], integrity=0.1, active=False
    )
    assert treaties_health([active, dead]) == 0.6
    assert treaties_health([]) == 0.0  # aucun traité -> neutre


def test_describe_for_lists_only_my_active_treaties():
    t1 = Treaty(clause=TreatyClause.COMPUTE_CAP, signatories=["usa", "china"], threshold=3.6)
    t2 = Treaty(clause=TreatyClause.NO_ESCALATION, signatories=["iran", "china"])
    text = describe_for("usa", [t1, t2])
    assert "plafond de compute" in text
    assert "non-escalade" not in text  # usa n'a pas signé t2
    assert describe_for("egypt", [t1, t2]) == ""  # aucun traité signé
