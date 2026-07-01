"""Tests des messages de négociation et du garde-fou apply_verdict."""

from agents.llm_agent import LLMAgent
from core.country_state import CountryState, Economy, Military, Resources
from core.world_state import WorldState
from inference.mock_backend import MockBackend
from simulation.negotiation import (
    NegotiationMessage,
    Verdict,
    apply_verdict,
    format_transcript,
)


def _world() -> WorldState:
    def c(cid, name, **kw):
        return CountryState(
            id=cid,
            name=name,
            economy=Economy(gdp=1e12, growth=2.0),
            military=Military(defense_budget=1e10, projection=0.6),
            resources=Resources(),
            political_stability=0.5,
            technology_level=0.5,
            **kw,
        )

    return WorldState.from_countries([c("usa", "USA"), c("iran", "Iran")])


def test_format_transcript():
    msgs = [
        NegotiationMessage(country="usa", text="Position A", pass_no=0),
        NegotiationMessage(country="iran", text="Réponse B", pass_no=0),
    ]
    text = format_transcript(msgs)
    assert "usa: Position A" in text
    assert "iran: Réponse B" in text
    assert format_transcript([]) == "(début de la négociation)"


def test_stream_negotiation_message():
    agent = LLMAgent("usa", MockBackend("La France propose un accord maritime."))
    from core.events import GeoEvent

    event = GeoEvent(id="e", round_id=1, event_type="x", title="Crise", actors=["usa"])
    out = "".join(agent.stream_negotiation_message(event, _world(), []))
    assert out == "La France propose un accord maritime."
    assert agent.model_tag  # badge modèle non vide


def test_apply_verdict_clamps_and_applies():
    world = _world()
    g0 = world.countries["usa"].economy.growth
    s0 = world.countries["usa"].political_stability
    verdict = Verdict(
        attribute_deltas={"usa": {"croissance": 9.0, "stabilité": -0.9}},  # au-delà des plafonds
        tension_deltas=[{"a": "usa", "b": "iran", "delta": 0.3}],
        new_pacts=[["usa", "iran"]],
    )
    deltas = apply_verdict(world, verdict)

    # croissance clampée à +1.5, stabilité clampée à -0.15 (bornée [0,1])
    assert world.countries["usa"].economy.growth == g0 + 1.5
    assert abs(world.countries["usa"].political_stability - max(0.0, s0 - 0.15)) < 1e-9
    assert world.get_tension("usa", "iran") > 0.0
    assert world.share_alliance("usa", "iran")  # pacte ajouté
    labels = {d.label for d in deltas}
    assert {"croissance", "stabilité"} <= labels


def test_apply_verdict_ignores_unknown_ids_and_labels():
    world = _world()
    verdict = Verdict(
        attribute_deltas={"atlantis": {"croissance": 1.0}, "usa": {"bogus": 5.0}},
    )
    assert apply_verdict(world, verdict) == []  # rien d'applicable


def test_support_levels_bounded_and_reflects_tension():
    from core.events import GeoEvent
    from simulation.negotiation import support_levels

    world = _world()
    world.adjust_tension("usa", "iran", 0.8)
    event = GeoEvent(id="e", round_id=1, event_type="x", title="t", actors=["iran"])
    levels = support_levels(world, event)
    assert set(levels) == {"usa", "iran"}
    assert all(0.0 <= v <= 1.0 for v in levels.values())
    assert levels["usa"] < 1.0  # forte tension avec l'acteur -> soutien moindre
