"""Prévisions inter-mode : branche choisie, réponse observée et calibration."""

import pytest

from simulation.scenario_forecasts import (
    classify_response,
    parse_chosen_forecasts,
    summarize_forecasts,
)


def test_only_the_chosen_future_is_scored():
    reasoning = (
        "FUTUR 1 | option: compromis | réponses prévues: iran=coopere: accepte | "
        "issue: accord | utilité: 70 | confiance: 80\n"
        "FUTUR 2 | option: pression | réponses prévues: "
        "iran=contre_escalade: sanctions | issue: tension | utilité: 60 | confiance: 65\n"
        "CHOIX | FUTUR 2 | motif: levier\n"
        "INCERTITUDE | cohésion adverse"
    )
    rows = parse_chosen_forecasts(
        reasoning,
        source="usa",
        round_no=2,
        participants={"usa", "iran"},
    )
    assert len(rows) == 1
    assert rows[0].future_no == 2
    assert rows[0].predicted_response == "contre_escalade"
    assert rows[0].confidence == pytest.approx(0.65)


def test_response_classifier_is_conservative_and_metrics_keep_pending_rows():
    assert classify_response("resiste: refuse l'offre") == "resiste"
    assert classify_response("menace de sanctions") == "contre_escalade"
    rows = parse_chosen_forecasts(
        "FUTUR 1 | option: attendre | réponses prévues: iran=temporise: silence | "
        "issue: attente | utilité: 40 | confiance: 50\nCHOIX | FUTUR 1 | motif: prudence",
        source="usa",
        round_no=1,
        participants={"usa", "iran"},
    )
    summary = summarize_forecasts(rows)["usa"]
    assert summary.evaluated == 0
    assert summary.pending == 1
    assert summary.exact_rate is None


def test_observable_journal_forecast_is_calibrated_too():
    reasoning = """FUTUR 1 — compromis
Action : proposer un contrôle conjoint
Réactions anticipées : iran=coopere: accepte une vérification
Chaîne causale : accord limité
Évaluation : utilité 72/100 · risque 18/100 · confiance 64/100

FUTUR 2 — pression
Action : annoncer une sanction réversible
Réactions anticipées : iran=resiste: refuse le calendrier
Chaîne causale : blocage
Évaluation : utilité 50/100 · risque 45/100 · confiance 61/100

FUTUR 3 — attente
Action : demander une session technique
Réactions anticipées : iran=temporise: attend de nouvelles données
Chaîne causale : décision différée
Évaluation : utilité 40/100 · risque 10/100 · confiance 55/100

ARBITRAGE
Choix : FUTUR 1
"""
    rows = parse_chosen_forecasts(
        reasoning,
        source="usa",
        round_no=3,
        participants={"usa", "iran"},
    )
    assert len(rows) == 1
    assert rows[0].option_summary == "proposer un contrôle conjoint"
    assert rows[0].predicted_response == "coopere"
    assert rows[0].confidence == pytest.approx(0.64)
