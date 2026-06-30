"""Construction des prompts et schéma de sortie des pays-agents LLM (Phase 1).

Budget contexte serré (le cache KV est le goulot VRAM) : prompt compact, seules
les tensions pertinentes, sortie JSON courte et cadrée par un schéma.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from core.country_state import CountryState
from core.events import GeoEvent
from core.world_state import WorldState
from simulation.action_space import ActionType

# Nombre maximum de tensions listées dans le prompt (top-k, budget contexte).
_TOP_K_TENSIONS = 5

SYSTEM_PROMPT = (
    "Tu es le système d'aide à la décision stratégique d'un État dans une simulation "
    "géopolitique. Tu raisonnes selon les intérêts nationaux, les alliances et les "
    "rivalités du pays. Tu es un outil d'analyse de signaux de risque, PAS un oracle : "
    "tu ne prédis pas la guerre et tu n'engages jamais de décision létale autonome. "
    "Réponds UNIQUEMENT par un objet JSON conforme au schéma demandé, sans aucun texte "
    "autour, sans Markdown."
)


class LLMDecision(BaseModel):
    """Sous-ensemble de la décision produit par le LLM.

    `country` et `round_id` ne sont volontairement pas demandés au modèle : ils sont
    injectés par l'agent (identité non falsifiable, sortie plus courte).
    """

    action: ActionType
    target: str | None = Field(None, description="id du pays ciblé, ou null")
    intensity: float = Field(0.5, ge=0.0, le=1.0)
    public_statement: str = Field("", description="déclaration publique, 1 phrase")
    risk_assessment: float = Field(0.5, ge=0.0, le=1.0)
    reasoning: str = Field("", description="justification brève")


def _format_economy(country: CountryState) -> str:
    eco = country.economy
    return (
        f"PIB~{eco.gdp:.2e} USD, croissance {eco.growth:.1f}%, "
        f"dépendance commerciale {eco.trade_dependency:.2f}"
    )


def _format_military(country: CountryState) -> str:
    mil = country.military
    nuke = "oui" if mil.nuclear_power else "non"
    return f"projection {mil.projection:.2f}, nucléaire {nuke}"


def _relevant_tensions(country_id: str, event: GeoEvent, world: WorldState) -> list[str]:
    """Tensions du pays vs les acteurs de l'événement (les plus fortes d'abord)."""
    others = [a for a in event.actors if a != country_id]
    pairs = [(a, world.get_tension(country_id, a)) for a in others]
    pairs.sort(key=lambda p: p[1], reverse=True)
    return [f"{a}: {t:.2f}" for a, t in pairs[:_TOP_K_TENSIONS]]


def build_decision_prompt(country: CountryState, event: GeoEvent, world: WorldState) -> str:
    """Construit un prompt compact pour la décision d'un pays face à un événement."""
    actions = ", ".join(a.value for a in ActionType)
    tensions = _relevant_tensions(country.id, event, world)
    tensions_str = "; ".join(tensions) if tensions else "aucune notable"
    involved = "oui" if country.id in event.actors else "non"
    candidates = ", ".join(cid for cid in sorted(world.countries) if cid != country.id)

    return (
        f"PAYS : {country.name} (id={country.id}, régime={country.political_system})\n"
        f"- Priorités : {', '.join(country.strategic_priorities) or 'n/a'}\n"
        f"- Alliances : {', '.join(country.alliances) or 'aucune'}\n"
        f"- Rivaux : {', '.join(country.rivals) or 'aucun'}\n"
        f"- Économie : {_format_economy(country)}\n"
        f"- Militaire : {_format_military(country)}\n\n"
        f"ÉVÉNEMENT (round {event.round_id}) : {event.title}\n"
        f"- {event.description}\n"
        f"- Lieu : {event.location or 'n/a'} | Acteurs : {', '.join(event.actors) or 'n/a'}\n"
        f"- Sévérité : {event.severity:.2f} | Pays impliqué : {involved}\n"
        f"- Tensions (toi vs acteurs) : {tensions_str}\n\n"
        f"ACTIONS AUTORISÉES : {actions}\n"
        f"Choisis UNE action servant tes intérêts. `target` est un id parmi [{candidates}] "
        f"ou null. Si tu choisis form_coalition ou support, `target` DOIT être l'id du pays "
        f"allié visé. `intensity` et `risk_assessment` sont des décimaux entre 0.0 et 1.0. "
        f"Réponds en JSON : {{action, target, intensity, "
        f"public_statement, risk_assessment, reasoning}}."
    )
