"""Tests M8 — santé épistémique (part de vrai en circulation) + érosion de A4."""

import pytest

from simulation.epistemic import Claim, epistemic_health, reveal


def _claim(cid, veracity, belief=1.0, resolved=False):
    return Claim(
        id=cid, text="…", author="usa", veracity=veracity, belief=belief, resolved=resolved
    )


def test_health_intact_when_no_claims():
    assert epistemic_health([]) == 1.0


def test_health_full_when_all_true():
    assert epistemic_health([_claim("a", True), _claim("b", True)]) == pytest.approx(1.0)


def test_health_zero_when_all_false():
    assert epistemic_health([_claim("a", False), _claim("b", False)]) == pytest.approx(0.0)


def test_health_is_belief_weighted():
    # une fausse très crue pèse plus qu'une vraie peu crue
    claims = [_claim("t", True, belief=0.2), _claim("f", False, belief=0.8)]
    assert epistemic_health(claims) == pytest.approx(0.2)  # 0.2 vrai / 1.0 total


def test_resolved_claims_dont_pollute():
    # une fausse RÉSOLUE (véracité révélée) ne circule plus
    claims = [_claim("t", True), _claim("f", False, resolved=True)]
    assert epistemic_health(claims) == pytest.approx(1.0)
    assert _claim("f", False).is_disinfo() and not _claim("f", False, resolved=True).is_disinfo()


def test_reveal_settles_claim():
    false_claim = _claim("f", veracity=False, belief=0.9)
    reveal(false_claim)
    assert false_claim.resolved and false_claim.belief == 0.0
    true_claim = _claim("t", veracity=True, belief=0.3)
    reveal(true_claim)
    assert true_claim.resolved and true_claim.belief == 1.0


def test_epistemic_health_erodes_transparency_a4():
    from core.country_state import CountryState, Economy, Military, Resources
    from core.events import GeoEvent
    from core.risk import RiskScore
    from core.rounds import RoundSummary
    from core.world_state import WorldState
    from simulation.trajectory import TrajectoryEngine

    world = WorldState.from_countries(
        [
            CountryState(id=c, name=c, economy=Economy(gdp=1e12),
                         military=Military(defense_budget=1e10), resources=Resources())
            for c in ("a", "b")
        ]
    )
    summary = RoundSummary(
        round_id=1,
        event=GeoEvent(id="e", round_id=1, event_type="c", title="T"),
        decisions=[],
        risk=RiskScore(round_id=1, escalation=0.3, economic_disruption=0.0,
                       alliance_fracture=0.0, uncertainty=0.0),
    )
    engine = TrajectoryEngine()
    healthy = engine.update(world, summary, epistemic_health=1.0)
    polluted = engine.update(world, summary, epistemic_health=0.0)
    assert polluted.axes["A4"] < healthy.axes["A4"]  # désinformation -> transparence érodée
    assert polluted.utopia < healthy.utopia
