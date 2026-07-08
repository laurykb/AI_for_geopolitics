"""Marchés vivants (G12 §1) — génération « le LLM habille, le code résout ».

L'assemblage choisit des prédicats PERTINENTS validés (max 3, dédoublonnés), la censure
ouvre TOUJOURS son marché (règle fixe), et un repli par règles fixes garantit un book même
si le JSON du LLM est invalide. La résolution mappe le prédicat → issue YES/NO (ou ouvert).
"""

from market.flash import MarketState, assemble_flash_specs, parse_specs, resolve_flash
from market.models import ResolutionCriterion, ResolutionKind
from market.predicates import MarketContext


def test_motion_always_opens_its_market():
    # Une censure déposée ouvre TOUJOURS son marché, même sans proposition du LLM.
    specs = assemble_flash_specs([], MarketState(current_round=2, motion_target="russia"))
    assert any(s.predicate == "motion_upheld" and s.params["target"] == "russia" for s in specs)


def test_llm_specs_validated_deduped_capped():
    u = {"threshold": 0.55, "round": 4}
    rung = {"k": 4, "before_round": 6}
    raw = [
        {"predicate": "u_above", "params": u, "question": "U>0,55 ?"},
        {"predicate": "rung_reached", "params": rung, "question": "palier ?"},
        {"predicate": "inconnu", "params": {}, "question": "?"},  # hors catalogue → rejeté
        {"predicate": "pact_signed", "params": {"a": "iran"}, "question": "?"},  # params manquants
        {"predicate": "u_above", "params": u, "question": "dup"},  # doublon
    ]
    specs = assemble_flash_specs(raw, MarketState(current_round=2), max_open=3)
    preds = [s.predicate for s in specs]
    assert "u_above" in preds and "rung_reached" in preds
    assert "inconnu" not in preds
    assert preds.count("u_above") == 1  # dédoublonné
    assert len(specs) <= 3


def test_fallback_when_no_valid_llm_specs():
    invalid = [{"predicate": "inconnu", "params": {}}]
    specs = assemble_flash_specs(invalid, MarketState(current_round=2))
    assert specs  # repli par règles fixes → au moins un book ouvert


def test_parse_specs_tolerant():
    assert parse_specs("pas du json") == []
    raw = '[{"predicate":"u_above","params":{"threshold":0.55,"round":4},"question":"?"}]'
    got = parse_specs(raw)
    assert got and got[0]["predicate"] == "u_above"


def test_resolve_flash_maps_yes_no_open():
    crit = ResolutionCriterion(
        kind=ResolutionKind.PREDICATE, predicate="u_above", params={"threshold": 0.55, "round": 3}
    )
    assert resolve_flash(crit, MarketContext(current_round=2)) is None  # OPEN → None
    assert resolve_flash(crit, MarketContext(current_round=3, utopia=0.6)) == "YES"
    assert resolve_flash(crit, MarketContext(current_round=3, utopia=0.5)) == "NO"
