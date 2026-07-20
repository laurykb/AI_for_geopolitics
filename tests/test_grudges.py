"""Tests du registre de griefs (G7-a, spec_g7_gamefeel lot 1) — déterministe, sans LLM."""

from simulation.grudges import (
    GamefeelParams,
    Grief,
    GrudgeBook,
    TimeBudgetParams,
    load_gamefeel_params,
    sampling_for_temperament,
)


def _grief(kind: str, weight: float, round_no: int = 1, summary: str = "x") -> Grief:
    return Grief(type=kind, round_no=round_no, weight=weight, summary=summary)


def test_params_load_with_expected_shape():
    p = load_gamefeel_params()
    assert p.grudges.weights["pact_broken"] == -5
    assert p.grudges.balance_cap == 10
    assert p.grudges.decay_every_rounds == 3
    assert p.deadlines.treaty_duration_rounds == 3
    assert 0.0 <= p.directives.public_refusal_threshold <= 1.0


def test_trajectory_params_load_with_expected_shape():
    # Brief 3 pt 3 — le pas/cap des 5 axes est externalisé (équilibrage Cowork sans code).
    p = load_gamefeel_params().trajectory
    assert p.cap == 0.09
    assert p.concentration_k > 0.0
    assert p.deadband == 0.02  # IMPORTANT 2 (revue) : évite le cycle-limite ± cap


def test_deltas_params_carry_mute_fallback():
    # Brief 3 pt 3 — repli déterministe (stabilité) quand le juge est muet sur un pays.
    p = load_gamefeel_params().deltas
    assert p.mute_fallback == 0.03


def test_sampling_temperaments_load_with_expected_shape():
    # Chantier dialogue limpide — un bloc par tempérament G17, distinct du socle "country".
    p = load_gamefeel_params().sampling
    assert p.country.temperature == 0.8 and p.country.repeat_penalty == 1.15
    assert p.temperaments["colombe"].temperature == 0.75
    assert p.temperaments["faucon"].temperature == 0.85
    assert p.temperaments["opportuniste"].temperature == 0.9
    # les trois profils sont bien distincts (sinon la nuance de registre n'existe pas)
    temps = {t.temperature for t in p.temperaments.values()}
    assert len(temps) == 3


def test_sampling_for_temperament_returns_the_matching_profile():
    p = load_gamefeel_params()
    assert sampling_for_temperament(p, "colombe") == p.sampling.temperaments["colombe"]
    assert sampling_for_temperament(p, "faucon") == p.sampling.temperaments["faucon"]


def test_time_budget_params_load_from_json_with_expected_shape():
    # Chantier budget-temps — le JSON (data/gamefeel/params.json -> "time_budgets") est
    # lu avec les mêmes valeurs que les défauts Python (test suivant) : une seule source
    # de vérité, équilibrable par Cowork sans toucher au code.
    p = load_gamefeel_params().time_budgets
    assert p.think_seconds == 60.0
    assert p.speak_seconds == 35.0
    assert p.decision_rescue_tokens == 250


def test_time_budget_python_defaults_match_the_json_defaults():
    # Défauts Python identiques au JSON (décision 4) : un GAMEFEEL_PARAMS_PATH pointant
    # vers un ancien fichier SANS le bloc "time_budgets" retombe donc sur ce même repos.
    assert TimeBudgetParams() == load_gamefeel_params().time_budgets


def test_gamefeel_params_without_time_budgets_key_falls_back_to_python_defaults():
    # Rétro-compat : un JSON d'avant ce chantier (sans la clé "time_budgets") continue de
    # se charger — Pydantic comble avec les défauts Python (identiques au JSON courant).
    legacy = GamefeelParams.model_validate({})
    assert legacy.time_budgets == TimeBudgetParams()


def test_sampling_for_temperament_falls_back_to_country_for_unknown_temperament():
    p = load_gamefeel_params()
    assert sampling_for_temperament(p, "inconnu") == p.sampling.country
    assert sampling_for_temperament(p, "") == p.sampling.country


def test_sampling_for_temperament_falls_back_when_json_has_no_temperaments_block():
    # Rétro-compat — un GamefeelParams construit sans le bloc "temperaments" (JSON
    # antérieur à ce chantier, ou fixture de test minimale) ne casse rien : Pydantic
    # comble avec les défauts Python, identiques au JSON par défaut du dépôt.
    minimal = GamefeelParams.model_validate({})
    assert sampling_for_temperament(minimal, "colombe").temperature == 0.75
    assert sampling_for_temperament(minimal, "totalement-inconnu") == minimal.sampling.country


def test_balance_is_bounded_and_directional():
    book = GrudgeBook()
    for _ in range(4):
        book.add("usa", "france", _grief("disinfo_exposed", -6))
    assert book.balance("usa", "france") == -10  # borné à −cap
    assert book.balance("france", "usa") == 0.0  # directionnel
    assert book.balance("usa", "china") == 0.0


def test_decay_every_three_rounds_toward_zero_keeps_history():
    book = GrudgeBook()
    book.add("usa", "france", _grief("pact_broken", -5, round_no=2, summary="pacte rompu"))
    book.decay(round_no=3)  # multiple de 3 → ±1 vers 0
    assert book.balance("usa", "france") == -4
    book.decay(round_no=4)  # pas un multiple → rien
    assert book.balance("usa", "france") == -4
    book.decay(round_no=6)
    assert book.balance("usa", "france") == -3
    # le grief d'origine n'est jamais effacé (il s'estompe, il ne disparaît pas)
    kinds = [g.type for g in book.grudges["usa"]["france"]]
    assert "pact_broken" in kinds and "decay" in kinds


def test_prompt_lines_name_the_grief_and_the_stance():
    book = GrudgeBook()
    book.add("usa", "france", _grief("pact_broken", -5, round_no=3, summary="a rompu le pacte"))
    book.add("usa", "china", _grief("motion_support", 3, round_no=2, summary="a plaidé pour nous"))
    lines = book.prompt_lines("usa", {"france": "France", "china": "Chine"})
    text = "\n".join(lines)
    assert "France" in text and "a rompu le pacte" in text
    assert "méfiance" in text  # solde ≤ −3
    assert "confiance" in text  # solde ≥ +3
    assert book.prompt_lines("france", {}) == []  # aucun grief → aucune ligne


def test_alliance_departure_aggrieves_remaining_partners():
    book = GrudgeBook()
    book.on_alliance_departure(leaver="france", tag="pact:france+usa", partners=["usa"], round_no=4)
    assert book.balance("usa", "france") == -5  # pact_broken
    assert book.balance("france", "usa") == 0.0


def test_motion_votes_feed_the_book():
    book = GrudgeBook()
    # une SI dépose une motion contre l'iran → trahison aux yeux de l'iran ; les griefs
    # suivants découlent du VOTE réel de chacun (G9 §2).
    book.on_motion_votes(
        target="iran",
        filed_by="usa",
        votes=[("usa", "pour"), ("china", "contre")],
        round_no=2,
    )
    assert book.balance("iran", "usa") == -4  # le dépôt (le vote ne compte pas double)
    assert book.balance("iran", "china") == 3  # a voté contre la motion → soutien
    # motion humaine : seule la voix des SI laisse des traces
    book2 = GrudgeBook()
    book2.on_motion_votes(
        target="iran", filed_by="human", votes=[("usa", "abstention")], round_no=2
    )
    assert book2.balance("iran", "usa") == 0.0  # l'abstention ne laisse pas de trace


def test_roundtrip_survives_snapshot():
    book = GrudgeBook()
    book.add("usa", "france", _grief("pact_broken", -5, summary="pacte rompu"))
    restored = GrudgeBook.model_validate(book.model_dump(mode="json"))
    assert restored.balance("usa", "france") == -5
