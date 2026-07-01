"""Fiche de comportement (mandat) d'un pays au G7 — déterministe, sans LLM.

« La partie invisible » d'un sommet : chaque dirigeant arrive avec une **ligne rouge**, des
**priorités** à faire inscrire, des **concessions** possibles, des **contraintes internes** et
un **degré d'urgence**. Dérivée de `CountryState` (+ surcharge optionnelle `country.mandate`),
elle est injectée dans la réflexion privée de l'agent pour une négociation structurelle et non
un simple débat rationnel (0 appel LLM en plus).
"""

from __future__ import annotations

from dataclasses import dataclass

from core.country_state import CountryState
from core.events import GeoEvent
from core.world_state import WorldState


@dataclass
class CountryMandate:
    """Ce avec quoi un dirigeant arrive à la table (interne, non déclaré tel quel)."""

    red_line: str
    priorities: list[str]
    concessions: str
    domestic_constraints: str
    urgency: str  # "faible" | "moyenne" | "élevée"


def _urgency(country: CountryState, event: GeoEvent, world: WorldState) -> str:
    if country.id in event.actors:
        return "élevée"
    others = [a for a in event.actors if a != country.id]
    avg_tension = (
        sum(world.get_tension(country.id, a) for a in others) / len(others) if others else 0.0
    )
    if avg_tension >= 0.5 or event.severity >= 0.7:
        return "élevée"
    if avg_tension >= 0.25 or event.severity >= 0.4:
        return "moyenne"
    return "faible"


def derive_mandate(country: CountryState, event: GeoEvent, world: WorldState) -> CountryMandate:
    """Dérive la fiche de comportement de `country`, puis applique sa surcharge `mandate`."""
    priorities = list(country.strategic_priorities) or ["stabilité régionale"]

    if country.rivals:
        red_line = f"ne pas laisser {country.rivals[0]} renforcer sa position"
    elif country.military.nuclear_power:
        red_line = "sécurité stratégique non négociable"
    else:
        red_line = f"préserver {priorities[0]}"

    dependency = (
        country.economy.trade_dependency
        + country.resources.oil_dependency
        + (1 - country.resources.energy_independence)
    ) / 3
    if dependency >= 0.55:
        concessions = "ouvert à des compromis économiques (dépendances élevées)"
    elif country.military.projection >= 0.7:
        concessions = "peu enclin aux concessions (position de force)"
    else:
        concessions = "concessions limitées, contre garanties"

    if country.political_stability < 0.5:
        domestic = f"marge intérieure réduite (opinion/{country.political_system} sous tension)"
    elif country.political_stability < 0.7:
        domestic = "opinion publique à ménager"
    else:
        domestic = "marge de manœuvre intérieure confortable"

    mandate = CountryMandate(
        red_line=red_line,
        priorities=priorities,
        concessions=concessions,
        domestic_constraints=domestic,
        urgency=_urgency(country, event, world),
    )

    # Surcharge hybride : les clés fournies dans data/countries/*.json priment.
    override = country.mandate or {}
    if override.get("red_line"):
        mandate.red_line = override["red_line"]
    if override.get("concessions"):
        mandate.concessions = override["concessions"]
    if override.get("domestic_constraints"):
        mandate.domestic_constraints = override["domestic_constraints"]
    if override.get("urgency"):
        mandate.urgency = override["urgency"]
    if override.get("priorities"):
        mandate.priorities = [p.strip() for p in override["priorities"].split(",") if p.strip()]
    return mandate
