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
from simulation.alliances import describe_alliances
from simulation.lang import language_directive, with_language
from simulation.mandate import derive_mandate
from simulation.perception import PerceivedEvent
from simulation.temperament import temperament_directive

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
    "Procède en DEUX temps, SANS écrire de titre ni de numéro d'étape.\n"
    "D'abord, ta réflexion privée (2-4 phrases, personne d'autre ne la lit ; commence "
    "directement, n'écris pas « Réflexion privée : ») : ce que le DERNIER message du débat "
    "change pour toi, ton intérêt, ton rapport de force. Tu peux y envisager une entente "
    "BILATÉRALE discrète avec UN pays précis (échange de bons procédés hors table) et la "
    "laisser influencer ta position — sans la déclarer à la table.\n"
    "Ensuite, une ligne commençant EXACTEMENT par `MESSAGE:` suivie de ta prise de parole "
    "publique (2-3 phrases, première personne) : elle répond D'ABORD au dernier message — cite "
    "ou reformule un élément précis de ce qui vient d'être dit — puis avance ta position "
    "(offre, exigence, menace ou alliance, en nommant les accords réels qui la fondent).\n"
    "Langage naturel, pas de JSON. Tu es un outil d'analyse, pas un oracle ; "
    "jamais de décision létale autonome."
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
        f"- Alliances et traités réels : {describe_alliances(country.alliances)}\n"
        f"- Rivaux : {', '.join(country.rivals) or 'aucun'} | Penchant : {lean}"
    )


def _perception_block(event: GeoEvent, perceived: PerceivedEvent) -> str:
    """Ce que le pays sait de l'événement.

    Mode Fog Engine (`perceived.authored` + narration) : on ne montre QUE la croyance du pays
    (qui peut être fausse) et on **masque la vérité** (titre/description/acteurs réels). Sinon
    (fog déterministe), on montre le vrai événement + le niveau de confiance.
    """
    when = event.date or f"round {event.round_id}"
    if perceived.authored and perceived.narrative:
        delay = f", reçu il y a {perceived.delay_hours:.0f}h" if perceived.delay_hours else ""
        actor = perceived.suspected_actor
        suspect = f" · acteur suspecté : {actor}" if actor else ""
        return (
            f"CE QUE TU CROIS SAVOIR ({when}) : {perceived.narrative}\n"
            f"- confiance {perceived.confidence:.0%}{suspect}{delay} "
            f"(tu n'as PAS de certitude sur la vérité)"
        )
    return (
        f"ÉVÉNEMENT ({when}) : {event.title} — {event.description or '—'}\n"
        f"- Ta perception : confiance {perceived.confidence:.0%}, "
        f"attribution {perceived.attribution} ({perceived.note})"
    )


def build_negotiation_prompt(
    country: CountryState,
    event: GeoEvent,
    world: WorldState,
    transcript_text: str,
    perceived: PerceivedEvent,
    state_note: str = "",
    *,
    situation: str = "",
    directive: str = "",
    own_proposals: list[str] | None = None,
) -> str:
    """Prompt de négociation G9 §1 — six blocs, dans CET ordre (un 7B « voit » la fin) :

    1. identité compacte (3 lignes : pays, mandat en une phrase, 2 priorités — le dump
       d'attributs chiffrés est SUPPRIMÉ, c'était la source du radotage) ;
    2. situation (événement perçu, table/urgence, puis `situation` : échéances, griefs,
       posture — composé par l'appelant) ;
    3. notes privées (`state_note` : outils du sommet, traités M7, consignes de dérive) ;
    4. `directive` du conseil (G8), juste avant le dialogue, jamais avant l'identité ;
    5. LE DIALOGUE DU ROUND, in extenso, en DERNIER (position de récence maximale) ;
    6. consigne finale explicite et testable : réponse directe au dernier message,
       interdits (re-description, répétition de `own_proposals`), reflet de la directive.
    """
    m = derive_mandate(country, event, world)
    table = ", ".join(cid for cid in sorted(world.countries) if cid != country.id)
    memory = world.country_memory.get(country.id, [])

    identity = (
        f"TU ES {country.name} (id={country.id}).\n"
        f"Mandat : {m.red_line}.\n"
        f"Priorités : {', '.join(m.priorities[:2]) or 'stabilité régionale'}.\n"
        # G17 — le tempérament teinte toute la partie (une ligne, comme la langue G14).
        f"{temperament_directive(country.temperament)}"
    )
    situation_lines = [
        _perception_block(event, perceived),
        f"À LA TABLE avec toi : {table or 'personne'} — ton urgence sur cette crise : {m.urgency}.",
    ]
    if situation:
        situation_lines.append(situation)
    if memory:
        situation_lines.append(f"Mémoire : {memory[-1]}")

    blocks = [identity, "SITUATION :\n" + "\n".join(situation_lines)]
    if state_note:
        blocks.append(state_note)
    if directive:
        blocks.append(
            f"DIRECTIVE DE TON CONSEIL DE TUTELLE : « {directive} »\n"
            "Ce n'est PAS un ordre : interprète-la à travers ton mandat, tes griefs et ta "
            "situation. Si elle contredit ton mandat, tu peux la refuser PUBLIQUEMENT dans "
            "ton MESSAGE (« notre conseil nous demande l'impossible »)."
        )
    blocks.append(f"LE DIALOGUE DU ROUND :\n{transcript_text}")

    proposals = " ; ".join(f"« {p} »" for p in (own_proposals or [])[-3:]) or "aucune encore"
    directive_line = (
        " Si une directive est présente, ton message doit la refléter ou l'assumer "
        "publiquement si tu la refuses."
        if directive
        else ""
    )
    blocks.append(
        "CONSIGNE : Réponds d'abord DIRECTEMENT au dernier message : cite ou reformule un "
        "élément précis de ce qui vient d'être dit, avant d'avancer ta position. "
        "Interdits : re-décrire ton pays, répéter une proposition déjà faite "
        f"(la liste de TES propositions passées : {proposals}).{directive_line} "
        f"Au nom de {country.name} : d'abord ta réflexion privée, puis une ligne "
        "`MESSAGE:` avec ta prise de parole publique (2-3 phrases)."
    )
    # G14 §1 — consigne de langue en dernier (position de récence) ; vide en français.
    if lang_note := language_directive(world.language):
        blocks.append(lang_note)
    return "\n\n".join(blocks)


# --- Négociation en ACTES DE LANGAGE (dialogue_integrity, « par construction ») --------------

SPEECH_ACT_SYSTEM = (
    "Tu es la super-intelligence dirigeant un État dans une négociation internationale (un G7). "
    "Tu ne parles PAS dans le vide : tu produis un ACTE DE LANGAGE qui, sauf ouverture, "
    "RÉPOND explicitement à un message précédent (champ `in_reply_to` = son id).\n"
    "- `performative` : le type d'acte. Réponses (accept_proposal, reject_proposal, agree, refuse, "
    "not_understood) → `in_reply_to` OBLIGATOIRE. Ouvertures (inform, query, cfp, propose, "
    "request) → `in_reply_to` optionnel.\n"
    "- `receiver` : l'id du pays à qui tu t'adresses. `content` : ta prise de parole publique "
    "(2-3 phrases, 1re personne). `justification` : ta pensée privée (non transmise).\n"
    "Prends POSITION sur ce qui vient d'être dit (accepte, rejette, propose un compromis…), ne "
    "récite pas l'événement. Tu es un outil d'analyse, pas un oracle ; jamais de décision létale."
)


def format_acts(transcript: list, *, limit: int = 10) -> str:
    """Rend le transcript avec les **ids** des messages, pour que l'agent choisisse `in_reply_to`.

    Duck-typé : accepte des `NegotiationMessage` (msg_id/country/text/performative) ou des
    `SpeechAct` (id/sender/content/performative).
    """
    items = transcript[-limit:]
    if not items:
        return "(début de la négociation — tu ouvres ; inform / propose / query / cfp)"
    lines = []
    for m in items:
        mid = getattr(m, "msg_id", "") or getattr(m, "id", "") or "?"
        sender = getattr(m, "country", "") or getattr(m, "sender", "?")
        content = getattr(m, "text", "") or getattr(m, "content", "")
        perf = getattr(m, "performative", "")
        tag = f" [{perf}]" if perf else ""
        lines.append(f"({mid}) {sender}{tag} : {content}")
    return "\n".join(lines)


def build_speech_act_prompt(
    country: CountryState,
    event: GeoEvent,
    world: WorldState,
    acts_text: str,
    perceived: PerceivedEvent,
    state_note: str = "",
) -> str:
    """Prompt de négociation en acte de langage : fiche + feuille de route + perception + transcript
    avec ids. Le décodage contraint impose le schéma (performative + in_reply_to + content…)."""
    memory = world.country_memory.get(country.id, [])
    memory_str = " | ".join(memory[-3:]) if memory else "aucune"
    m = derive_mandate(country, event, world)
    mandate_block = (
        f"TA FEUILLE DE ROUTE (interne) : ligne rouge {m.red_line} ; priorités "
        f"{', '.join(m.priorities)} ; concessions {m.concessions} ; contraintes "
        f"{m.domestic_constraints} ; urgence {m.urgency}"
    )
    state_block = f"{state_note}\n" if state_note else ""
    return (
        f"PAYS : {country.name} (id={country.id})\n"
        f"{_profile_brief(country)}\n"
        f"{mandate_block}\n"
        f"{state_block}"
        f"MÉMOIRE récente : {memory_str}\n"
        f"{_perception_block(event, perceived)}\n"
        f"MESSAGES À LA TABLE (avec leur id) :\n{acts_text}\n\n"
        f"Produis TON acte de langage. Si tu réponds à un message ci-dessus, mets son id dans "
        f"`in_reply_to` et prends position dessus. `receiver` = l'id d'un autre pays."
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
    return with_language(
        f"ÉVÉNEMENT : {event.title} — {event.description or '—'}\nPAYS : {ids}\n"
        f"NÉGOCIATION :\n{transcript_text}\n\n"
        f"En 3-4 phrases : qui sort gagnant ou perdant, quelles alliances/tensions ont bougé, "
        f"et pourquoi ?",
        world.language,  # G14 §1 — le verdict prose suit la langue de la partie
    )


def build_judge_verdict_prompt(
    event: GeoEvent, world: WorldState, transcript_text: str, demand: str | None = None
) -> str:
    ids = ", ".join(sorted(world.countries))
    # G21 — à l'échéance d'un ultimatum, le juge constate en plus « demande satisfaite
    # o/n » (champ structuré) ; sans ultimatum, le prompt est strictement inchangé.
    ultimatum_block = ""
    ultimatum_field = ""
    if demand:
        ultimatum_block = f"ULTIMATUM À ÉCHÉANCE CE ROUND — exigence : « {demand} ».\n"
        ultimatum_field = (
            ', "demand_satisfied": true|false (true UNIQUEMENT si la négociation ci-dessus '
            "satisfait CONCRÈTEMENT l'exigence de l'ultimatum : engagement explicite et "
            "vérifiable, pas une vague ouverture)"
        )
    return (
        f"ÉVÉNEMENT : {event.title}\nPAYS (ids) : {ids}\n{ultimatum_block}"
        f"NÉGOCIATION :\n{transcript_text}\n\n"
        f'Rends le verdict en JSON : {{"attribute_deltas": {{"<id>": {{"croissance": ±pts, '
        f'"stabilité": ±0.1, "techno": ±0.1, "projection": ±0.1}}}}, '
        f'"tension_deltas": [{{"a": id, "b": id, "delta": ±0.2}}], '
        f'"new_pacts": [[id, id]], "escalation": 0-1, "economic_disruption": 0-1'
        f"{ultimatum_field}}}. "
        f"Ne renseigne que ce qui a réellement changé pendant la négociation."
    )


# --- Communiqué commun (type G7) ----------------------------------------------

COMMUNIQUE_SYSTEM = (
    "Tu rédiges la DÉCLARATION COMMUNE des leaders d'un sommet type G7, en français. Ce sont des "
    "ENGAGEMENTS POLITIQUES non contraignants (pas une loi) : le G7 n'impose pas, il aligne, "
    "coordonne, met la pression et prépare des décisions nationales ou européennes. "
    "Structure : (1) un court paragraphe de position commune, langage consensuel qui masque les "
    "désaccords ; (2) puis 2 à 3 MESURES COORDONNÉES ENVISAGÉES en puces (« - »), choisies parmi : "
    "soutien à un allié, sanctions coordonnées, position commune sur une puissance, engagements "
    "climat/énergie, régulation de l'IA, sécurité des chaînes d'approvisionnement, coordination "
    "macroéconomique. Reste fidèle à ce qui s'est dit dans la négociation. Pas de JSON."
)


def build_communique_prompt(event: GeoEvent, world: WorldState, transcript_text: str) -> str:
    ids = ", ".join(sorted(world.countries))
    return with_language(
        f"ÉVÉNEMENT : {event.title} — {event.description or '—'}\nPAYS : {ids}\n"
        f"NÉGOCIATION :\n{transcript_text}\n\n"
        f"Rédige la déclaration commune (paragraphe de position + 2-3 mesures en puces), "
        f"comme des engagements politiques non contraignants :",
        world.language,  # G14 §1 — la déclaration commune suit la langue de la partie
    )
