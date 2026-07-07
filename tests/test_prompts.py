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


def test_negotiation_prompt_includes_mandate_and_urgency():
    from agents.prompts import build_negotiation_prompt
    from simulation.perception import perceive

    world, event = _world(), _event()
    perceived = perceive(event, world.countries["usa"])
    prompt = build_negotiation_prompt(world.countries["usa"], event, world, "(début)", perceived)
    assert "FEUILLE DE ROUTE" in prompt
    assert "Ligne rouge" in prompt
    assert "Urgence" in prompt


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


def test_negotiation_system_asks_for_private_reasoning_then_message():
    from agents.prompts import NEGOTIATION_SYSTEM

    # la super-intelligence pense en privé puis conclut par le marqueur MESSAGE:
    assert "MESSAGE:" in NEGOTIATION_SYSTEM
    lowered = NEGOTIATION_SYSTEM.lower()
    assert "réfléch" in lowered or "réflexion" in lowered or "pens" in lowered


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
