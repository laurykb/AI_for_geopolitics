"""Protocoles reproductibles, intervalles et traces auditables du laboratoire."""

import pytest

from simulation.research_lab import (
    FEATURED_PROTOCOL_IDS,
    STANDARD_MINIMUM_REPETITIONS_PER_GROUP,
    CourseOfAction,
    LabRunResult,
    ScenarioDeliberationTrace,
    ai_arms_dyadic_protocol,
    ai_arms_screening_protocol,
    assess_invariant,
    build_cells,
    default_protocols,
    featured_protocols,
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


def test_featured_protocol_ids_keeps_only_the_nuclear_threshold_experiment():
    """Décision user 2026-07-20 : « garde uniquement l'expérience du seuil nucléaire ».

    Le protocole du seuil nucléaire est `uranium-alpha-beta-v1` (carte 4 de la spec refonte
    labo : « le rapport de force fait-il franchir le seuil nucléaire ? ») — pas le protocole
    de langue (`language-framing-nuclear-v1`, la carte « langue → retenue ») ni le tournoi
    dyadique (`ai-arms-dyadic-tournament-v1`).
    """

    assert FEATURED_PROTOCOL_IDS == ("uranium-alpha-beta-v1",)


def test_featured_protocols_exposes_only_the_featured_ids_in_declared_order():
    protocols = featured_protocols()
    assert [protocol.id for protocol in protocols] == list(FEATURED_PROTOCOL_IDS)
    assert protocols[0].id == uranium_protocol().id


def test_featured_protocols_narrows_the_catalog_without_amputating_the_engine():
    """Catalogue resserré, pas amputé (décision 1) : les autres protocoles restent définis,
    valides et exécutables par le moteur — seule la vue catalogue les cache."""

    all_ids = {protocol.id for protocol in default_protocols()}
    assert set(FEATURED_PROTOCOL_IDS) <= all_ids
    assert len(default_protocols()) == 5  # non-régression : rien n'a été supprimé du moteur
    assert len(featured_protocols()) < len(default_protocols())


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
    # `research/runner.py` fige toujours `repetitions_per_cell` sur le nombre réellement choisi
    # (`model_copy`) : on reproduit ce geste ici pour construire un plan pilote explicite.
    pilot_protocol = protocol.model_copy(
        update={"repetitions_per_cell": protocol.pilot_repetitions_per_cell}
    )
    pilot = build_cells(
        pilot_protocol,
        factor_selection={
            "scenario": ["strategic_resource_race"],
            "temporal_condition": ["deadline"],
            "turn_limit": ["pilot_6"],
        },
    )
    assert len(pilot) == protocol.pilot_repetitions_per_cell
    assert pilot[0].factors["turn_limit"] == 6
    assert any(level.value == 40 for level in protocol.factors[2].levels)
    assert protocol.outcomes[0].id == "forecast_mae"


def test_research_question_is_a_single_non_empty_sentence():
    """Cadre §2 étape 1 (QUESTION) : une phrase falsifiable, pas un paragraphe."""

    for protocol in default_protocols():
        question = protocol.research_question.strip()
        assert question, f"{protocol.id} : research_question vide"
        # Une seule ponctuation de fin de phrase (?/./!), placée au dernier caractère :
        # heuristique simple d'« une phrase » qui tolère les virgules internes.
        terminal_marks = sum(char in ".?!" for char in question[:-1])
        assert terminal_marks == 0, f"{protocol.id} : research_question dépasse une phrase"
        assert question[-1] in ".?!"


def test_every_outcome_metric_has_a_label_and_a_one_sentence_description():
    """Cadre §2 étape 3 (MESURES) : jamais un identifiant nu, toujours une définition."""

    for protocol in default_protocols():
        for metric in protocol.outcomes:
            assert metric.label.strip(), f"{protocol.id}/{metric.id} : label vide"
            description = metric.description.strip()
            assert description, f"{protocol.id}/{metric.id} : description vide"
            terminal_marks = sum(char in ".?!" for char in description[:-1])
            assert terminal_marks == 0, (
                f"{protocol.id}/{metric.id} : description dépasse une phrase"
            )


def test_pilot_preset_is_declared_and_stays_under_the_standard_threshold():
    """Cadre §2 étape 2 (PROTOCOLE) : le pilote est une donnée déclarée, pas un piège silencieux."""

    for protocol in default_protocols():
        assert 1 <= protocol.pilot_repetitions_per_cell < STANDARD_MINIMUM_REPETITIONS_PER_GROUP
        factor_ids = {factor.id for factor in protocol.factors}
        assert set(protocol.pilot_factor_selection) <= factor_ids


def test_pilot_factor_selection_only_restricts_known_levels():
    dyadic = ai_arms_dyadic_protocol()
    scenario_ids = {level.id for level in dyadic.factors[0].levels}
    selected_scenarios = dyadic.pilot_factor_selection.get("scenario", [])
    assert selected_scenarios, "le pilote dyadique doit fixer un scénario par défaut"
    assert set(selected_scenarios) <= scenario_ids

    language = language_probe_protocol()
    language_ids = {level.id for level in language.factors[0].levels}
    hypothesis_only_ids = {
        level.id for level in language.factors[0].levels if level.hypothesis_only
    }
    selected_languages = set(language.pilot_factor_selection.get("language", []))
    assert selected_languages, "le pilote langue doit fixer au moins une langue"
    assert selected_languages <= language_ids
    # Le pilote ne doit jamais présenter comme acquise la langue marquée hypothèse non vérifiée.
    assert not (selected_languages & hypothesis_only_ids)


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


def _uranium_results(count: int, *, model_id: str = "model-a:1") -> list[LabRunResult]:
    return [
        LabRunResult(
            cell_id=f"c-{index}",
            protocol_id="uranium-alpha-beta-v1",
            factors={"alpha_win_prior": 0.8},
            repetition=index + 1,
            model_id=model_id,
            prompt_version="v1",
            seed=index,
            nuclear_use=index < count // 2,
            escalation_peak=300,
        )
        for index in range(count)
    ]


def test_small_completed_plan_reads_as_a_pilot_not_a_cliff_edge():
    """Cadre §2 étape 4 (RÉSULTAT) : protocole petit-n honnête (Galindez), pas un couperet."""

    results = _uranium_results(3)
    summary = summarize_results(
        "uranium-alpha-beta-v1",
        results,
        planned=3,
        failed=0,
        status="completed",
    )
    assert summary.verdict == "pilot"
    assert summary.verdict_label == "Pilote lisible — pas une preuve"
    assert "PAS" in summary.explanation
    assert "3" in summary.explanation


def test_thirty_repetitions_keep_the_historical_verdicts_unchanged():
    """Non-régression : le seuil standard (30) garde son verdict `descriptive` d'origine."""

    results = _uranium_results(30)
    summary = summarize_results(
        "uranium-alpha-beta-v1",
        results,
        planned=30,
        failed=0,
        status="completed",
    )
    assert summary.verdict == "descriptive"


def test_language_verdicts_still_resolve_replicated_qualified_not_replicated_at_thirty():
    """Non-régression des trois verdicts historiques de `_language_verdict` à n=30."""

    def cell(language: str, model_id: str, nuclear: bool, index: int) -> LabRunResult:
        return LabRunResult(
            cell_id=f"{language}-{model_id}-{index}",
            protocol_id="language-framing-nuclear-v1",
            factors={"language": language, "temporal_pressure": False},
            repetition=index + 1,
            model_id=model_id,
            prompt_version="v1",
            seed=index,
            nuclear_use=nuclear,
        )

    def summary_for(en_rate_all_true: bool, ja_rate_all_true: bool | None):
        results = [cell("en", "m", en_rate_all_true, i) for i in range(30)]
        if ja_rate_all_true is not None:
            results += [cell("ja", "m", ja_rate_all_true, i) for i in range(30)]
        return summarize_results(
            "language-framing-nuclear-v1",
            results,
            planned=len(results),
            failed=0,
            status="completed",
        )

    replicated = summary_for(True, False)
    assert replicated.verdict == "replicated"

    not_replicated = summary_for(False, True)
    assert not_replicated.verdict == "not_replicated"

    missing_stratum = summary_for(True, None)
    assert missing_stratum.verdict == "insufficient_data"


def test_cancelled_plan_with_partial_results_stays_insufficient_data():
    """`insufficient_data` reste réservé aux plans interrompus ou invalides (§3.5)."""

    results = _uranium_results(3)
    cancelled = summarize_results(
        "uranium-alpha-beta-v1",
        results,
        planned=30,
        failed=0,
        status="cancelled",
    )
    assert cancelled.verdict == "insufficient_data"
    assert cancelled.verdict != "pilot"


def test_small_plan_with_a_high_error_rate_stays_insufficient_data():
    """Un pilote n'est lisible que si le taux d'erreur reste raisonnable (§Tâche 2)."""

    results = _uranium_results(3)
    summary = summarize_results(
        "uranium-alpha-beta-v1",
        results,
        planned=9,
        failed=6,
        status="completed",
    )
    assert summary.verdict == "insufficient_data"


def test_failed_status_with_a_completed_small_plan_reads_as_pilot():
    """Revue (Critical) : `research/store.py` marque "failed" dès qu'UN run échoue, même un
    plan allé à son terme (attempted == planned). Le court-circuit ne doit s'appliquer qu'à
    `cancelled` : ici 9 réussis + 1 échec sur 10 prévus doit encore se lire comme un pilote."""

    results = _uranium_results(9)
    summary = summarize_results(
        "uranium-alpha-beta-v1",
        results,
        planned=10,
        failed=1,
        status="failed",
    )
    assert summary.verdict == "pilot"


def test_failed_status_with_a_completed_full_plan_keeps_its_normal_verdict():
    """Même bug côté plan complet : 30 réussis + 1 échec (statut "failed") ne doit pas
    régresser vers `insufficient_data` — l'ancien comportement (descriptive/replicated) doit
    être préservé quand le plan est allé à son terme."""

    results = _uranium_results(30)
    summary = summarize_results(
        "uranium-alpha-beta-v1",
        results,
        planned=31,
        failed=1,
        status="failed",
    )
    assert summary.verdict == "descriptive"


def test_failed_status_that_never_reached_its_planned_length_stays_insufficient_data():
    """Un "failed" réellement interrompu (attempted < planned) reste `insufficient_data`,
    avec un message honnête qui parle d'un plan non terminé, pas d'une annulation."""

    results = _uranium_results(5)
    summary = summarize_results(
        "uranium-alpha-beta-v1",
        results,
        planned=30,
        failed=1,
        status="failed",
    )
    assert summary.verdict == "insufficient_data"
    assert "6/30" in summary.explanation
    assert "terminé" in summary.explanation


def test_wilson_interval_stays_valid_at_zero_and_full_rate():
    """Non-régression : les bornes 0/n et n/n restent dans [0, 1] (docstring `wilson_interval`)."""

    zero = wilson_interval(0, 10)
    assert zero.rate == 0.0
    assert zero.confidence_low == 0.0
    assert 0.0 < zero.confidence_high < 1.0

    full = wilson_interval(10, 10)
    assert full.rate == 1.0
    assert full.confidence_high == pytest.approx(1.0)
    assert 0.0 < full.confidence_low < 1.0
