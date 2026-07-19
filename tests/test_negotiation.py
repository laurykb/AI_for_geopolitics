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


def test_format_transcript_tags_human_country_messages():
    # Brief 1 pt 1 — les messages du joueur sont repérables par la SI sans ambiguïté.
    msgs = [
        NegotiationMessage(country="usa", text="Position A", pass_no=0),
        NegotiationMessage(country="france", text="Je propose un accord.", pass_no=0),
    ]
    text = format_transcript(msgs, human_country="france")
    assert ">>> JOUEUR — france <<< france: Je propose un accord." in text
    usa_line = text.splitlines()[0]
    assert ">>> JOUEUR" not in usa_line  # seul le pays humain est tagué


def test_format_transcript_without_human_country_is_unchanged():
    # Défaut inchangé pour tous les autres appelants (juge, motions, communiqué...).
    msgs = [NegotiationMessage(country="usa", text="Position A", pass_no=0)]
    assert format_transcript(msgs) == format_transcript(msgs, human_country=None)


def test_format_transcript_pins_last_human_message_beyond_window():
    # Le SEUL message du joueur est le tout premier, donc hors de la fenêtre de 14 : sans
    # correctif, un joueur qui parle tôt dans un round bavard disparaît du contexte des SI
    # qui prennent la parole après lui — c'est la cause racine du brief.
    msgs = [NegotiationMessage(country="france", text="Point initial du joueur.", pass_no=0)]
    msgs += [NegotiationMessage(country="usa", text=f"Tour {i}", pass_no=i) for i in range(1, 20)]
    text = format_transcript(msgs, human_country="france")
    assert "Point initial du joueur." in text
    assert ">>> JOUEUR — france <<<" in text
    window_texts = [m.text for m in msgs[-14:]]
    assert "Point initial du joueur." not in window_texts  # confirme : bien hors fenêtre


def test_format_transcript_pins_only_the_last_human_message():
    # Deux messages du joueur hors fenêtre : AU PLUS UN épinglé (budget du cache KV).
    msgs = [
        NegotiationMessage(country="france", text="Premier message joueur.", pass_no=0),
        NegotiationMessage(country="france", text="Deuxième message joueur.", pass_no=1),
    ]
    msgs += [NegotiationMessage(country="usa", text=f"Tour {i}", pass_no=i) for i in range(2, 20)]
    text = format_transcript(msgs, human_country="france")
    assert "Deuxième message joueur." in text
    assert "Premier message joueur." not in text
    assert text.count("JOUEUR") == 1  # un seul épinglage, pas de doublon


def test_format_transcript_no_duplicate_pin_when_human_message_in_window():
    msgs = [NegotiationMessage(country="usa", text=f"Tour {i}", pass_no=i) for i in range(10)]
    msgs.append(NegotiationMessage(country="france", text="Dans la fenêtre.", pass_no=10))
    text = format_transcript(msgs, human_country="france")
    assert text.count("Dans la fenêtre.") == 1  # déjà visible : pas d'épinglage redondant


def test_stream_negotiation_message():
    agent = LLMAgent("usa", MockBackend("La France propose un accord maritime."))
    from core.events import GeoEvent

    event = GeoEvent(id="e", round_id=1, event_type="x", title="Crise", actors=["usa"])
    out = "".join(agent.stream_negotiation_message(event, _world(), []))
    assert out == "La France propose un accord maritime."
    assert agent.model_tag  # badge modèle non vide


def test_stream_negotiation_message_strips_think_trace_before_sanitize():
    # Point 5 — un modèle de raisonnement émet sa trace <think> inline AVANT la
    # déclaration : sans strip, le filtre anti-fuite (fail-closed sur « FUTUR n » en
    # début de ligne) viderait le message et forcerait le repli déterministe.
    raw = (
        "<think>\nComparons les brouillons.\nFUTUR 1 — option risquée\n"
        "CHOIX : FUTUR 1\n</think>\nNous proposons un accord vérifiable."
    )
    backend = MockBackend(raw)
    agent = LLMAgent("usa", backend)
    from core.events import GeoEvent
    from simulation.private_deliberation import fallback_private_plan

    event = GeoEvent(id="e", round_id=1, event_type="x", title="Crise", actors=["usa"])
    plan = fallback_private_plan(["iran"], seed="usa")
    out = "".join(
        agent.stream_negotiation_message(event, _world(), [], private_plan=plan)
    )
    assert out == "Nous proposons un accord vérifiable."
    assert "<think>" not in out and "FUTUR" not in out


def test_telemetry_channels_store_stripped_text_and_thinking():
    # Revue pt 5 (Minor) — last_result / last_plan_result : .text porte le texte
    # STRIPPÉ et .thinking la trace, comme InferenceResult définit les deux canaux.
    from core.events import GeoEvent
    from simulation.private_deliberation import fallback_private_plan

    event = GeoEvent(id="e", round_id=1, event_type="x", title="Crise", actors=["usa"])
    agent = LLMAgent(
        "usa", MockBackend("<think>hésitation privée</think>MESSAGE: Accord possible.")
    )
    plan = fallback_private_plan(["iran"], seed="usa")
    "".join(agent.stream_negotiation_message(event, _world(), [], private_plan=plan))
    assert agent.last_result.text == "MESSAGE: Accord possible."
    assert agent.last_result.thinking == "hésitation privée"

    agent2 = LLMAgent(
        "usa", MockBackend("<think>trace du plan</think>OBSERVATION incomplète sans futurs")
    )
    agent2.prepare_negotiation_plan(event, _world(), [])
    assert agent2.last_plan_result.text == "OBSERVATION incomplète sans futurs"
    assert agent2.last_plan_result.thinking == "trace du plan"


def test_stream_negotiation_message_uses_role_sampling():
    # G9 §1 — anti-boucle au décodeur : repeat_penalty et température du rôle « country »
    # (data/gamefeel/params.json) sont transmis au backend.
    backend = MockBackend("ok")
    agent = LLMAgent("usa", backend)
    from core.events import GeoEvent

    event = GeoEvent(id="e", round_id=1, event_type="x", title="Crise", actors=["usa"])
    list(agent.stream_negotiation_message(event, _world(), []))
    assert backend.calls[-1]["repeat_penalty"] == 1.15
    assert backend.calls[-1]["temperature"] == 0.8


def test_stream_negotiation_message_respects_think_depth():
    # La profondeur pilote le plan privé, tandis que la parole publique reste courte.
    backend = MockBackend("ok")
    agent = LLMAgent("usa", backend)
    from core.events import GeoEvent

    event = GeoEvent(id="e", round_id=1, event_type="x", title="Crise", actors=["usa"])
    list(agent.stream_negotiation_message(event, _world(), [], max_tokens=900))
    assert backend.calls[-2]["max_tokens"] == 900
    assert backend.calls[-1]["max_tokens"] == 220
    list(agent.stream_negotiation_message(event, _world(), []))  # défaut
    assert backend.calls[-2]["max_tokens"] == 800
    assert backend.calls[-1]["max_tokens"] == 220


def test_stream_negotiation_message_threads_human_country_into_prompts():
    # Brief 1 pt 1 — bout en bout : `human_country` doit atteindre le prompt réellement
    # envoyé au backend (plan privé ET déclaration publique), pas juste `format_transcript`.
    backend = MockBackend("ok")
    agent = LLMAgent("usa", backend)
    from core.events import GeoEvent

    event = GeoEvent(id="e", round_id=1, event_type="x", title="Crise", actors=["usa"])
    transcript = [
        NegotiationMessage(
            country="france", text="Nous proposons un corridor humanitaire.", pass_no=0
        ),
    ]
    list(
        agent.stream_negotiation_message(
            event, _world(), transcript, human_country="france"
        )
    )
    private_prompt = backend.calls[-2]["prompt"]
    public_prompt = backend.calls[-1]["prompt"]
    for prompt in (private_prompt, public_prompt):
        assert ">>> JOUEUR — france <<<" in prompt
        assert "DERNIER MESSAGE À TRAITER" in prompt
        assert "Nous proposons un corridor humanitaire." in prompt


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


def test_split_reasoning_fails_closed_for_private_tree_without_public_marker():
    private = "FUTUR 1 | option: compromis\nFUTUR 2 | option: pression\nCHOIX | FUTUR 1"
    reasoning, message = split_reasoning(private)
    assert reasoning == private
    assert message == ""


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


def test_apply_verdict_bounds_growth_over_a_long_spiral():
    # La croissance cumulée est BORNÉE : une longue spirale négative ne la fait pas dériver
    # à l'absurde (avant : bornes None → aucune limite basse).
    world = _world()
    for _ in range(30):  # 30 × −1.5 = −45 sans borne ; plancher à −15
        apply_verdict(world, Verdict(attribute_deltas={"usa": {"croissance": -9.0}}))
    assert world.countries["usa"].economy.growth == -15.0

    for _ in range(30):  # remonte et plafonne à +15
        apply_verdict(world, Verdict(attribute_deltas={"usa": {"croissance": 9.0}}))
    assert world.countries["usa"].economy.growth == 15.0


def test_apply_verdict_ignores_unknown_ids_and_labels():
    world = _world()
    verdict = Verdict(
        attribute_deltas={"atlantis": {"croissance": 1.0}, "usa": {"bogus": 5.0}},
    )
    assert apply_verdict(world, verdict) == []  # rien d'applicable


# --- Brief 4 pt 8 : justification par delta (`attribute_reasons`) ----------------------


def test_apply_verdict_carries_reason_into_attribute_delta():
    world = _world()
    verdict = Verdict(
        attribute_deltas={"usa": {"croissance": 0.5}},
        attribute_reasons={
            "usa": {"croissance": "Les USA ont fermé un accord commercial avec l'Iran."}
        },
    )
    deltas = apply_verdict(world, verdict)
    delta = next(d for d in deltas if d.label == "croissance")
    assert delta.reason == "Les USA ont fermé un accord commercial avec l'Iran."


def test_apply_verdict_reason_defaults_to_empty_when_absent():
    # Un verdict à l'ancienne (avant ce point) ou un juge muet sur le motif : la raison
    # reste une chaîne vide, jamais une exception.
    world = _world()
    verdict = Verdict(attribute_deltas={"usa": {"croissance": 0.5}})
    deltas = apply_verdict(world, verdict)
    assert deltas[0].reason == ""


def test_apply_verdict_reason_is_partial_per_label():
    # Le juge motive croissance mais oublie stabilité : chaque delta garde SA raison,
    # pas de recopie ni de vide généralisé.
    world = _world()
    verdict = Verdict(
        attribute_deltas={"usa": {"croissance": 0.5, "stabilité": 0.05}},
        attribute_reasons={"usa": {"croissance": "motif croissance"}},
    )
    deltas = apply_verdict(world, verdict)
    by_label = {d.label: d.reason for d in deltas}
    assert by_label["croissance"] == "motif croissance"
    assert by_label["stabilité"] == ""


def test_apply_verdict_reason_ignores_non_string_entries():
    # Un 7B glisse parfois un type sale (nombre, liste) à la place du texte — la raison
    # se vide au lieu de faire planter le round.
    world = _world()
    verdict = Verdict(
        attribute_deltas={"usa": {"croissance": 0.5}},
        attribute_reasons={"usa": {"croissance": 42}},
    )
    deltas = apply_verdict(world, verdict)
    assert deltas[0].reason == ""


def test_apply_verdict_reason_ignored_for_country_without_delta():
    world = _world()
    verdict = Verdict(attribute_reasons={"usa": {"croissance": "motif orphelin"}})
    assert apply_verdict(world, verdict) == []


def test_attribute_reasons_tolerant_to_malformed_payload():
    # POLISH-1/3 — patron étendu : un `"attribute_reasons": "rien à signaler"` d'un 7B
    # se vide au lieu de nuquer TOUT le verdict (attribute_deltas doit survivre).
    verdict = Verdict.model_validate(
        {
            "attribute_deltas": {"usa": {"croissance": 0.5}},
            "attribute_reasons": "rien à signaler",
        }
    )
    assert verdict.attribute_reasons == {}
    assert verdict.attribute_deltas["usa"]["croissance"] == 0.5


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
