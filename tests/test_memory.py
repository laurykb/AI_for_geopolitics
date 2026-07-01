"""Tests de la mémoire par pays (déterministe)."""

from core.country_state import CountryState, Economy, Military, Resources
from core.events import GeoEvent
from core.world_state import WorldState
from simulation.negotiation import NegotiationMessage, Verdict, update_memories


def _world():
    def c(cid):
        return CountryState(
            id=cid,
            name=cid.upper(),
            economy=Economy(gdp=1e12),
            military=Military(defense_budget=1e10),
            resources=Resources(),
        )

    return WorldState.from_countries([c("usa"), c("iran")])


def _event(rid=1, date="2025-07-01"):
    return GeoEvent(
        id=f"e{rid}", round_id=rid, event_type="x", title="Crise", date=date, actors=["usa"]
    )


def test_update_memories_appends_line_per_country():
    world = _world()
    messages = [NegotiationMessage(country="usa", text="Position ferme des USA.", pass_no=0)]
    verdict = Verdict(new_pacts=[["usa", "iran"]])
    update_memories(world, _event(), messages, verdict)

    assert "usa" in world.country_memory and "iran" in world.country_memory
    usa_mem = world.country_memory["usa"][-1]
    assert "Crise" in usa_mem
    assert "j'ai dit" in usa_mem
    assert "pacte avec iran" in usa_mem  # pacte reflété


def test_memory_is_capped():
    world = _world()
    for r in range(6):
        update_memories(world, _event(rid=r), [], Verdict())
    assert len(world.country_memory["usa"]) <= 4  # borné


def test_negotiation_prompt_includes_profile_perception_memory():
    from agents.prompts import build_negotiation_prompt
    from simulation.perception import perceive

    world = _world()
    world.country_memory["usa"] = ["R1 · Vieux sommet — j'ai dit : « ... »"]
    country = world.countries["usa"]
    event = _event()
    prompt = build_negotiation_prompt(country, event, world, "(début)", perceive(event, country))

    assert "Penchant" in prompt  # fiche/penchant dérivé
    assert "perception" in prompt.lower()  # fog of war
    assert "Vieux sommet" in prompt  # mémoire réinjectée
