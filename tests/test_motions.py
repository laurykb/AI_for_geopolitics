"""Tests du module motions (R4) : événement de motion, parse du verdict, arbitrage."""

import pytest

from agents.judge import JudgeAgent
from inference.mock_backend import MockBackend
from simulation.loader import load_world
from simulation.motions import (
    Motion,
    arbitrate_stream,
    build_motion_prompt,
    motion_event,
    parse_motion_verdict,
)
from simulation.negotiation import NegotiationMessage


def test_motion_event_carries_target_and_reason():
    event = motion_event(Motion(country="iran", reason="escalade répétée"), 3)
    assert event.event_type == "motion"
    assert event.round_id == 3
    assert event.actors == ["iran"]
    assert "iran" in event.title
    assert "escalade répétée" in event.description


def test_motion_event_fills_default_reason():
    event = motion_event(Motion(country="usa"), 1)
    assert "préoccupant" in event.description


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Le pays a plaidé, mais la menace demeure.\nVERDICT: SUSPENDRE", True),
        ("verdict: suspendre", True),
        ("VERDICT - suspension immédiate d'un round", True),
        ("La plaidoirie a convaincu.\nVERDICT: REJETER", False),
        ("aucun marqueur lisible dans ce texte", False),
        ("", False),
        # plusieurs lignes VERDICT : la dernière fait foi
        ("VERDICT: SUSPENDRE\nAprès réflexion…\nVERDICT: REJETER", False),
    ],
)
def test_parse_motion_verdict(text, expected):
    assert parse_motion_verdict(text) is expected


def test_build_prompt_mentions_motion_and_debate():
    world = load_world()
    motion = Motion(country="iran", reason="refus d'inspection")
    event = motion_event(motion, 1)
    transcript = [
        NegotiationMessage(
            country="usa",
            text="Nous soutenons la motion.",
            reasoning="",
            pass_no=0,
            seconds=0.1,
            model="mock",
        )
    ]
    prompt = build_motion_prompt(motion, event, world, transcript)
    assert "iran" in prompt and "refus d'inspection" in prompt
    assert "Nous soutenons la motion." in prompt
    assert "VERDICT" in prompt


def test_arbitrate_stream_falls_back_to_reject_when_backend_dies():
    class DeadBackend(MockBackend):
        def stream_generate(self, *args, **kwargs):
            raise RuntimeError("backend hors service")

    judge = JudgeAgent(DeadBackend())
    motion = Motion(country="usa")
    event = motion_event(motion, 1)
    text = "".join(arbitrate_stream(judge, motion, event, load_world(), []))
    assert "indisponible" in text
    assert parse_motion_verdict(text) is False  # repli conservateur : rejet
