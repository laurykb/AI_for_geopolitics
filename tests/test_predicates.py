"""Marchés vivants (G12 §1) — catalogue de prédicats RÉSOLUBLES par code.

« Le LLM habille, le code résout » : chaque prédicat rend YES / NO / OPEN à partir de
l'état de fin de round (jamais du texte). Trichotomie testée : condition atteinte (YES),
horizon dépassé sans elle (NO), sinon encore ouvert (OPEN). + validation des params.
"""

from market.predicates import MarketContext, is_valid, resolve_predicate


def _ctx(**kw) -> MarketContext:
    base = dict(
        current_round=2,
        pacts=set(),
        pacts_broken=set(),
        motion_verdicts=[],
        motions_filed_rounds=[],
        ladder_reached=0,
        tensions={},
        deltas={},
        utopia=0.5,
        suspended=set(),
        deadlines_honored=set(),
        game_over=False,
    )
    base.update(kw)
    return MarketContext(**base)


def test_pact_signed_trichotomy():
    p = {"a": "iran", "b": "china", "before_round": 5}
    assert resolve_predicate("pact_signed", p, _ctx()) == "OPEN"  # rien encore, horizon loin
    assert resolve_predicate("pact_signed", p, _ctx(pacts={frozenset({"iran", "china"})})) == "YES"
    assert resolve_predicate("pact_signed", p, _ctx(current_round=5)) == "NO"  # horizon dépassé


def test_resolve_is_defensive_on_bad_params():
    # Prédicat connu mais params manquants/mal typés → OPEN, jamais de KeyError : le
    # résolveur ne voit que des params validés (garde-fou étendu à resolve_predicate).
    assert resolve_predicate("pact_signed", {}, _ctx()) == "OPEN"  # "a"/"b" manquants
    assert resolve_predicate("pact_signed", {"a": "iran"}, _ctx()) == "OPEN"  # "b" manquant
    assert resolve_predicate("inconnu", {"x": 1}, _ctx()) == "OPEN"  # prédicat inconnu


def test_motion_upheld():
    p = {"target": "russia"}
    assert resolve_predicate("motion_upheld", p, _ctx()) == "OPEN"
    yes = _ctx(motion_verdicts=[{"country": "russia", "upheld": True}])
    no = _ctx(motion_verdicts=[{"country": "russia", "upheld": False}])
    assert resolve_predicate("motion_upheld", p, yes) == "YES"
    assert resolve_predicate("motion_upheld", p, no) == "NO"


def test_rung_reached():
    p = {"k": 4, "before_round": 6}
    assert resolve_predicate("rung_reached", p, _ctx(ladder_reached=3)) == "OPEN"
    assert resolve_predicate("rung_reached", p, _ctx(ladder_reached=4)) == "YES"
    assert resolve_predicate("rung_reached", p, _ctx(ladder_reached=3, current_round=6)) == "NO"


def test_tension_below_resolves_at_round():
    p = {"a": "usa", "b": "iran", "threshold": 0.3, "round": 3}
    assert resolve_predicate("tension_below", p, _ctx(current_round=2)) == "OPEN"
    low = _ctx(current_round=3, tensions={("iran", "usa"): 0.2})
    high = _ctx(current_round=3, tensions={("iran", "usa"): 0.5})
    assert resolve_predicate("tension_below", p, low) == "YES"
    assert resolve_predicate("tension_below", p, high) == "NO"


def test_u_above_resolves_at_round():
    p = {"threshold": 0.55, "round": 4}
    assert resolve_predicate("u_above", p, _ctx(current_round=3)) == "OPEN"
    assert resolve_predicate("u_above", p, _ctx(current_round=4, utopia=0.6)) == "YES"
    assert resolve_predicate("u_above", p, _ctx(current_round=4, utopia=0.5)) == "NO"


def test_suspension_before_end():
    p: dict = {}
    assert resolve_predicate("suspension_before_end", p, _ctx()) == "OPEN"
    assert resolve_predicate("suspension_before_end", p, _ctx(suspended={"iran"})) == "YES"
    # partie finie sans suspension → NO.
    assert resolve_predicate("suspension_before_end", p, _ctx(game_over=True)) == "NO"


def test_validation_rejects_unknown_and_missing_params():
    assert is_valid("pact_signed", {"a": "iran", "b": "china", "before_round": 5}) is True
    assert is_valid("inconnu", {}) is False  # prédicat hors catalogue
    assert is_valid("pact_signed", {"a": "iran"}) is False  # params manquants
    assert is_valid("rung_reached", {"k": "quatre", "before_round": 5}) is False  # type invalide
