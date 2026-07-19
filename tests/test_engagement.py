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


def test_director_max_turns_caps_repeats_once_floor_is_met():
    # Le budget ne borne plus que les RÉPÉTITIONS au-delà du plancher (décision user,
    # tour de table minimal) : avec 4 candidats et un budget de 3, le plancher force
    # quand même les 4 à parler — seul le nombre de reprises reste plafonné par le budget.
    world = _world()
    world.adjust_tension("usa", "iran", 0.9)  # forte tension -> engagement élevé et durable
    event = _event(["usa", "iran"])
    candidates = speaking_order(list(world.countries), event)
    director = TurnDirector(candidates, max_turns=3)
    order = _drain(director, event, world)
    assert set(order) == set(candidates)  # le plancher dépasse le budget configuré
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


def test_director_floor_leaves_nobody_silent_after_full_drain():
    # Avant le plancher (décision user), un spectateur peu concerné pouvait ne jamais
    # parler du round. Désormais un tour de table complet est garanti avant la clôture.
    world = _world()
    event = _event(["usa", "iran"], severity=0.2)  # france/egypte peu concernées
    director = TurnDirector(speaking_order(list(world.countries), event), max_turns=6)
    _drain(director, event, world)
    assert director.silent() == []  # plus personne n'est oublié


def test_priority_country_is_scheduled():
    world = _world()
    event = _event(["usa"], severity=0.1)  # france serait normalement muette
    assert engagement_score("france", event, world, [], {}) < SPEAK_THRESHOLD
    director = TurnDirector(["france"], max_turns=1, priority="france")
    assert director.next_speaker(event, world, []) == "france"  # le joueur humain participe


def test_budget_zero_still_forces_the_floor():
    # Le plancher (décision user) prime sur le budget configuré : même à budget 0, un
    # round avec des candidats ne peut pas se clore sans qu'ils aient parlé une fois
    # (budget effectif = max(budget configuré, nombre de candidats)).
    world = _world()
    event = _event(["usa"])
    director = TurnDirector(speaking_order(list(world.countries), event), max_turns=0)
    assert director.next_speaker(event, world, []) is not None


def test_no_speaker_when_no_candidates():
    world = _world()
    event = _event(["usa"])
    director = TurnDirector([], max_turns=6)
    assert director.next_speaker(event, world, []) is None


def test_priority_boost_only_before_first_turn():
    # Le boost garantit UNE prise de parole au joueur humain ; ensuite il concourt
    # normalement (un boost permanent lui faisait monopoliser la table — Joueur-pays web).
    world = _world()
    event = _event(["usa"], severity=0.1)  # france serait normalement muette
    director = TurnDirector(["france"], max_turns=3, priority="france")
    assert director.next_speaker(event, world, []) == "france"
    director.commit("france")
    assert director.next_speaker(event, world, []) is None  # plus de boost : sous le seuil


def test_director_never_leaves_summit_mute():
    # Garde-fou (décision user) : casting prudent + événement mineur dont aucun acteur
    # ne siège -> personne ne franchit le seuil, mais le sommet ne reste pas muet :
    # le plus concerné ouvre quand même la séance. Le plancher (tour de table minimal)
    # prend ensuite le relais : la séance se poursuit jusqu'à ce que TOUT le monde ait
    # parlé — il n'y a plus de silence forcé après le premier orateur.
    world = _world()
    event = _event(["china"], severity=0.1)  # l'acteur n'est même pas à la table
    candidates = speaking_order(list(world.countries), event)
    director = TurnDirector(candidates, max_turns=6)
    first = director.next_speaker(event, world, [])
    assert first is not None  # au moins un orateur
    director.commit(first)
    order = [first, *_drain(director, event, world)]
    assert set(order) == set(candidates)  # le tour de table se termine, personne n'est oublié


def test_military_ally_of_actor_gains_solidarity():
    # Spec alliances→moteur (2026-07-07) : un NON-acteur qui partage une alliance
    # MILITAIRE avec un acteur s'engage (+0,15 — l'OTAN se lève pour un allié) ;
    # un spectateur sans alliance reste au niveau de base (jitter ±0,05 près).
    world = WorldState.from_countries(
        [
            _c("usa", "USA", alliances=["NATO"]),
            _c("france", "France", alliances=["NATO"]),
            _c("egypt", "Egypte"),
        ]
    )
    event = _event(["usa"], severity=0.5)
    ally = engagement_score("france", event, world, [], {})
    bystander = engagement_score("egypt", event, world, [], {})
    assert ally > bystander + 0.09  # +0,15 de solidarité, moins l'écart de jitter


def test_economic_or_informal_tags_give_no_solidarity():
    # La cohésion économique joue au communiqué, pas à la prise de parole ;
    # un bloc d'affinité (Western, informel) ne pèse pas du tout.
    world = WorldState.from_countries(
        [
            _c("usa", "USA", alliances=["Western", "USMCA"]),
            _c("canada", "Canada", alliances=["Western", "USMCA"]),
            _c("iran", "Iran"),
        ]
    )
    event = _event(["usa"], severity=0.5)
    partner = engagement_score("canada", event, world, [], {})
    bystander = engagement_score("iran", event, world, [], {})
    assert abs(partner - bystander) <= 0.06  # rien au-delà du jitter


# --- Plancher : tour de table minimal (décision user, 2026-07-19) ------------------
# Retour utilisateur : « un round peut se finir avec un seul pays qui parle ». Décision
# arbitrée : chaque pays candidat (donc actif, non suspendu — les suspendus sont déjà
# retirés des candidats en amont) parle AU MOINS UNE FOIS par round. Le budget
# (`max_turns`, modes Cheap/Balanced/Full) ne borne plus que les échanges AU-DELÀ de ce
# tour de table complet : budget effectif = max(budget configuré, nombre de candidats).


def _muted_event():
    """Acteur hors table + sévérité nulle -> tous les candidats restent sous le seuil."""
    return _event(["ghost"], severity=0.0)


def test_floor_cheap_budget_all_four_speak_exactly_once():
    # (a) 4 pays, engagements tous sous le seuil, budget Cheap (=1) -> les 4 parlent
    # exactement une fois.
    world = _world()
    event = _muted_event()
    candidates = speaking_order(list(world.countries), event)
    director = TurnDirector(candidates, max_turns=1)
    order = _drain(director, event, world)
    assert set(order) == set(candidates)
    assert all(director.spoke_count[c] == 1 for c in candidates)


def test_floor_exceeds_a_budget_smaller_than_the_table():
    # (b) budget 2 avec 5 pays -> les 5 parlent (le plancher dépasse le budget).
    world = WorldState.from_countries(
        [
            _c("usa", "USA"),
            _c("iran", "Iran"),
            _c("france", "France"),
            _c("egypt", "Egypte"),
            _c("china", "Chine"),
        ]
    )
    event = _muted_event()
    candidates = speaking_order(list(world.countries), event)
    director = TurnDirector(candidates, max_turns=2)
    order = _drain(director, event, world)
    assert set(order) == set(candidates)
    assert director.turns_taken == len(order) == 5


def test_floor_does_not_change_repeats_under_a_full_budget():
    # (c) budget Full -> comportement au-delà du plancher inchangé (les plus engagés
    # re-parlent).
    world = _world()
    world.adjust_tension("usa", "iran", 0.9)
    event = _event(["usa", "iran"])
    candidates = speaking_order(list(world.countries), event)
    director = TurnDirector(candidates, max_turns=8)  # budget Full généreux
    order = _drain(director, event, world)
    assert set(order) == set(candidates)  # le plancher reste satisfait...
    assert any(order.count(cid) >= 2 for cid in set(order))  # ...et les plus engagés reparlent


def test_floor_ignores_countries_not_passed_as_candidates():
    # (d) un pays suspendu est déjà retiré des `agents` du round en amont : il n'est
    # jamais passé dans `candidates`, donc le plancher ne le concerne pas.
    world = _world()  # usa, iran, france, egypt existent dans le monde...
    event = _muted_event()
    candidates = ["usa", "iran"]  # ...mais france/egypt sont hors table (suspendus)
    director = TurnDirector(candidates, max_turns=1)
    order = _drain(director, event, world)
    assert set(order) == {"usa", "iran"}
    assert "france" not in director.spoke_count
    assert "egypt" not in director.spoke_count


def test_floor_speaks_in_descending_engagement_order():
    # (e) même sous le seuil, le plancher respecte l'ordre d'engagement décroissant :
    # ce n'est pas un round-robin déguisé.
    world = _world()
    event = _muted_event()
    candidates = speaking_order(list(world.countries), event)
    expected_scores = {cid: engagement_score(cid, event, world, [], {}) for cid in candidates}
    director = TurnDirector(candidates, max_turns=1)
    order = _drain(director, event, world)
    assert order == sorted(candidates, key=lambda c: expected_scores[c], reverse=True)
