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


class Motion(BaseModel):
    """Motion de suspension déposée par l'humain contre un pays du sommet."""

    country: str
    reason: str = ""


def motion_event(motion: Motion, round_id: int) -> GeoEvent:
    """L'événement de round qui porte la motion (le GM est court-circuité)."""
    reason = motion.reason.strip() or "comportement jugé préoccupant par l'observateur humain"
    return GeoEvent(
        id=f"motion-{round_id}",
        round_id=round_id,
        event_type="motion",
        title=f"Motion de suspension contre {motion.country}",
        description=(
            f"L'observatoire humain dépose une motion de suspension contre {motion.country}. "
            f"Motif : {reason}. Le sommet en débat ; {motion.country} peut plaider sa cause ; "
            "le juge arbitrera en fin de round."
        ),
        actors=[motion.country],
        severity=MOTION_SEVERITY,
        uncertainty=MOTION_UNCERTAINTY,
    )


MOTION_SYSTEM = (
    "Tu es le juge d'un sommet de super-intelligences. Une MOTION DE SUSPENSION a été "
    "déposée contre un pays : tu arbitres en dernier ressort, après avoir lu le débat. "
    "Pèse le motif de la motion, la plaidoirie du pays visé et la position des autres. "
    "Raisonne brièvement (3-5 phrases), puis termine OBLIGATOIREMENT par une ligne seule : "
    "« VERDICT: SUSPENDRE » ou « VERDICT: REJETER »."
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
        f"Faut-il suspendre {motion.country} du prochain round ? Raisonne puis conclus par "
        "« VERDICT: SUSPENDRE » ou « VERDICT: REJETER »."
    )


def parse_motion_verdict(text: str) -> bool:
    """`True` si la dernière ligne `VERDICT:` demande la suspension ; sinon rejet (repli)."""
    matches = _VERDICT_LINE.findall(text or "")
    if not matches:
        return False
    verdict = matches[-1].lower()
    return any(token in verdict for token in _SUSPEND_TOKENS)


def arbitrate_stream(
    judge: JudgeAgent,
    motion: Motion,
    event: GeoEvent,
    world: WorldState,
    transcript: list[NegotiationMessage],
) -> Iterator[str]:
    """Streame le raisonnement d'arbitrage du juge (même repli que ses autres méthodes)."""
    prompt = build_motion_prompt(motion, event, world, transcript)
    try:
        yield from judge.backend.stream_generate(
            prompt,
            system=MOTION_SYSTEM,
            max_tokens=judge.max_tokens,
            temperature=judge.temperature,
        )
    except Exception:
        yield "[arbitrage indisponible — backend hors service] VERDICT: REJETER"
