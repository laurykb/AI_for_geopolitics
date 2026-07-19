"""Tests du registre de griefs (G7-a, spec_g7_gamefeel lot 1) — déterministe, sans LLM."""

from simulation.grudges import Grief, GrudgeBook, load_gamefeel_params


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
    book.on_alliance_departure(
        leaver="france", tag="pact:france+usa", partners=["usa"], round_no=4
    )
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
