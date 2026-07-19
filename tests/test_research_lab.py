"""Protocoles reproductibles, intervalles et traces auditables du laboratoire."""

import pytest

from simulation.research_lab import (
    CourseOfAction,
    LabRunResult,
    ScenarioDeliberationTrace,
    ai_arms_dyadic_protocol,
    ai_arms_screening_protocol,
    assess_invariant,
    build_cells,
    language_probe_protocol,
    summarize_results,
    uranium_protocol,
    wilson_interval,
)


def test_uranium_protocol_builds_three_cells_times_thirty():
    protocol = uranium_protocol()
    cells = build_cells(protocol)
    assert protocol.cell_count == 3
    assert protocol.planned_runs == 90
    assert len(cells) == 90
    assert len({cell.id for cell in cells}) == 90
    assert len({cell.seed for cell in cells}) == 90
    assert {cell.factors["alpha_win_prior"] for cell in cells} == {0.8, 0.5, 0.2}
    assert [beat.round_no for beat in protocol.scenario_beats] == [1, 2, 3]
    assert all(beat.inter_round_activity and beat.measurement for beat in protocol.scenario_beats)
    assert "Comparer" in protocol.conclusion_rule


def test_language_claim_is_an_explicit_hypothesis_not_a_fact():
    protocol = language_probe_protocol()
    japanese = next(level for level in protocol.factors[0].levels if level.value == "ja")
    assert japanese.hypothesis_only is True
    assert any("n'est soutenu" in caveat for caveat in protocol.caveats)


def test_ai_arms_screening_exposes_seven_scenarios_and_both_roles():
    protocol = ai_arms_screening_protocol()
    assert protocol.cell_count == 14
    assert protocol.planned_runs == 420
    assert len(protocol.factors[0].levels) == 7
    assert {level.value for level in protocol.factors[1].levels} == {"alpha", "beta"}
    assert any("pas la réplication" in caveat for caveat in protocol.caveats)


def test_dyadic_protocol_supports_a_small_pilot_and_full_replication():
    protocol = ai_arms_dyadic_protocol()
    pilot = build_cells(
        protocol,
        factor_selection={
            "scenario": ["strategic_resource_race"],
            "temporal_condition": ["deadline"],
            "turn_limit": ["pilot_6"],
        },
    )
    assert len(pilot) == 1
    assert pilot[0].factors["turn_limit"] == 6
    assert any(level.value == 40 for level in protocol.factors[2].levels)
    assert protocol.outcomes[0].id == "forecast_mae"


def test_trace_rejects_a_selection_that_was_not_proposed():
    option = CourseOfAction(id="hold", label="Maintenir", confidence=0.5)
    with pytest.raises(ValueError, match="selected_course_id"):
        ScenarioDeliberationTrace(
            situation_summary="Crise contrôlée",
            courses_of_action=[option, option.model_copy(update={"id": "signal"})],
            challenge_summary="Risque de perception adverse",
            selected_course_id="unknown",
            public_statement="Nous maintenons notre position.",
        )


def test_raw_provider_trace_normalizes_percent_and_preserves_declared_selection():
    trace = ScenarioDeliberationTrace.model_validate(
        {
            "situation_summary": "Pression contrôlée.",
            "courses_of_action": [
                {"id": "hold", "label": "Maintenir", "confidence": 75},
                {"id": "signal", "label": "Signaler", "confidence": 25},
            ],
            "challenge_summary": "Incertitude élevée.",
            "selected_course_id": "Option tierce déclarée",
            "public_statement": "Position maintenue.",
        }
    )
    assert trace.courses_of_action[0].confidence == 0.75
    assert trace.selected_course_id == "Option tierce déclarée"
    assert any(course.id == trace.selected_course_id for course in trace.courses_of_action)
    assert trace.normalization_notes


def test_wilson_interval_and_invariant_do_not_overclaim_small_samples():
    estimate = wilson_interval(20, 21)
    assert estimate.rate == pytest.approx(20 / 21)
    assert estimate.confidence_low < 0.9
    results = [
        LabRunResult(
            cell_id=f"c-{index}",
            protocol_id="p",
            factors={},
            repetition=index + 1,
            model_id="m",
            prompt_version="v1",
            seed=index,
            nuclear_use=index < 20,
        )
        for index in range(21)
    ]
    invariant = assess_invariant(results, minimum_rate=0.9)
    assert invariant.supported is False
    assert "protocole" in invariant.caveat


def test_summary_stays_provisional_then_reports_wilson_groups():
    results = [
        LabRunResult(
            cell_id=f"c-{index}",
            protocol_id="uranium-alpha-beta-v1",
            factors={"alpha_win_prior": 0.8},
            repetition=index + 1,
            model_id="model-a:1",
            prompt_version="v1",
            seed=index,
            nuclear_use=index < 12,
            nuclear_signal=index < 20,
            moral_constraint_present=index % 2 == 0,
            decision_latency_s=float(index + 1),
            escalation_peak=450 if index < 12 else 125,
        )
        for index in range(30)
    ]
    provisional = summarize_results(
        "uranium-alpha-beta-v1",
        results[:5],
        planned=30,
        failed=0,
        status="running",
    )
    assert provisional.verdict == "running"

    complete = summarize_results(
        "uranium-alpha-beta-v1",
        results,
        planned=30,
        failed=0,
        status="completed",
    )
    assert complete.verdict == "descriptive"
    assert complete.groups[0].nuclear_use.rate == pytest.approx(0.4)
    assert complete.groups[0].nuclear_use.confidence_low < 0.4
    assert complete.groups[0].median_latency_s == 15.5
