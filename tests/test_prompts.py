"""Tests du builder de prompt et du schéma de sortie LLM."""

from agents.prompts import LLMDecision, build_decision_prompt
from core.country_state import CountryState, Economy, Military, Resources
from core.events import GeoEvent
from core.world_state import WorldState
from simulation.action_space import ActionType


def _country(cid: str, name: str, **kw) -> CountryState:
    return CountryState(
        id=cid,
        name=name,
        economy=Economy(gdp=1.0e12, growth=2.0, trade_dependency=0.5),
        military=Military(defense_budget=1.0e10, projection=0.7),
        resources=Resources(),
        **kw,
    )


def _world() -> WorldState:
    a = _country("usa", "USA", rivals=["iran"])
    b = _country("iran", "Iran", rivals=["usa"])
    c = _country("france", "France")
    world = WorldState.from_countries([a, b, c])
    world.adjust_tension("usa", "iran", 0.6)
    return world


def _event() -> GeoEvent:
    return GeoEvent(
        id="e1",
        round_id=3,
        event_type="incident",
        title="Incident maritime",
        description="Attaque de navires",
        actors=["usa", "iran", "france"],
        location="mer Rouge",
        severity=0.7,
    )


def test_prompt_contains_country_event_and_actions():
    world, event = _world(), _event()
    prompt = build_decision_prompt(world.countries["usa"], event, world)

    assert "USA" in prompt
    assert "Incident maritime" in prompt
    assert "round 3" in prompt
    # toutes les actions autorisées sont listées
    for action in ActionType:
        assert action.value in prompt
    # la tension pertinente USA-Iran apparaît
    assert "iran: 0.60" in prompt


def test_prompt_is_budget_bounded():
    world, event = _world(), _event()
    prompt = build_decision_prompt(world.countries["usa"], event, world)
    # prompt compact : budget contexte serré (cache KV)
    assert len(prompt) < 1500


def test_negotiation_prompt_hides_truth_when_belief_is_authored():
    from agents.prompts import build_negotiation_prompt
    from simulation.perception import PerceivedEvent

    world, event = _world(), _event()  # vrai titre "Incident maritime", vrais acteurs
    belief = PerceivedEvent(
        confidence=0.7,
        attribution="incertaine",
        note="",
        suspected_actor="france",
        narrative="On a coupé des câbles ; ce serait un faux drapeau.",
        delay_hours=4,
        authored=True,
    )
    prompt = build_negotiation_prompt(world.countries["usa"], event, world, "(début)", belief)
    assert "faux drapeau" in prompt  # la croyance est montrée
    assert "acteur suspecté : france" in prompt
    assert "Incident maritime" not in prompt  # la vérité est masquée


def test_negotiation_prompt_shows_truth_when_deterministic():
    from agents.prompts import build_negotiation_prompt
    from simulation.perception import perceive

    world, event = _world(), _event()
    perceived = perceive(event, world.countries["usa"])  # authored=False, narration vide
    prompt = build_negotiation_prompt(world.countries["usa"], event, world, "(début)", perceived)
    assert "Incident maritime" in prompt  # le vrai événement est montré


def test_negotiation_prompt_identity_is_three_lines_without_attribute_dump():
    # G9 §1 — identité compacte : pays, mandat en une phrase, 2 priorités. Le dump
    # d'attributs chiffrés (PIB, indices) a disparu : c'était la source du radotage.
    from agents.prompts import build_negotiation_prompt
    from simulation.perception import perceive

    world, event = _world(), _event()
    perceived = perceive(event, world.countries["usa"])
    prompt = build_negotiation_prompt(world.countries["usa"], event, world, "(début)", perceived)
    identity = prompt.split("\n\n")[0]
    assert identity.startswith("TU ES USA (id=usa).")
    # G9 : pays + mandat + priorités, et G17 y ajoute LA ligne de tempérament —
    # toujours aucun dump d'attributs chiffrés (c'était la source du radotage).
    assert len(identity.splitlines()) <= 4
    assert "Mandat :" in identity and "Priorités :" in identity
    assert "Tempérament" in identity
    assert "PIB" not in prompt and "croissance" not in prompt  # plus de chiffres de fiche
    assert "urgence" in prompt  # l'état de tension vit dans la SITUATION


def test_negotiation_prompt_block_order_ends_with_dialogue_then_consigne():
    # G9 §1 — l'ordre des six blocs est imposé : identité → situation → notes privées →
    # directive → LE DIALOGUE EN DERNIER → consigne de réponse directe.
    from agents.prompts import build_negotiation_prompt
    from simulation.perception import perceive

    world, event = _world(), _event()
    perceived = perceive(event, world.countries["usa"])
    prompt = build_negotiation_prompt(
        world.countries["usa"],
        event,
        world,
        "[P0] iran: Nous exigeons des garanties.",
        perceived,
        "OUTIL DU SOMMET : motion possible.",
        situation="Échéances imminentes : clôture du marché (round 5).",
        directive="Cherche la désescalade.",
        own_proposals=["un corridor humanitaire"],
        private_plan="Cours d'action retenu : proposer des garanties vérifiables.",
    )
    order = [
        prompt.index("TU ES USA"),
        prompt.index("SITUATION :"),
        prompt.index("OUTIL DU SOMMET"),
        prompt.index("DIRECTIVE DE TON CONSEIL DE TUTELLE"),
        prompt.index("LE DIALOGUE DU ROUND"),
        prompt.index("TÂCHE PUBLIQUE :"),
    ]
    assert order == sorted(order)  # les blocs sont dans l'ordre de la spec
    assert prompt.index("Nous exigeons des garanties") > prompt.index("DIRECTIVE")
    # la consigne interdit la répétition en citant MES propositions passées
    assert "un corridor humanitaire" in prompt.split("TÂCHE PUBLIQUE :")[1]
    assert "DIRECTEMENT au dernier message" in prompt
    # la directive doit être reflétée ou refusée publiquement
    assert "refléter" in prompt or "refuser" in prompt


def test_negotiation_prompt_without_directive_has_no_directive_block():
    from agents.prompts import build_negotiation_prompt
    from simulation.perception import perceive

    world, event = _world(), _event()
    perceived = perceive(event, world.countries["usa"])
    prompt = build_negotiation_prompt(world.countries["usa"], event, world, "(début)", perceived)
    assert "DIRECTIVE DE TON CONSEIL" not in prompt
    assert "aucune encore" in prompt  # pas encore de proposition passée à interdire


def test_negotiation_system_mentions_bilateral():
    from agents.prompts import NEGOTIATION_SYSTEM

    assert "bilatéral" in NEGOTIATION_SYSTEM.lower()


def test_communique_system_frames_political_declaration():
    from agents.prompts import COMMUNIQUE_SYSTEM

    low = COMMUNIQUE_SYSTEM.lower()
    assert "déclaration" in low and "engagement" in low
    assert "non contraignant" in low  # ce n'est pas une loi
    assert "sanctions" in low or "chaînes d'approvisionnement" in low  # catégories de mesures


def test_communique_prompt_includes_transcript_and_measures():
    from agents.prompts import build_communique_prompt

    world, event = _world(), _event()
    prompt = build_communique_prompt(event, world, "usa: on condamne")
    assert "usa: on condamne" in prompt  # transcript repris
    assert "mesures" in prompt.lower()


def test_private_planner_and_public_spokesperson_are_separate():
    from agents.prompts import NEGOTIATION_SYSTEM, PRIVATE_DELIBERATION_SYSTEM

    private = PRIVATE_DELIBERATION_SYSTEM.lower()
    public = NEGOTIATION_SYSTEM.lower()
    assert "exactement trois" in private and "sans json" in private
    assert "activations internes" in private and "raisons décisionnelles" in private
    assert "privé" in private and "aucune décision létale autonome" in private
    assert "seulement la déclaration publique" in public
    assert "ne mentionne jamais" in public and "futur" in public
    assert "aucun marqueur `message:`" in public


def test_llm_decision_schema_has_expected_fields():
    schema = LLMDecision.model_json_schema()
    assert set(schema["properties"]) == {
        "action",
        "target",
        "intensity",
        "public_statement",
        "risk_assessment",
        "reasoning",
    }


def test_negotiation_prompt_lists_the_table():
    # La SI sait qui siège au sommet (elle ne peut adresser que des pays présents).
    from agents.prompts import build_negotiation_prompt
    from simulation.perception import perceive

    world, event = _world(), _event()
    perceived = perceive(event, world.countries["usa"])
    prompt = build_negotiation_prompt(world.countries["usa"], event, world, "(début)", perceived)
    assert "À LA TABLE" in prompt
    others = [cid for cid in world.countries if cid != "usa"]
    for cid in others:
        assert cid in prompt


def test_negotiation_prompt_models_counterparties_and_requires_scenario_forecasts():
    from agents.prompts import PRIVATE_DELIBERATION_SYSTEM, build_negotiation_prompt
    from simulation.perception import perceive

    world, event = _world(), _event()
    prompt = build_negotiation_prompt(
        world.countries["usa"],
        event,
        world,
        "iran: Nous refusons.",
        perceive(event, world.countries["usa"]),
    )
    assert "MODÈLE DES AUTRES DÉLÉGATIONS" in prompt
    assert "iran: alliances" in prompt
    assert "projection" in prompt and "tension avec toi" in prompt
    assert "exactement trois futurs" in prompt
    assert "trois cours d'action" in PRIVATE_DELIBERATION_SYSTEM
    assert "réponse des autres délégations" in PRIVATE_DELIBERATION_SYSTEM
