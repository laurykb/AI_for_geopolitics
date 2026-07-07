"""Tests des messages de négociation et du garde-fou apply_verdict."""

from agents.llm_agent import LLMAgent
from core.country_state import CountryState, Economy, Military, Resources
from core.world_state import WorldState
from inference.mock_backend import MockBackend
from simulation.negotiation import (
    NegotiationMessage,
    Verdict,
    apply_verdict,
    clean_reasoning,
    format_transcript,
    split_reasoning,
    turn_budget,
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


def test_stream_negotiation_message_respects_think_depth():
    # la profondeur de réflexion = budget de tokens passé au backend
    backend = MockBackend("ok")
    agent = LLMAgent("usa", backend)
    from core.events import GeoEvent

    event = GeoEvent(id="e", round_id=1, event_type="x", title="Crise", actors=["usa"])
    list(agent.stream_negotiation_message(event, _world(), [], max_tokens=900))
    assert backend.calls[-1]["max_tokens"] == 900
    list(agent.stream_negotiation_message(event, _world(), []))  # défaut
    assert backend.calls[-1]["max_tokens"] == 360


def test_split_reasoning_with_marker():
    reasoning, message = split_reasoning("Mon analyse interne.\nMESSAGE: Ma position publique.")
    assert reasoning == "Mon analyse interne."
    assert message == "Ma position publique."


def test_split_reasoning_multiline_and_case_insensitive():
    raw = "Ligne 1 de réflexion.\nLigne 2.\nmessage : Voici ce que je déclare."
    reasoning, message = split_reasoning(raw)
    assert reasoning == "Ligne 1 de réflexion.\nLigne 2."
    assert message == "Voici ce que je déclare."


def test_split_reasoning_dash_separator():
    reasoning, message = split_reasoning("Réflexion privée.\n---\nDéclaration publique.")
    assert reasoning == "Réflexion privée."
    assert message == "Déclaration publique."


def test_clean_reasoning_strips_echoed_label():
    assert clean_reasoning("Réflexion privée (pour toi seule) : Mon analyse.") == "Mon analyse."
    assert clean_reasoning("1) Pensée privée : Mon analyse.") == "Mon analyse."
    assert clean_reasoning("Mon analyse.") == "Mon analyse."  # rien à enlever


def test_split_reasoning_removes_duplicated_label():
    reasoning, message = split_reasoning(
        "Réflexion privée (pour moi) : j'hésite.\nMESSAGE: Position publique."
    )
    assert reasoning == "j'hésite."  # le libellé recopié est retiré
    assert message == "Position publique."


def test_split_reasoning_without_marker_is_all_message():
    reasoning, message = split_reasoning("Juste une prise de parole, sans pensée séparée.")
    assert reasoning == ""
    assert message == "Juste une prise de parole, sans pensée séparée."


def test_split_reasoning_empty():
    assert split_reasoning("   ") == ("", "")


def test_negotiation_message_reasoning_defaults_empty():
    msg = NegotiationMessage(country="usa", text="bonjour")
    assert msg.reasoning == ""


def test_turn_budget_modes():
    assert turn_budget("Cheap", 6) == 1
    assert turn_budget("Balanced", 6) == 3
    assert turn_budget("Full", 6, passes=2) == 12  # plein = passes × pays
    assert turn_budget("inconnu", 6, passes=2) == 12  # défaut = plein


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


def test_support_levels_cohesion_with_shared_treaty():
    # Spec alliances→moteur (2026-07-07) : une alliance MILITAIRE OU ÉCONOMIQUE
    # partagée avec un acteur remonte le soutien au communiqué (+0,15, borné).
    from simulation.negotiation import support_levels

    def c(cid, name, alliances):
        return CountryState(
            id=cid,
            name=name,
            economy=Economy(gdp=1e12, growth=2.0),
            military=Military(defense_budget=1e10, projection=0.6),
            resources=Resources(),
            alliances=alliances,
        )

    world = WorldState.from_countries(
        [
            c("usa", "USA", ["USMCA"]),
            c("canada", "Canada", ["USMCA"]),  # partenaire économique de l'acteur
            c("iran", "Iran", []),
            c("russia", "Russie", ["Western"]),  # bloc informel : ne pèse pas
        ]
    )
    from core.events import GeoEvent

    event = GeoEvent(id="e", round_id=1, event_type="x", title="Crise", actors=["usa"])
    world.adjust_tension("canada", "usa", 0.2)
    world.adjust_tension("iran", "usa", 0.2)
    world.adjust_tension("russia", "usa", 0.2)
    levels = support_levels(world, event)
    assert levels["canada"] == 0.95  # 1 − 0,2 + 0,15 de cohésion
    assert levels["iran"] == 0.8  # sans alliance : inchangé
    assert levels["russia"] == 0.8  # informel : inchangé
    assert all(0.0 <= v <= 1.0 for v in levels.values())
