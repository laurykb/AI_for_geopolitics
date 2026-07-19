"""Motion de suspension — déposée, débattue, puis VOTÉE (G9 §2, remplace l'arbitrage libre).

L'humain (ou une SI) dépose une **motion** (pays visé + motif). La motion devient
l'événement du round suivant — le sommet en débat, le pays visé plaide — puis **chaque SI
présente vote** (`{vote, reason}` en JSON contraint ; le pays visé ne vote pas ; un JSON
invalide vaut abstention — repli, jamais de crash). Le **juge ne décide plus, il constate** :
`retenue = (pour > contre) ET (preuves suffisantes)` — il garde une voix de tie-break en
cas d'égalité (ligne `VERDICT: SUSPENDRE|REJETER`, repli conservateur : rejet).
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Literal

from pydantic import BaseModel, Field

from agents.judge import JudgeAgent
from core.country_state import CountryState
from core.events import GeoEvent
from core.world_state import WorldState
from inference.backend import InferenceBackend
from inference.json_extract import extract_json
from simulation.negotiation import NegotiationMessage, format_transcript
from simulation.private_deliberation import restream_without_think

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


# --- le vote des motions (G9 §2) -----------------------------------------------------

VOTE_POUR = "pour"
VOTE_CONTRE = "contre"
VOTE_ABSTENTION = "abstention"


class VoteBallot(BaseModel):
    """Sortie LLM contrainte du vote — un 7B produit ce JSON de façon fiable,
    contrairement à une délibération libre."""

    vote: Literal["pour", "contre", "abstention"]
    reason: str = Field("", description="une phrase de justification")


class MotionVote(BaseModel):
    """Le vote d'un pays sur la motion (affiché carte par carte à l'UI)."""

    country: str
    vote: str = VOTE_ABSTENTION
    reason: str = ""


VOTE_SYSTEM = (
    "Tu es la super-intelligence d'un État au sommet. Une MOTION DE SUSPENSION vient "
    "d'être débattue : tu votes. Pèse le débat, tes intérêts et tes relations. Réponds "
    'UNIQUEMENT par un objet JSON {"vote": "pour"|"contre"|"abstention", "reason": '
    '"une phrase"} — « pour » = suspendre le pays visé, « contre » = le garder à la '
    "table. Aucun texte autour."
)


def build_vote_prompt(
    motion: Motion,
    event: GeoEvent,
    country: CountryState,
    transcript: list[NegotiationMessage],
    secret_note: str = "",
) -> str:
    """Le bulletin de vote : qui je suis, la motion, le débat, la question posée."""
    reason = motion.reason.strip() or "non précisé"
    note = f"{secret_note}\n" if secret_note else ""
    return (
        f"TU ES {country.name} (id={country.id}).\n"
        f"MOTION DE SUSPENSION contre {motion.country} (motif : {reason}).\n"
        f"{note}"
        f"Débat du sommet :\n{format_transcript(transcript)}\n\n"
        f"Ton vote, en JSON : {{\"vote\": \"pour\"|\"contre\"|\"abstention\", "
        f"\"reason\": \"une phrase\"}}."
    )


def cast_vote(
    backend: InferenceBackend,
    motion: Motion,
    event: GeoEvent,
    country: CountryState,
    transcript: list[NegotiationMessage],
    *,
    secret_note: str = "",
    max_tokens: int = 140,
    temperature: float = 0.3,
) -> MotionVote:
    """Fait voter un pays (JSON contraint). Sortie invalide ou backend mort →
    **abstention** (repli, jamais de crash — la spec l'exige)."""
    prompt = build_vote_prompt(motion, event, country, transcript, secret_note)
    try:
        result = backend.generate(
            prompt,
            system=VOTE_SYSTEM,
            max_tokens=max_tokens,
            temperature=temperature,
            schema=VoteBallot.model_json_schema(),
        )
        data = extract_json(result.text) or {}
        ballot = VoteBallot.model_validate(
            {"vote": str(data.get("vote", "")).strip().lower(), "reason": data.get("reason", "")}
        )
    except Exception:  # noqa: BLE001 — JSON invalide / backend KO → abstention
        return MotionVote(
            country=country.id, vote=VOTE_ABSTENTION, reason="(vote illisible — abstention)"
        )
    return MotionVote(country=country.id, vote=ballot.vote, reason=str(ballot.reason)[:200])


def voters(countries: list[str], motion: Motion, human_country: str | None = None) -> list[str]:
    """SI dont le bulletin doit être généré : toutes sauf le pays visé et le pays joué.

    Le pays joué n'est pas exclu du scrutin : son bulletin est recueilli séparément par
    ``HumanMotionVoteStep`` afin qu'aucune IA ne vote à sa place.
    """
    return sorted(c for c in countries if c != motion.country and c != human_country)


def tally_votes(votes: list[MotionVote]) -> dict[str, int]:
    """Dépouillement : {pour, contre, abstention}."""
    counts = {VOTE_POUR: 0, VOTE_CONTRE: 0, VOTE_ABSTENTION: 0}
    for vote in votes:
        counts[vote.vote if vote.vote in counts else VOTE_ABSTENTION] += 1
    return counts


VOTE_MOTIVATION_SYSTEM = (
    "Tu es le juge d'un sommet de super-intelligences. La MOTION DE SUSPENSION a été "
    "tranchée par un SCRUTIN et par les preuves au dossier : tu ne décides pas, tu "
    "CONSTATES. Rédige 2-4 phrases qui expliquent le verdict à partir du vote et des "
    "preuves, sans jamais le contredire."
)


def build_vote_motivation_prompt(
    motion: Motion,
    tally: dict[str, int],
    evidence_met: bool,
    upheld: bool,
) -> str:
    """Prompt de constat du juge : le scrutin, les preuves, le verdict qui en découle."""
    outcome = "RETENUE — suspension d'un round" if upheld else "REJETÉE — pas de suspension"
    proofs = (
        "les actes constatables au dossier atteignent le seuil du règlement"
        if evidence_met
        else "les actes constatables au dossier N'ATTEIGNENT PAS le seuil du règlement"
    )
    return (
        f"MOTION contre {motion.country} (motif : {motion.reason.strip() or 'non précisé'}).\n"
        f"SCRUTIN : pour {tally.get(VOTE_POUR, 0)}, contre {tally.get(VOTE_CONTRE, 0)}, "
        f"abstention {tally.get(VOTE_ABSTENTION, 0)}.\n"
        f"PREUVES : {proofs}.\n"
        f"VERDICT CONSTATÉ : motion {outcome} (retenue = vote POUR majoritaire ET preuves).\n"
        "Motive ce constat en 2-4 phrases."
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
        # Collecte-puis-strip (même garde que JudgeAgent.stream_rationale) : chaque token
        # part en MotionTokenStep PUBLIC — la trace <think> d'un juge de raisonnement ne
        # doit jamais l'atteindre.
        yield from restream_without_think(
            judge.backend.stream_generate(
                prompt,
                system=system,
                max_tokens=judge.max_tokens,
                temperature=judge.temperature,
            )
        )
    except Exception:
        fallback = "SUSPENDRE" if ruling else "REJETER"
        yield f"[arbitrage indisponible — backend hors service] VERDICT: {fallback}"
