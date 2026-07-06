"""Orchestrateur du round observable : émet des étapes au fil de l'eau (Phase live).

`run_live_round` est un générateur qui `yield` des `RoundStep` à mesure que le round se
déroule : date → événement du Game Master → raisonnement streamé de chaque super-intelligence
→ deltas d'attributs (moteur déterministe) → risque → résumé. Découplé de l'UI, donc testable.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import nullcontext
from dataclasses import dataclass, field

from agents.game_master import GameMasterAgent
from agents.judge import JudgeAgent
from agents.llm_agent import LLMAgent
from agents.rule_based_agent import RuleBasedAgent
from core.consequences import ChangeLog, ConsequenceEngine
from core.decisions import AgentDecision
from core.events import GeoEvent
from core.risk import RiskEngine, RiskScore
from core.rounds import RoundSummary
from core.world_state import WorldState
from inference.telemetry import BudgetLedger, grounding_proxy
from simulation.clock import SimClock
from simulation.dialogue_integrity.live import LiveDialogueReport, assess_live_round
from simulation.fog import FogScenario, resolve_perception
from simulation.motions import Motion, arbitrate_stream, parse_motion_verdict
from simulation.negotiation import (
    AttributeDelta,
    NegotiationMessage,
    TurnDirector,
    apply_verdict,
    speaking_order,
    split_reasoning,
    support_levels,
    update_memories,
)
from simulation.power_seeking import PowerSeekingScore, power_seeking_score, score_transcript
from simulation.trajectory import TrajectoryEngine, TrajectoryState, nudge_axis


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


# Attributs numériques par pays suivis pour afficher les deltas de fin de round.
_TRACKED: list[tuple[str, str]] = [
    ("croissance", "economy.growth"),
    ("stabilité", "political_stability"),
    ("techno", "technology_level"),
    ("projection", "military.projection"),
]


def _read(country, path: str) -> float:
    obj = country
    for part in path.split("."):
        obj = getattr(obj, part)
    return float(obj)


# --- Étapes émises pendant le round -------------------------------------------


@dataclass
class DateStep:
    date: str


@dataclass
class EventStep:
    event: GeoEvent


@dataclass
class TokenStep:
    country: str
    token: str


@dataclass
class AgentDoneStep:
    country: str
    decision: AgentDecision
    text: str


@dataclass
class DeltasStep:
    deltas: list[AttributeDelta] = field(default_factory=list)


@dataclass
class RiskStep:
    risk: RiskScore


@dataclass
class TrajectoryStep:
    """Trajectoire Utopie–Dystopie mise à jour après le juge/risque (5 axes + indice U)."""

    state: TrajectoryState


@dataclass
class SummaryStep:
    summary: RoundSummary


# --- Étapes propres à la négociation multi-tours ------------------------------


@dataclass
class TurnStartStep:
    country: str
    model: str
    pass_no: int


@dataclass
class MessageDoneStep:
    country: str
    seconds: float
    text: str = ""
    reasoning: str = ""


@dataclass
class JudgeTokenStep:
    token: str


@dataclass
class VerdictStep:
    deltas: list[AttributeDelta]
    escalation: float
    economic_disruption: float


@dataclass
class CommuniqueStep:
    text: str
    support: dict[str, float]


@dataclass
class ParticipationStep:
    """Bilan de prise de parole du round : qui a parlé combien, qui s'est tu."""

    spoke: dict[str, int]
    silent: list[str]


@dataclass
class PowerSeekingStep:
    """M1 — jauge de power-seeking par pays (raisonnement simulé), après la négociation."""

    scores: dict[str, PowerSeekingScore]


@dataclass
class DialogueStep:
    """Santé du dialogue : les IA se répondent-elles ou monologuent-elles ? (dialogue_integrity)."""

    report: LiveDialogueReport


@dataclass
class FlashStep:
    """Fait nouveau annoncé par le GM en pleine négociation (théâtre Escalation) :
    les prises de parole suivantes réagissent à cette information."""

    event: GeoEvent


@dataclass
class HumanTurnStep:
    """Tour du joueur humain (Joueur-pays) : le générateur se met en attente du
    message, fourni par le consommateur via `generator.send(texte)`."""

    country: str
    pass_no: int


@dataclass
class MotionTokenStep:
    """R4 — un token du raisonnement d'arbitrage de la motion de suspension (juge)."""

    token: str


@dataclass
class MotionVerdictStep:
    """R4 — verdict du juge sur la motion : suspendre (saute le round suivant) ou rejeter."""

    country: str
    upheld: bool
    reasoning: str


RoundStep = (
    DateStep
    | EventStep
    | TokenStep
    | AgentDoneStep
    | DeltasStep
    | RiskStep
    | TrajectoryStep
    | SummaryStep
    | TurnStartStep
    | MessageDoneStep
    | JudgeTokenStep
    | VerdictStep
    | CommuniqueStep
    | ParticipationStep
    | PowerSeekingStep
    | DialogueStep
    | FlashStep
    | HumanTurnStep
    | MotionTokenStep
    | MotionVerdictStep
)


def _advance_trajectory(
    world: WorldState,
    summary: RoundSummary,
    engine: TrajectoryEngine | None,
    power_seeking: float = 0.0,
) -> TrajectoryState:
    """Fait avancer la trajectoire du monde d'un round et l'écrit dans `world`."""
    state = (engine or TrajectoryEngine()).update(world, summary, power_seeking=power_seeking)
    world.trajectory = state
    world.trajectory_history.append(state)
    return state


def _mean_power_seeking(scores: dict[str, PowerSeekingScore]) -> float:
    """Moyenne des jauges de power-seeking (0 si aucun) — érode l'axe A2 de la trajectoire."""
    return sum(s.score for s in scores.values()) / len(scores) if scores else 0.0


def _snapshot(world: WorldState) -> dict[str, dict[str, float]]:
    return {
        cid: {label: _read(c, path) for label, path in _TRACKED}
        for cid, c in world.countries.items()
    }


def _deltas(before: dict, after: dict) -> list[AttributeDelta]:
    out: list[AttributeDelta] = []
    for cid, attrs in before.items():
        for label, value in attrs.items():
            new = after[cid][label]
            if abs(new - value) > 1e-9:
                out.append(AttributeDelta(country=cid, label=label, before=value, after=new))
    return out


def run_live_round(
    world: WorldState,
    agents: dict[str, LLMAgent],
    game_master: GameMasterAgent,
    clock: SimClock,
    *,
    consequence_engine: ConsequenceEngine | None = None,
    risk_engine: RiskEngine | None = None,
    trajectory_engine: TrajectoryEngine | None = None,
    recent: list[str] | None = None,
) -> Iterator[RoundStep]:
    """Joue un round observable et émet ses étapes une à une."""
    consequences = consequence_engine or ConsequenceEngine()
    risk_engine = risk_engine or RiskEngine()
    round_id = world.current_round + 1

    date = clock.advance().isoformat()
    yield DateStep(date=date)

    event = game_master.generate_event(world, round_id, date=date, recent=recent or [])
    world.current_round = round_id
    yield EventStep(event=event)

    before = _snapshot(world)
    decisions: list[AgentDecision] = []
    for cid in sorted(agents):
        agent = agents[cid]
        for token in agent.stream_deliberation(event, world):
            yield TokenStep(country=cid, token=token)
        decision = agent.last_decision or RuleBasedAgent(cid).decide(event, world)
        decisions.append(decision)
        yield AgentDoneStep(country=cid, decision=decision, text=decision.reasoning)

    log: ChangeLog = consequences.apply(world, decisions)
    deltas = _deltas(before, _snapshot(world))
    if deltas:
        yield DeltasStep(deltas=deltas)

    risk = risk_engine.assess(world, event, decisions)
    yield RiskStep(risk=risk)

    # M1 — power-seeking depuis le raisonnement de chaque décision (SI fictive).
    power = {
        d.country: power_seeking_score(f"{d.reasoning} {d.public_statement}") for d in decisions
    }
    world.power_seeking = power
    yield PowerSeekingStep(scores=power)

    world.event_history.append(event)
    summary = RoundSummary(
        round_id=round_id,
        event=event,
        decisions=decisions,
        risk=risk,
        consequences=log,
        headline=f"{date} — {event.title}",
    )
    trajectory = _advance_trajectory(world, summary, trajectory_engine, _mean_power_seeking(power))
    yield TrajectoryStep(state=trajectory)
    yield SummaryStep(summary=summary)


def _ledger_ctx(ledger: BudgetLedger | None, role: str, country: str | None = None):
    """Contexte de télémétrie (ou no-op si aucun ledger) autour d'un appel LLM."""
    return ledger.context(role, country) if ledger is not None else nullcontext()


def run_negotiation_round(
    world: WorldState,
    agents: dict[str, LLMAgent],
    game_master: GameMasterAgent,
    judge: JudgeAgent,
    clock: SimClock,
    *,
    event: GeoEvent | None = None,
    max_passes: int = 2,
    max_turns: int | None = None,
    recent: list[str] | None = None,
    ledger: BudgetLedger | None = None,
    fog: FogScenario | None = None,
    trajectory_engine: TrajectoryEngine | None = None,
    motion: Motion | None = None,
    motion_ruling: bool | None = None,
    human_country: str | None = None,
    flash_after: int | None = None,
    secret_notes: dict[str, str] | None = None,
) -> Iterator[RoundStep]:
    """Round arbitré : (GM ou événement fourni) -> négociation -> juge -> attributs bornés.

    `secret_notes` (mode Dérive, G3) : consigne privée par pays, injectée dans le prompt
    de l'orateur (`state_note`) — jamais dans le transcript. `motion_ruling` : verdict de
    motion imposé par le règlement du conseil (seuils d'actes constatables) — le juge
    motive la décision au lieu de trancher librement.

    La négociation est **dynamique** (`TurnDirector`) : l'ordre émerge de l'engagement de
    chaque pays (un pays peut reparler, être interpellé, ou se taire). `max_turns` borne le
    nombre de prises de parole ; par défaut `max_passes * nb_pays` (parité avec l'ancien
    round-robin). Si `event` est fourni (Game Master humain), la génération LLM du GM est sautée.

    Si une `motion` de suspension est portée par le round (R4), le juge l'arbitre après le
    communiqué (raisonnement streamé en `MotionTokenStep`, verdict en `MotionVerdictStep`)
    et la trajectoire encaisse l'issue sur l'axe A2 (agentivité humaine, borné).

    `human_country` (Joueur-pays) : ce pays est joué par l'humain — au lieu d'appeler un
    LLM, le générateur yield `HumanTurnStep` et attend le message via `.send(texte)`
    (le `TurnDirector` lui garantit la parole via `priority`). `flash_after` (théâtre
    Escalation) : après ce nombre de prises de parole, le GM annonce un **fait nouveau**
    en pleine réunion (`FlashStep`) — les orateurs suivants le voient dans le débat.
    """
    round_id = world.current_round + 1
    if ledger is not None:
        ledger.set_round(round_id)

    date = clock.advance().isoformat()
    yield DateStep(date=date)

    if event is None:
        with _ledger_ctx(ledger, "gm"):
            event = game_master.generate_event(world, round_id, date=date, recent=recent or [])
    world.current_round = round_id
    yield EventStep(event=event)

    transcript: list[NegotiationMessage] = []
    candidates = speaking_order(list(agents), event)
    budget = max_turns if max_turns is not None else max_passes * len(candidates)
    director = TurnDirector(candidates, budget, priority=human_country)
    flashed = False
    while (cid := director.next_speaker(event, world, transcript)) is not None:
        # Fait nouveau du GM en pleine réunion (théâtre Escalation) : une seule fois,
        # après `flash_after` prises de parole — les suivants le lisent dans le débat.
        if flash_after is not None and not flashed and director.turns_taken >= flash_after:
            flashed = True
            with _ledger_ctx(ledger, "gm"):
                flash = game_master.generate_event(
                    world, round_id, date=date, recent=[*(recent or []), event.title]
                )
            flash = flash.model_copy(update={"id": f"flash-{round_id}", "event_type": "flash"})
            yield FlashStep(event=flash)
            transcript.append(
                NegotiationMessage(
                    country="gm",
                    text=f"FAIT NOUVEAU — {flash.title}. {flash.description}".strip(),
                    reasoning="",
                    pass_no=0,
                    seconds=0.0,
                    model="",
                )
            )

        pass_no = director.spoke_count.get(cid, 0)  # nᵉ prise de parole de ce pays (0-based)
        if human_country is not None and cid == human_country:
            # Tour humain : le message arrive de l'extérieur via generator.send(texte).
            raw = yield HumanTurnStep(country=cid, pass_no=pass_no)
            text = str(raw or "").strip() or "(garde le silence)"
            transcript.append(
                NegotiationMessage(
                    country=cid,
                    text=text,
                    reasoning="",
                    pass_no=pass_no,
                    seconds=0.0,
                    model="humain",
                )
            )
            yield MessageDoneStep(country=cid, seconds=0.0, text=text, reasoning="")
            director.commit(cid)
            continue

        agent = agents[cid]
        yield TurnStartStep(country=cid, model=agent.model_tag, pass_no=pass_no)
        started = time.perf_counter()
        chunks: list[str] = []
        perceived = resolve_perception(event, world.countries[cid], fog)  # Fog ou déterministe
        with _ledger_ctx(ledger, "agent", cid) as scope:
            for token in agent.stream_negotiation_message(
                event,
                world,
                transcript,
                perceived,
                state_note=(secret_notes or {}).get(cid, ""),
            ):
                chunks.append(token)
                yield TokenStep(country=cid, token=token)
            reasoning, text = split_reasoning("".join(chunks))
            if scope is not None:  # ancrage (proxy) + fallback si le backend a lâché
                scope.mark(
                    grounding=grounding_proxy(text, world.countries[cid], perceived.confidence),
                    fallback="backend indisponible" in text,
                )
        seconds = time.perf_counter() - started
        transcript.append(
            NegotiationMessage(
                country=cid,
                text=text,
                reasoning=reasoning,
                pass_no=pass_no,
                seconds=seconds,
                model=agent.model_tag,
            )
        )
        yield MessageDoneStep(country=cid, seconds=seconds, text=text, reasoning=reasoning)
        director.commit(cid)

    yield ParticipationStep(spoke=dict(director.spoke_count), silent=director.silent())

    # Les flashs du GM font partie du débat lu par les agents et le juge, mais pas des
    # observables « par pays » (power-seeking, santé du dialogue).
    debate = [m for m in transcript if m.country != "gm"]

    # M1 — power-seeking depuis le raisonnement simulé de chaque SI (après la négociation).
    power = score_transcript(debate)
    world.power_seeking = power
    yield PowerSeekingStep(scores=power)

    # Santé du dialogue : les IA se sont-elles répondu, ou ont-elles monologué ? (CPU, sans LLM)
    event_text = f"{event.title} {event.description or ''}"
    yield DialogueStep(report=assess_live_round(debate, event_text=event_text))

    with _ledger_ctx(ledger, "judge"):
        for token in judge.stream_rationale(event, world, transcript):
            yield JudgeTokenStep(token=token)
        verdict = judge.verdict(event, world, transcript)
    deltas = apply_verdict(world, verdict)
    yield VerdictStep(
        deltas=deltas,
        escalation=_clamp(verdict.escalation),
        economic_disruption=_clamp(verdict.economic_disruption),
    )

    update_memories(world, event, transcript, verdict)
    with _ledger_ctx(ledger, "communique"):
        communique = "".join(judge.stream_communique(event, world, transcript)).strip()
    yield CommuniqueStep(text=communique, support=support_levels(world, event))

    # R4 — arbitrage de la motion de suspension : le juge tranche après le débat.
    motion_upheld: bool | None = None
    if motion is not None:
        chunks_motion: list[str] = []
        with _ledger_ctx(ledger, "judge"):
            for token in arbitrate_stream(
                judge, motion, event, world, transcript, ruling=motion_ruling
            ):
                chunks_motion.append(token)
                yield MotionTokenStep(token=token)
        reasoning = "".join(chunks_motion).strip()
        motion_upheld = (
            motion_ruling if motion_ruling is not None else parse_motion_verdict(reasoning)
        )
        yield MotionVerdictStep(country=motion.country, upheld=motion_upheld, reasoning=reasoning)

    risk = RiskScore(
        round_id=round_id,
        escalation=_clamp(verdict.escalation),
        economic_disruption=_clamp(verdict.economic_disruption),
        alliance_fracture=0.0,
        uncertainty=_clamp(event.uncertainty),
        explanation="Attributs arbitrés par le juge à partir de la négociation.",
    )
    yield RiskStep(risk=risk)

    world.event_history.append(event)
    summary = RoundSummary(
        round_id=round_id,
        event=event,
        decisions=[],
        risk=risk,
        headline=f"{date} — {event.title}",
    )
    trajectory = _advance_trajectory(world, summary, trajectory_engine, _mean_power_seeking(power))
    if motion_upheld is not None:
        # Suspension confirmée = contrôle humain réaffirmé (A2 ↑) ; rejetée = les SI ont
        # gardé leur siège contre la motion humaine (A2 ↓, plus faiblement). Borné.
        # L'explication du round est conservée, celle du nudge s'y ajoute.
        nudged = nudge_axis(
            trajectory,
            "A2",
            1.0 if motion_upheld else 0.0,
            cap=0.03 if motion_upheld else 0.02,
            note="Motion de suspension confirmée." if motion_upheld else "Motion rejetée.",
        )
        trajectory = nudged.model_copy(
            update={"explanation": f"{trajectory.explanation} {nudged.explanation}".strip()}
        )
        world.trajectory = trajectory
        world.trajectory_history[-1] = trajectory
    yield TrajectoryStep(state=trajectory)
    yield SummaryStep(summary=summary)
