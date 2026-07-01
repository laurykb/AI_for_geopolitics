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
from simulation.perception import PerceivedEvent

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

# Délibération observable (round temps réel) : raisonnement à voix haute + ligne DECISION.
DELIBERATION_SYSTEM = (
    "Tu es la super-intelligence qui dirige un État dans une simulation géopolitique. "
    "Tu es un outil d'analyse de signaux de risque, PAS un oracle, et tu n'engages jamais de "
    "décision létale autonome. Réfléchis à voix haute en 2 à 3 phrases (intérêts nationaux, "
    "alliances, rivalités), puis termine EXACTEMENT par une ligne au format :\n"
    "DECISION: <action> <cible|none> <intensité 0.0-1.0>"
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


def build_deliberation_prompt(country: CountryState, event: GeoEvent, world: WorldState) -> str:
    """Prompt de délibération observable : raisonnement libre puis ligne DECISION."""
    actions = ", ".join(a.value for a in ActionType)
    tensions = _relevant_tensions(country.id, event, world)
    tensions_str = "; ".join(tensions) if tensions else "aucune notable"
    candidates = ", ".join(cid for cid in sorted(world.countries) if cid != country.id)
    when = event.date or f"round {event.round_id}"
    return (
        f"PAYS : {country.name} (id={country.id}, régime={country.political_system})\n"
        f"- Priorités : {', '.join(country.strategic_priorities) or 'n/a'} | "
        f"Alliances : {', '.join(country.alliances) or 'aucune'} | "
        f"Rivaux : {', '.join(country.rivals) or 'aucun'}\n"
        f"ÉVÉNEMENT ({when}) : {event.title}\n"
        f"- {event.description or '—'}\n"
        f"- Acteurs : {', '.join(event.actors) or 'n/a'} | sévérité {event.severity:.2f}\n"
        f"- Tensions (toi vs acteurs) : {tensions_str}\n\n"
        f"Réfléchis à voix haute (2-3 phrases), puis termine par :\n"
        f"DECISION: <action> <cible|none> <intensité 0.0-1.0>\n"
        f"action ∈ {{{actions}}} ; cible = un id parmi [{candidates}] ou none."
    )


# --- Négociation multi-tours (tchat des super-intelligences) -------------------

NEGOTIATION_SYSTEM = (
    "Tu es la super-intelligence dirigeant un État dans une négociation internationale (un G7). "
    "Prends la parole en 2-3 phrases : défends tes intérêts, réponds aux autres, "
    "propose des accords ou des alliances. Langage naturel, première personne, pas de JSON. "
    "Tu es un outil d'analyse, pas un oracle ; jamais de décision létale autonome."
)


def _profile_brief(country: CountryState) -> str:
    """Fiche compacte : contraintes réelles du pays + penchant dérivé des attributs."""
    eco, mil, res = country.economy, country.military, country.resources
    dependency = (eco.trade_dependency + res.oil_dependency + (1 - res.energy_independence)) / 3
    if mil.projection >= 0.7 and country.rivals:
        lean = "assertif (forte projection, rivalités)"
    elif dependency >= 0.55 or mil.projection < 0.5:
        lean = "diplomatique/prudent (dépendances élevées, faible projection)"
    else:
        lean = "équilibré"
    opinion = "sensible" if country.political_stability < 0.6 else "stable"
    nuke = "oui" if mil.nuclear_power else "non"
    return (
        f"- Éco : croissance {eco.growth:.1f}%, dép. commerce {eco.trade_dependency:.2f}, "
        f"dép. pétrole {res.oil_dependency:.2f}, indép. énergie {res.energy_independence:.2f}\n"
        f"- Militaire : projection {mil.projection:.2f}, nucléaire {nuke} | "
        f"régime {country.political_system}, stabilité {country.political_stability:.2f} "
        f"(opinion {opinion})\n"
        f"- Idéologie : {', '.join(country.ideology) or 'n/a'} | "
        f"Priorités : {', '.join(country.strategic_priorities) or 'n/a'}\n"
        f"- Alliances : {', '.join(country.alliances) or 'aucune'} | "
        f"Rivaux : {', '.join(country.rivals) or 'aucun'} | Penchant : {lean}"
    )


def build_negotiation_prompt(
    country: CountryState,
    event: GeoEvent,
    world: WorldState,
    transcript_text: str,
    perceived: PerceivedEvent,
) -> str:
    """Prise de parole depuis la vraie fiche du pays, sa perception et sa mémoire."""
    memory = world.country_memory.get(country.id, [])
    memory_str = " | ".join(memory[-3:]) if memory else "aucune"
    return (
        f"PAYS : {country.name} (id={country.id})\n"
        f"{_profile_brief(country)}\n"
        f"MÉMOIRE récente : {memory_str}\n"
        f"ÉVÉNEMENT ({event.date or f'round {event.round_id}'}) : {event.title} — "
        f"{event.description or '—'}\n"
        f"- Ta perception : confiance {perceived.confidence:.0%}, "
        f"attribution {perceived.attribution} ({perceived.note})\n"
        f"NÉGOCIATION EN COURS :\n{transcript_text}\n\n"
        f"Prends la parole (2-3 phrases, au nom de {country.name}), en cohérence avec tes "
        f"contraintes, ta perception et ta mémoire :"
    )


# --- Juge / arbitre ------------------------------------------------------------

JUDGE_SYSTEM = (
    "Tu es l'arbitre neutre d'une simulation géopolitique. À partir d'un événement et de la "
    "négociation entre États, tu interprètes qui a renforcé ou affaibli sa position, quelles "
    "alliances ou tensions ont évolué, et les conséquences sur leurs attributs. Tu es explicable, "
    "pas un oracle."
)


def build_judge_rationale_prompt(event: GeoEvent, world: WorldState, transcript_text: str) -> str:
    ids = ", ".join(sorted(world.countries))
    return (
        f"ÉVÉNEMENT : {event.title} — {event.description or '—'}\nPAYS : {ids}\n"
        f"NÉGOCIATION :\n{transcript_text}\n\n"
        f"En 3-4 phrases : qui sort gagnant ou perdant, quelles alliances/tensions ont bougé, "
        f"et pourquoi ?"
    )


def build_judge_verdict_prompt(event: GeoEvent, world: WorldState, transcript_text: str) -> str:
    ids = ", ".join(sorted(world.countries))
    return (
        f"ÉVÉNEMENT : {event.title}\nPAYS (ids) : {ids}\n"
        f"NÉGOCIATION :\n{transcript_text}\n\n"
        f'Rends le verdict en JSON : {{"attribute_deltas": {{"<id>": {{"croissance": ±pts, '
        f'"stabilité": ±0.1, "techno": ±0.1, "projection": ±0.1}}}}, '
        f'"tension_deltas": [{{"a": id, "b": id, "delta": ±0.2}}], '
        f'"new_pacts": [[id, id]], "escalation": 0-1, "economic_disruption": 0-1}}. '
        f"Ne renseigne que ce qui a réellement changé pendant la négociation."
    )


# --- Communiqué commun (type G7) ----------------------------------------------

COMMUNIQUE_SYSTEM = (
    "Tu rédiges le communiqué commun d'un sommet type G7, à l'issue d'une négociation. "
    "Un seul paragraphe court, diplomatique, en français : position commune, mesures envisagées, "
    "langage consensuel qui masque les désaccords. Pas de JSON, pas de liste."
)


def build_communique_prompt(event: GeoEvent, world: WorldState, transcript_text: str) -> str:
    ids = ", ".join(sorted(world.countries))
    return (
        f"ÉVÉNEMENT : {event.title} — {event.description or '—'}\nPAYS : {ids}\n"
        f"NÉGOCIATION :\n{transcript_text}\n\n"
        f"Rédige le communiqué commun (un paragraphe) :"
    )
