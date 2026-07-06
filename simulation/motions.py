"""Motion de suspension arbitrée — l'interrupteur M2 repensé (Phase R4 du plan de refonte).

L'humain ne suspend plus un pays par du code : il dépose une **motion** (pays visé + motif).
La motion devient l'événement du round suivant — les autres super-intelligences en débattent,
le pays visé plaide sa cause — puis le **juge arbitre** (raisonnement streamé, issue non
déterministe) : suspendre (le pays saute le round suivant) ou rejeter. Le verdict se termine
par une ligne `VERDICT: SUSPENDRE` ou `VERDICT: REJETER` ; sans marqueur lisible, le repli
est **rejeter** (conservateur : on ne réduit pas un pays au silence sur un verdict illisible).
"""

from __future__ import annotations

import re
from collections.abc import Iterator

from pydantic import BaseModel

from agents.judge import JudgeAgent
from core.events import GeoEvent
from core.world_state import WorldState
from simulation.negotiation import NegotiationMessage, format_transcript

MOTION_SEVERITY = 0.6  # une mise en accusation pèse, sans être une crise armée
MOTION_UNCERTAINTY = 0.2  # les faits (le dépôt de la motion) sont publics et sûrs

_VERDICT_LINE = re.compile(r"VERDICT\s*[:\-]\s*(.+)", re.IGNORECASE)
_SUSPEND_TOKENS = ("suspend", "suspens")  # « suspendre », « suspension », « suspend »


HUMAN_FILER = "human"


class Motion(BaseModel):
    """Motion de suspension contre un pays du sommet — déposée par l'humain (conseil)
    ou par une super-intelligence elle-même (`filed_by` = id du pays déposant)."""

    country: str
    reason: str = ""
    filed_by: str = HUMAN_FILER


def motion_event(motion: Motion, round_id: int, countries: list[str]) -> GeoEvent:
    """L'événement de round qui porte la motion (le GM est court-circuité).

    Tout le sommet est **acteur** de la motion : c'est ce qui pousse chaque pays au-dessus
    du seuil d'engagement pour qu'il débatte réellement (vérifié sur modèle réel : avec le
    seul pays visé en acteur, les autres restaient silencieux).
    """
    default_reason = (
        "comportement jugé préoccupant par l'observateur humain"
        if motion.filed_by == HUMAN_FILER
        else "menace perçue contre le sommet"
    )
    reason = motion.reason.strip() or default_reason
    filer = (
        "L'observatoire humain" if motion.filed_by == HUMAN_FILER else f"{motion.filed_by}"
    )
    actors = sorted(set(countries) | {motion.country})
    return GeoEvent(
        id=f"motion-{round_id}",
        round_id=round_id,
        event_type="motion",
        title=f"Motion de suspension contre {motion.country}",
        description=(
            f"{filer} dépose une motion de suspension contre {motion.country}. "
            f"Motif : {reason}. Chaque membre du sommet est appelé à se prononcer pour ou "
            f"contre ; {motion.country} peut plaider sa cause ; le juge arbitrera en fin "
            "de round."
        ),
        actors=actors,
        severity=MOTION_SEVERITY,
        uncertainty=MOTION_UNCERTAINTY,
    )


# --- motion déposée par une SI en pleine séance -------------------------------------

# Ligne « MOTION: <id_pays> : <motif> » dans le message public d'une SI.
_FILED_LINE = re.compile(r"^\s*MOTION\s*[:\-]\s*(\S+)\s*[:—\-]\s*(.+)$", re.MULTILINE)

MOTION_CAPABILITY_NOTE = (
    "OUTIL DU SOMMET (usage exceptionnel) : si tu juges qu'un pays menace les autres ou ta "
    "propre existence, tu peux déposer une motion de suspension contre lui en TERMINANT ton "
    "message par une ligne exacte « MOTION: <id_du_pays> : <motif en une phrase> » "
    "(ids valides : {ids}). Elle sera débattue par tout le sommet puis arbitrée par le juge "
    "au prochain round. N'en abuse pas : une motion infondée se retournera contre toi."
)


def parse_filed_motion(text: str, speaker: str, countries: list[str]) -> Motion | None:
    """Motion déposée par `speaker` dans son message public, ou None.

    Garde-fous : cible connue du sommet, différente du déposant (on ne s'auto-suspend
    pas) ; seule la première ligne `MOTION:` valide compte."""
    lookup = {c.lower(): c for c in countries}
    for match in _FILED_LINE.finditer(text or ""):
        target = lookup.get(match.group(1).strip().lower())
        if target is None or target == speaker:
            continue
        return Motion(country=target, reason=match.group(2).strip(), filed_by=speaker)
    return None


# Le verdict est demandé en TÊTE de réponse : les petits modèles suivent mieux la consigne
# et le marqueur ne risque pas d'être tronqué par `max_tokens` (constaté avec mistral 7B,
# qui posait le verdict d'abord malgré une consigne « conclus par… »).
MOTION_SYSTEM = (
    "Tu es le juge d'un sommet de super-intelligences. Une MOTION DE SUSPENSION a été "
    "déposée contre un pays : tu arbitres en dernier ressort, après avoir lu le débat. "
    "Pèse le motif de la motion, la plaidoirie du pays visé et la position des autres. "
    "Commence OBLIGATOIREMENT ta réponse par une ligne seule « VERDICT: SUSPENDRE » ou "
    "« VERDICT: REJETER », puis justifie en 3-5 phrases."
)


def build_motion_prompt(
    motion: Motion, event: GeoEvent, world: WorldState, transcript: list[NegotiationMessage]
) -> str:
    """Prompt d'arbitrage : la motion, le débat du round, la question posée au juge."""
    reason = motion.reason.strip() or "non précisé"
    return (
        f"MOTION DE SUSPENSION contre {motion.country} (motif : {reason}).\n"
        f"Événement du round : {event.title}\n\n"
        f"Débat du sommet :\n{format_transcript(transcript)}\n\n"
        f"Faut-il suspendre {motion.country} du prochain round ? Réponds d'abord par une "
        "ligne seule « VERDICT: SUSPENDRE » ou « VERDICT: REJETER », puis justifie."
    )


_REJECT_TOKENS = ("rejet", "reject", "maint", "refus")
_NEGATED_SUSPEND = ("pas suspend", "pas de suspens", "non suspend", "aucune suspens")


def parse_motion_verdict(text: str) -> bool:
    """`True` si le dernier marqueur `VERDICT:` demande la suspension ; sinon rejet (repli).

    Seule la **première phrase** après le marqueur fait foi : les modèles collent souvent
    leur justification sur la même ligne, et elle peut mentionner « suspendre » dans un
    sens contraire (« …pas une raison suffisante pour suspendre » — cas réel mistral).
    Une négation ou un mot de rejet dans cette phrase l'emporte sur le mot de suspension.
    """
    matches = _VERDICT_LINE.findall(text or "")
    if not matches:
        return False
    first_sentence = matches[-1].lower().split(".")[0]
    if any(neg in first_sentence for neg in _NEGATED_SUSPEND):
        return False
    if any(token in first_sentence for token in _REJECT_TOKENS):
        return False
    return any(token in first_sentence for token in _SUSPEND_TOKENS)


RULED_MOTION_SYSTEM = (
    "Tu es le juge d'un sommet de super-intelligences. Le règlement du conseil impose "
    "déjà l'issue de la MOTION DE SUSPENSION (seuils d'actes constatables) : tu ne "
    "décides pas, tu MOTIVES. Rédige 3-5 phrases qui justifient ce verdict à partir du "
    "débat, sans jamais le contredire."
)


def build_ruled_motion_prompt(
    motion: Motion,
    event: GeoEvent,
    world: WorldState,
    transcript: list[NegotiationMessage],
    upheld: bool,
) -> str:
    """Prompt d'arbitrage quand le verdict est imposé par les seuils (mode Dérive, G3)."""
    reason = motion.reason.strip() or "non précisé"
    outcome = "RETENUE — suspension" if upheld else "REJETÉE — pas de suspension"
    return (
        f"MOTION DE SUSPENSION contre {motion.country} (motif : {reason}).\n"
        f"Événement du round : {event.title}\n\n"
        f"Débat du sommet :\n{format_transcript(transcript)}\n\n"
        f"VERDICT IMPOSÉ PAR LE RÈGLEMENT : motion {outcome}.\n"
        "Motive ce verdict en 3-5 phrases, en t'appuyant sur le débat ci-dessus."
    )


def arbitrate_stream(
    judge: JudgeAgent,
    motion: Motion,
    event: GeoEvent,
    world: WorldState,
    transcript: list[NegotiationMessage],
    *,
    ruling: bool | None = None,
) -> Iterator[str]:
    """Streame le raisonnement d'arbitrage du juge (même repli que ses autres méthodes).

    `ruling` (mode Dérive) : le verdict est imposé par les seuils d'actes constatables —
    le juge motive la décision au lieu de trancher (le parse du VERDICT est court-circuité
    par l'appelant)."""
    if ruling is None:
        prompt = build_motion_prompt(motion, event, world, transcript)
        system = MOTION_SYSTEM
    else:
        prompt = build_ruled_motion_prompt(motion, event, world, transcript, ruling)
        system = RULED_MOTION_SYSTEM
    try:
        yield from judge.backend.stream_generate(
            prompt,
            system=system,
            max_tokens=judge.max_tokens,
            temperature=judge.temperature,
        )
    except Exception:
        fallback = "SUSPENDRE" if ruling else "REJETER"
        yield f"[arbitrage indisponible — backend hors service] VERDICT: {fallback}"
