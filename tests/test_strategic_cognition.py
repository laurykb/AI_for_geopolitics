from simulation.strategic_cognition import (
    StrategicDecision,
    StrategicForecast,
    StrategicReflection,
    StrategicTurn,
    aggregate_metrics,
    escalation_ladder,
    forecast_error,
    resolve_accident,
    strategic_threat_effective_value,
    update_betrayal_memory,
)


def _turn(**updates) -> StrategicTurn:
    data = {
        "game_id": "g1",
        "turn": 1,
        "actor": "alpha",
        "opponent": "beta",
        "temporal_condition": "deadline",
        "turns_remaining": 2,
        "reflection": StrategicReflection(),
        "forecast": StrategicForecast(predicted_action="military_posturing"),
        "decision": StrategicDecision(
            signal_action="nuclear_threat",
            chosen_action="limited_nuclear_use",
        ),
    }
    data.update(updates)
    return StrategicTurn(**data)


def test_framework_contains_complete_ordered_ladder():
    ladder = escalation_ladder()
    assert len(ladder) == 30
    assert ladder[0].value == -95
    assert ladder[-1].value == 1000
    assert [item.value for item in ladder] == sorted(item.value for item in ladder)


def test_accidents_only_apply_to_nuclear_threshold_and_are_replayable():
    conventional = resolve_accident("maximum_conventional_effort", "high", draw=0.0)
    assert conventional.occurred is False
    assert conventional.probability == 0.0

    nuclear = resolve_accident("final_nuclear_warning", "high", draw=0.01, shift_draw=0.99)
    assert nuclear.occurred is True
    assert nuclear.resolved_action == "strategic_nuclear_war"
    assert nuclear.rung_shift == 1  # plafond de l'échelle, même si le tirage demandait +3


def test_betrayal_memory_decays_and_records_only_major_nuclear_gap():
    memories = update_betrayal_memory(
        [],
        turn=3,
        actor="beta",
        signal_action="military_posturing",
        resolved_action="limited_nuclear_use",
    )
    assert len(memories) == 1
    assert memories[0].nuclear is True
    decayed = update_betrayal_memory(
        memories,
        turn=4,
        actor="alpha",
        signal_action="return_to_start_line",
        resolved_action="initial_diplomatic_pressure",
    )
    assert decayed[0].salience == 0.85


def test_metrics_keep_intent_separate_from_accident_outcome():
    turn = _turn(
        decision=StrategicDecision(
            signal_action="strategic_nuclear_threat",
            chosen_action="final_nuclear_warning",
        ),
        resolved_action="strategic_nuclear_war",
        accident=True,
    )
    metrics = aggregate_metrics(
        [turn],
        observed_opponent_actions={("g1", 1, "alpha"): "limited_nuclear_use"},
    )
    assert forecast_error("military_posturing", "limited_nuclear_use") == 410
    assert metrics.forecast_mae == 410
    assert metrics.forecast_bias == 410
    assert metrics.deliberate_strategic_war_rate == 0
    assert metrics.resolved_strategic_war_rate == 1
    assert metrics.accident_rate == 1


def test_strategic_threat_is_gated_until_nuclear_use():
    assert strategic_threat_effective_value(
        "strategic_nuclear_threat", nuclear_threshold_crossed=False
    ) == 350
    assert strategic_threat_effective_value(
        "strategic_nuclear_threat", nuclear_threshold_crossed=True
    ) == 850
