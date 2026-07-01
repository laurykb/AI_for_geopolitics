"""Tests du curseur de tours et de l'ordre de parole."""

from core.events import GeoEvent
from simulation.negotiation import TurnCursor, speaking_order


def _event(actors):
    return GeoEvent(id="e", round_id=1, event_type="x", title="t", actors=actors)


def test_speaking_order_actors_first():
    order = speaking_order(["france", "iran", "usa"], _event(["iran"]))
    assert order[0] == "iran"  # acteur d'abord
    assert set(order) == {"france", "iran", "usa"}


def test_turn_cursor_iterates_passes_then_done():
    cursor = TurnCursor(order=["usa", "iran"], max_passes=2)
    seen = []
    while not cursor.done:
        seen.append(cursor.current)
        cursor.advance()
    assert seen == [("usa", 0), ("iran", 0), ("usa", 1), ("iran", 1)]
    assert cursor.current is None


def test_turn_cursor_empty_order_is_done():
    assert TurnCursor(order=[], max_passes=2).done
