"""Tests de l'engagement et de l'ordonnanceur de parole dynamique (déterministe)."""

from core.country_state import CountryState, Economy, Military, Resources
from core.events import GeoEvent
from core.world_state import WorldState
from simulation.engagement import SPEAK_THRESHOLD, engagement_score
from simulation.negotiation import NegotiationMessage, TurnDirector, speaking_order


def _c(cid, name, **kw):
    return CountryState(
        id=cid,
        name=name,
        economy=Economy(gdp=1e12, growth=2.0),
        military=Military(defense_budget=1e10, projection=0.5),
        resources=Resources(),
        political_stability=0.5,
        technology_level=0.5,
        **kw,
    )


def _world():
    return WorldState.from_countries(
        [_c("usa", "USA"), _c("iran", "Iran"), _c("france", "France"), _c("egypt", "Egypte")]
    )


def _event(actors, severity=0.6):
    return GeoEvent(
        id="e1", round_id=1, event_type="incident", title="Crise", actors=actors, severity=severity
    )


def test_actor_scores_higher_than_bystander():
    world = _world()
    event = _event(["usa"])
    assert engagement_score("usa", event, world, [], {}) > engagement_score(
        "france", event, world, [], {}
    )


def test_addressed_country_gets_boost_interruption():
    world = _world()
    event = _event(["usa", "iran"])
    base = engagement_score("france", event, world, [], {})
    last = [NegotiationMessage(country="usa", text="La France doit choisir.")]
    addressed = engagement_score("france", event, world, last, {})
    assert addressed > base + 0.4  # forte envie de réagir quand on est interpellé


def test_fatigue_reduces_score():
    world = _world()
    event = _event(["usa"])
    fresh = engagement_score("usa", event, world, [], {})
    tired = engagement_score("usa", event, world, [], {"usa": 2})
    assert tired < fresh


def test_unconcerned_country_below_threshold():
    world = _world()
    event = _event(["usa"], severity=0.1)  # événement mineur, france n'est pas actrice
    assert engagement_score("france", event, world, [], {}) < SPEAK_THRESHOLD


def _drain(director, event, world):
    """Joue la négociation entière (sans LLM) et renvoie la séquence des orateurs."""
    order = []
    while (cid := director.next_speaker(event, world, [])) is not None:
        order.append(cid)
        director.commit(cid)
    return order


def test_director_respects_max_turns():
    world = _world()
    world.adjust_tension("usa", "iran", 0.9)  # forte tension -> engagement élevé et durable
    event = _event(["usa", "iran"])
    director = TurnDirector(speaking_order(list(world.countries), event), max_turns=3)
    order = _drain(director, event, world)
    assert len(order) <= 3
    assert director.turns_taken == len(order)


def test_director_allows_repeats():
    world = _world()
    world.adjust_tension("usa", "iran", 0.9)
    event = _event(["usa", "iran"])
    director = TurnDirector(speaking_order(list(world.countries), event), max_turns=8)
    order = _drain(director, event, world)
    # un pays très engagé peut reprendre la parole plusieurs fois
    assert any(order.count(cid) >= 2 for cid in set(order))


def test_director_is_deterministic():
    world = _world()
    world.adjust_tension("usa", "iran", 0.7)
    event = _event(["usa", "iran"])
    order = speaking_order(list(world.countries), event)
    a = _drain(TurnDirector(order, max_turns=6), event, world)
    b = _drain(TurnDirector(order, max_turns=6), event, world)
    assert a == b


def test_director_silent_lists_unspoken():
    world = _world()
    event = _event(["usa", "iran"], severity=0.2)  # france/egypte peu concernées
    director = TurnDirector(speaking_order(list(world.countries), event), max_turns=6)
    _drain(director, event, world)
    silent = director.silent()
    assert "france" in silent or "egypt" in silent  # au moins un spectateur reste muet


def test_priority_country_is_scheduled():
    world = _world()
    event = _event(["usa"], severity=0.1)  # france serait normalement muette
    assert engagement_score("france", event, world, [], {}) < SPEAK_THRESHOLD
    director = TurnDirector(["france"], max_turns=1, priority="france")
    assert director.next_speaker(event, world, []) == "france"  # le joueur humain participe


def test_no_speaker_when_budget_zero():
    world = _world()
    event = _event(["usa"])
    director = TurnDirector(speaking_order(list(world.countries), event), max_turns=0)
    assert director.next_speaker(event, world, []) is None
