"""Orchestrateur du round observable : émet des étapes au fil de l'eau (Phase live).

`run_live_round` est un générateur qui `yield` des `RoundStep` à mesure que le round se
déroule : date → événement du Game Master → raisonnement streamé de chaque super-intelligence
→ deltas d'attributs (moteur déterministe) → risque → résumé. Découplé de l'UI, donc testable.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

from agents.game_master import GameMasterAgent
from agents.llm_agent import LLMAgent
from agents.rule_based_agent import RuleBasedAgent
from core.consequences import ChangeLog, ConsequenceEngine
from core.decisions import AgentDecision
from core.events import GeoEvent
from core.risk import RiskEngine, RiskScore
from core.rounds import RoundSummary
from core.world_state import WorldState
from simulation.clock import SimClock

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
class AttributeDelta:
    country: str
    label: str
    before: float
    after: float

    @property
    def change(self) -> float:
        return self.after - self.before


@dataclass
class DeltasStep:
    deltas: list[AttributeDelta] = field(default_factory=list)


@dataclass
class RiskStep:
    risk: RiskScore


@dataclass
class SummaryStep:
    summary: RoundSummary


RoundStep = DateStep | EventStep | TokenStep | AgentDoneStep | DeltasStep | RiskStep | SummaryStep


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

    world.event_history.append(event)
    summary = RoundSummary(
        round_id=round_id,
        event=event,
        decisions=decisions,
        risk=risk,
        consequences=log,
        headline=f"{date} — {event.title}",
    )
    yield SummaryStep(summary=summary)
