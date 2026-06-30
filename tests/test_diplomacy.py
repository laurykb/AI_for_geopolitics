"""Tests du DiplomacyEngine : propositions, accept/refuse, pactes, résumé."""

from core.country_state import CountryState, Economy, Military, Resources
from core.decisions import AgentDecision
from core.world_state import WorldState
from simulation.action_space import ActionType
from simulation.diplomacy import DiplomacyEngine, pact_id


def _country(cid: str, name: str, **kw) -> CountryState:
    return CountryState(
        id=cid,
        name=name,
        economy=Economy(gdp=1.0e12),
        military=Military(defense_budget=1.0e10),
        resources=Resources(),
        **kw,
    )


def _world(*countries: CountryState) -> WorldState:
    return WorldState.from_countries(list(countries))


def _decide(country: str, action: ActionType, target: str | None = None, **kw) -> AgentDecision:
    return AgentDecision(country=country, round_id=1, action=action, target=target, **kw)


def test_proposal_from_form_coalition_is_accepted_and_forms_pact():
    world = _world(_country("france", "France"), _country("usa", "USA"))
    engine = DiplomacyEngine()
    decisions = [_decide("france", ActionType.FORM_COALITION, "usa")]

    outcome = engine.resolve(world, decisions, 1)

    assert ("france", "usa") in outcome.pacts_formed
    assert world.share_alliance("france", "usa")  # pacte effectif
    assert pact_id("france", "usa") in world.countries["france"].alliances
    assert world.get_tension("france", "usa") < 0.0001  # rapproché (déjà 0, borné)
    # un message d'offre + un message de réponse
    assert len(outcome.messages) == 2
    assert "Pactes" in outcome.summary


def test_rivals_refuse():
    world = _world(
        _country("usa", "USA", rivals=["iran"]), _country("iran", "Iran", rivals=["usa"])
    )
    engine = DiplomacyEngine()
    outcome = engine.resolve(world, [_decide("usa", ActionType.SUPPORT, "iran")], 1)

    assert outcome.pacts_formed == []
    assert not world.share_alliance("usa", "iran")
    assert "Refus" in outcome.summary
    assert "rivalité" in outcome.messages[1].content


def test_high_tension_refuses():
    world = _world(_country("a", "A"), _country("b", "B"))
    world.adjust_tension("a", "b", 0.7)  # base 0.3 < seuil 0.5
    engine = DiplomacyEngine()
    outcome = engine.resolve(world, [_decide("a", ActionType.FORM_COALITION, "b")], 1)

    assert outcome.pacts_formed == []
    assert "Refus" in outcome.summary


def test_common_rival_overcomes_tension():
    world = _world(
        _country("a", "A", rivals=["z"]),
        _country("b", "B", rivals=["z"]),
        _country("z", "Z"),
    )
    world.adjust_tension("a", "b", 0.6)  # base 0.4 ; +0.3 rival commun -> 0.7 >= 0.5
    engine = DiplomacyEngine()
    outcome = engine.resolve(world, [_decide("a", ActionType.FORM_COALITION, "b")], 1)

    assert ("a", "b") in outcome.pacts_formed
    assert "rival commun" in outcome.messages[1].content


def test_proposed_alliances_field_generates_proposals():
    world = _world(_country("a", "A"), _country("b", "B"), _country("c", "C"))
    engine = DiplomacyEngine()
    decisions = [_decide("a", ActionType.CONDEMN, None, proposed_alliances=["b", "c"])]

    outcome = engine.resolve(world, decisions, 1)

    assert ("a", "b") in outcome.pacts_formed
    assert ("a", "c") in outcome.pacts_formed


def test_no_duplicate_pact_when_already_bound():
    world = _world(_country("a", "A"), _country("b", "B"))
    engine = DiplomacyEngine()
    engine.resolve(world, [_decide("a", ActionType.FORM_COALITION, "b")], 1)
    # second round, même proposition : pas de nouveau pacte signalé
    outcome = engine.resolve(world, [_decide("a", ActionType.FORM_COALITION, "b")], 2)

    assert outcome.pacts_formed == []
    assert world.countries["a"].alliances.count(pact_id("a", "b")) == 1


def test_unknown_and_self_targets_are_ignored():
    world = _world(_country("a", "A"))
    engine = DiplomacyEngine()
    decisions = [
        _decide("a", ActionType.FORM_COALITION, "a"),  # self
        _decide("a", ActionType.SUPPORT, "ghost"),  # inconnu
    ]
    outcome = engine.resolve(world, decisions, 1)
    assert outcome.messages == []
    assert outcome.summary == "Aucune proposition"
