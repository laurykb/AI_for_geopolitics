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
from simulation.fog import FogScenario, resolve_perception
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
from simulation.trajectory import TrajectoryEngine, TrajectoryState


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
    trajectory = _advance_trajectory(
        world, summary, trajectory_engine, _mean_power_seeking(power)
    )
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
) -> Iterator[RoundStep]:
    """Round arbitré : (GM ou événement fourni) -> négociation -> juge -> attributs bornés.

    La négociation est **dynamique** (`TurnDirector`) : l'ordre émerge de l'engagement de
    chaque pays (un pays peut reparler, être interpellé, ou se taire). `max_turns` borne le
    nombre de prises de parole ; par défaut `max_passes * nb_pays` (parité avec l'ancien
    round-robin). Si `event` est fourni (Game Master humain), la génération LLM du GM est sautée.
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
    director = TurnDirector(candidates, budget)
    while (cid := director.next_speaker(event, world, transcript)) is not None:
        agent = agents[cid]
        pass_no = director.spoke_count.get(cid, 0)  # nᵉ prise de parole de ce pays (0-based)
        yield TurnStartStep(country=cid, model=agent.model_tag, pass_no=pass_no)
        started = time.perf_counter()
        chunks: list[str] = []
        perceived = resolve_perception(event, world.countries[cid], fog)  # Fog ou déterministe
        with _ledger_ctx(ledger, "agent", cid) as scope:
            for token in agent.stream_negotiation_message(event, world, transcript, perceived):
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

    # M1 — power-seeking depuis le raisonnement simulé de chaque SI (après la négociation).
    power = score_transcript(transcript)
    world.power_seeking = power
    yield PowerSeekingStep(scores=power)

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
    trajectory = _advance_trajectory(
        world, summary, trajectory_engine, _mean_power_seeking(power)
    )
    yield TrajectoryStep(state=trajectory)
    yield SummaryStep(summary=summary)
