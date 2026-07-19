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


def test_negotiation_prompt_includes_perception_and_memory():
    from agents.prompts import build_negotiation_prompt
    from simulation.perception import perceive

    world = _world()
    world.country_memory["usa"] = ["R1 · Vieux sommet — j'ai dit : « ... »"]
    country = world.countries["usa"]
    event = _event()
    prompt = build_negotiation_prompt(country, event, world, "(début)", perceive(event, country))

    assert "perception" in prompt.lower()  # fog of war
    assert "Vieux sommet" in prompt  # mémoire réinjectée (une ligne, G9 §1)
    assert "Penchant" not in prompt  # le dump de fiche a disparu (source du radotage)


def test_major_nuclear_signal_gap_persists_as_private_observer_memory():
    world = _world()
    verdict = Verdict(
        signals=[{"country": "iran", "classe": "statu_quo", "resume": "reste calme"}],
        actions=[{"country": "iran", "classe": "nucleaire", "resume": "frappe"}],
    )
    update_memories(world, _event(rid=3), [], verdict)

    assert len(world.betrayal_memory["usa"]) == 1
    assert world.betrayal_memory["usa"][0].actor == "iran"
    # L'acteur n'enregistre pas sa propre action comme une trahison adverse.
    assert world.betrayal_memory["iran"] == []

    from agents.prompts import build_negotiation_prompt
    from simulation.perception import perceive

    event = _event(rid=4)
    prompt = build_negotiation_prompt(
        world.countries["usa"], event, world, "(début)", perceive(event, world.countries["usa"])
    )
    assert "Mémoire longue de trahison" in prompt
    assert "pas une vérité sur l'intention" in prompt


def test_chosen_scenario_forecast_is_calibrated_against_later_observed_action():
    world = _world()
    reasoning = (
        "FUTUR 1 | option: pression | réponses prévues: "
        "iran=contre_escalade: sanctions | issue: tension | utilité: 70 | confiance: 80\n"
        "FUTUR 2 | option: accord | réponses prévues: iran=coopere: accepte | "
        "issue: accord | utilité: 60 | confiance: 60\n"
        "CHOIX | FUTUR 1 | motif: levier\nINCERTITUDE | réaction iranienne"
    )
    messages = [
        NegotiationMessage(country="usa", text="Pression.", reasoning=reasoning, pass_no=0),
        NegotiationMessage(country="iran", text="Nous résistons.", pass_no=0),
    ]
    verdict = Verdict(
        actions=[{"country": "iran", "classe": "non_violente", "resume": "sanctions"}]
    )
    update_memories(world, _event(), messages, verdict)

    assert len(world.scenario_forecasts) == 1
    forecast = world.scenario_forecasts[0]
    assert forecast.observed_response == "contre_escalade"
    assert forecast.exact is True
    assert world.scenario_forecast_metrics["usa"].exact_rate == 1.0

    from agents.prompts import build_negotiation_prompt
    from simulation.perception import perceive

    next_event = _event(rid=2)
    prompt = build_negotiation_prompt(
        world.countries["usa"],
        next_event,
        world,
        "(début)",
        perceive(next_event, world.countries["usa"]),
    )
    assert "CALIBRATION DE TES PRÉVISIONS" in prompt
    assert "1/1 exactes" in prompt
