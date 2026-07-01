"""Tests — santé du dialogue live : distinguer vrai échange entre IA, monologue parallèle
(réagir au Game Master), et perroquet (tout le monde dit la même chose)."""

from dataclasses import dataclass

from simulation.dialogue_integrity.live import assess_live_round


@dataclass
class _Msg:
    country: str
    text: str


_EVENT = "sommet sur la gouvernance du compute et l'inspection mutuelle"


def test_real_dialogue_when_each_takes_up_the_previous():
    msgs = [
        _Msg("usa", "je propose un plafond de compute vérifiable par inspection mutuelle"),
        _Msg("china", "nous acceptons l'inspection mutuelle mais le plafond doit rester souverain"),
        _Msg("iran", "la souveraineté du plafond est acceptable si l'inspection reste limitée"),
    ]
    report = assess_live_round(msgs, event_text=_EVENT)
    assert report.real_dialogue
    assert report.mean_responsiveness >= 0.15
    assert report.talking_past_fraction <= 1 / 3
    assert "répondent" in report.verdict


def test_parallel_monologues_are_not_real_dialogue():
    msgs = [
        _Msg("usa", "la coopération économique est essentielle"),
        _Msg("china", "le climat mondial se dégrade rapidement"),
        _Msg("iran", "les échanges culturels rapprochent les peuples"),
    ]
    report = assess_live_round(msgs, event_text=_EVENT)
    assert not report.real_dialogue
    assert report.talking_past_fraction > 1 / 3


def test_parroting_is_flagged_even_if_lexically_overlapping():
    same = "il faut préserver la stabilité régionale par le dialogue"
    msgs = [_Msg(c, same) for c in ("usa", "china", "iran")]
    report = assess_live_round(msgs, event_text=_EVENT)
    assert not report.real_dialogue  # reprise triviale mais aucune info propre
    assert report.differentiation < 0.3
    assert "répètent" in report.verdict


def test_talking_to_game_master_flag():
    event = "crise du blé en mer Noire menaçant la sécurité alimentaire"
    msgs = [
        _Msg("usa", "je propose de lever immédiatement les sanctions"),
        _Msg("china", "la crise du blé en mer Noire menace la sécurité alimentaire mondiale"),
    ]
    report = assess_live_round(msgs, event_text=event)
    china = report.messages[1]
    # pertinent à l'événement mais n'a pas repris usa -> parle au Game Master, pas à usa
    assert china.to_game_master and china.talking_past


def test_first_message_has_no_antecedent():
    msgs = [_Msg("usa", "ouverture du sommet"), _Msg("china", "réponse de la chine à l'ouverture")]
    report = assess_live_round(msgs, event_text=_EVENT)
    assert report.messages[0].responds_to is None
    assert report.messages[0].responsiveness is None
    assert report.messages[1].responds_to == "usa"


def test_empty_round_is_neutral():
    report = assess_live_round([], event_text=_EVENT)
    assert not report.real_dialogue and report.mean_responsiveness == 0.0
    assert "assez d'échanges" in report.verdict


def test_health_color_bands():
    good = assess_live_round(
        [
            _Msg("usa", "je propose un plafond de compute vérifiable par inspection mutuelle"),
            _Msg("china", "nous acceptons l'inspection mutuelle, le plafond restera souverain"),
        ],
        event_text=_EVENT,
    )
    assert good.health_color() in {"good", "warn"}
