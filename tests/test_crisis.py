"""Tests du Crisis Replay : bibliothèque de crises + comparaison historique vs simulé."""

from simulation.crisis import (
    Crisis,
    HistoricalOutcome,
    compare_outcome,
    load_crises,
)


def _crisis() -> Crisis:
    return Crisis(
        id="c",
        title="Test",
        historical_outcome=HistoricalOutcome(
            escalation=0.6,
            measures=["coalition maritime", "médiation diplomatique", "libération de réserves"],
        ),
    )


def test_load_crises_parses_data_dir():
    crises = load_crises()
    ids = {c.id for c in crises}
    assert {"hormuz_energy_shock", "tech_sanctions", "satellite_interference"} <= ids
    hormuz = next(c for c in crises if c.id == "hormuz_energy_shock")
    assert hormuz.events and hormuz.events[0].actors == ["iran", "saudi_arabia"]
    assert hormuz.historical_outcome.measures  # issue historique renseignée


def test_compare_less_escalated():
    text = "Nous formons une coalition et appelons à la médiation."
    comp = compare_outcome(_crisis(), 0.35, text)
    assert comp.label == "moins escaladé"
    assert comp.gap < 0
    assert "coalition maritime" in comp.matched_measures
    assert "médiation diplomatique" in comp.matched_measures
    assert "libération de réserves" in comp.missed_measures
    assert "MOINS" in comp.explanation


def test_compare_more_escalated():
    comp = compare_outcome(_crisis(), 0.9, "Rupture des discussions, sanctions immédiates.")
    assert comp.label == "plus escaladé"
    assert comp.gap > 0
    assert comp.matched_measures == []  # aucune mesure historique retrouvée


def test_compare_conform():
    comp = compare_outcome(_crisis(), 0.62, "Communiqué équilibré.")
    assert comp.label == "conforme"


def test_comparison_gap_and_fields():
    comp = compare_outcome(_crisis(), 0.5, "texte")
    assert comp.historical_escalation == 0.6
    assert comp.simulated_escalation == 0.5
    assert isinstance(comp.explanation, str) and comp.explanation
