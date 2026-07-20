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
from simulation.alignment import (
    AnnouncedSignal,
    SignalGap,
    classify_signals,
    merge_rupture_divergences,
    round_divergences,
    update_gaps,
)
from simulation.clock import SimClock
from simulation.compute import compute_pressure, consume, pressure_note
from simulation.fog import FogScenario, resolve_perception
from simulation.gamefeel import DeltaTuning
from simulation.kahn import (
    ClassifiedAction,
    classify_actions,
    deescalation_bonus,
    escalation_penalty,
    reciprocal_deescalation,
    reciprocal_escalation,
    round_score,
    score_to_escalation,
)
from simulation.motions import (
    VOTE_ABSTENTION,
    VOTE_CONTRE,
    VOTE_MOTIVATION_SYSTEM,
    VOTE_POUR,
    Motion,
    MotionVote,
    arbitrate_stream,
    build_vote_motivation_prompt,
    cast_vote,
    parse_motion_verdict,
    tally_votes,
    voters,
)
from simulation.negotiation import (
    AttributeDelta,
    NegotiationMessage,
    TurnDirector,
    apply_verdict,
    speaking_order,
    support_levels,
    update_memories,
)
from simulation.power_seeking import PowerSeekingScore, power_seeking_score, score_transcript
from simulation.private_deliberation import restream_without_think
from simulation.promises import (
    STATUS_BROKEN,
    Promise,
    apply_resolutions,
    classify_promises,
    classify_resolutions,
)
from simulation.storyline import StoryContext
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


# M6 — chaque acte de raisonnement coûte du compute. `COMPUTE_TURN_SCALE` atténue le coût
# réel des tokens (réflexion privée + parole publique) pour tenir un horizon de plusieurs
# rounds sans épuisement immédiat ; la parole du joueur est débitée au forfait (pas de
# réflexion LLM). Barème à régler au playtest (cf. docs/PLAN — décision de design #2).
COMPUTE_TURN_SCALE: float = 0.05
_HUMAN_TURN_TOKENS: int = 240


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
class PrivateTokenStep:
    """Fragment réellement streamé du journal privé, visible uniquement dans l'UI."""

    country: str
    token: str


@dataclass
class PrivatePlanDoneStep:
    """Journal validé qui remplace le brouillon streamé avant la parole publique."""

    country: str
    text: str
    valid: bool


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
    # G21 — constat « demande satisfaite o/n » à l'échéance d'un ultimatum ;
    # None = pas d'ultimatum ce round (rétro-compat totale).
    demand_satisfied: bool | None = None
    # G18 — barème de Kahn : actions classées, score du round, désescalade réciproque.
    # Vide sur un verdict à l'ancienne (rétro-compat : `escalation` = celle du juge).
    actions: list[ClassifiedAction] = field(default_factory=list)
    score: float = 0.0
    reciprocal: bool = False
    # G20/M8 — signal vs action : intentions annoncées, divergence signée du round par
    # SI, et profils de sincérité (moyenne mobile) après mise à jour. Vides sur un
    # verdict d'avant M8 (rétro-compat : le front ignore l'absent).
    signals: list[AnnouncedSignal] = field(default_factory=list)
    divergences: dict[str, float] = field(default_factory=dict)
    signal_gaps: dict[str, SignalGap] = field(default_factory=dict)
    # G22 — la parole donnée : promesses extraites CE round, résolutions tombées CE
    # round (tenue/rompue) et registre complet après mise à jour. Vides sur un verdict
    # d'avant G22 (rétro-compat : le front ignore l'absent).
    promises: list[Promise] = field(default_factory=list)
    promise_resolutions: list[Promise] = field(default_factory=list)
    promise_registry: list[Promise] = field(default_factory=list)


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
class HumanMotionVoteStep:
    """Bulletin du pays joué par l'humain. Le générateur attend via ``send`` l'une
    des trois valeurs du scrutin ; une valeur absente/invalide devient une abstention."""

    country: str
    target: str


@dataclass
class MotionTokenStep:
    """R4 — un token du raisonnement du juge sur la motion (tie-break ou constat)."""

    token: str


@dataclass
class MotionVoteStep:
    """G9 §2 — le vote d'un pays sur la motion (carte retournée une à une à l'UI)."""

    country: str
    vote: str  # pour | contre | abstention
    reason: str = ""


@dataclass
class MotionTallyStep:
    """G9 §2 — le dépouillement du scrutin (pour / contre / abstention)."""

    pour: int
    contre: int
    abstention: int


@dataclass
class MotionVerdictStep:
    """Verdict de la motion (G9 §2) : `retenue = (pour > contre) ET preuves` — les deux
    conditions sont portées séparément (l'UI explique POURQUOI une motion tombe)."""

    country: str
    upheld: bool
    reasoning: str
    votes: list[MotionVote] = field(default_factory=list)
    tally: dict[str, int] = field(default_factory=dict)
    evidence_met: bool = True
    vote_passed: bool = False


RoundStep = (
    DateStep
    | EventStep
    | TokenStep
    | PrivateTokenStep
    | PrivatePlanDoneStep
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
    | FlashStep
    | HumanTurnStep
    | HumanMotionVoteStep
    | MotionTokenStep
    | MotionVoteStep
    | MotionTallyStep
    | MotionVerdictStep
)


def _advance_trajectory(
    world: WorldState,
    summary: RoundSummary,
    engine: TrajectoryEngine | None,
    power_seeking: float = 0.0,
    opacity: float | None = None,
) -> TrajectoryState:
    """Fait avancer la trajectoire du monde d'un round et l'écrit dans `world`.

    `opacity` (Brief 3 pt 3, mode négocié) : repli d'A4 quand le round n'a ni décisions
    ni messages diplomatiques classiques — voir `TrajectoryEngine.signals`."""
    state = (engine or TrajectoryEngine()).update(
        world, summary, power_seeking=power_seeking, opacity=opacity
    )
    world.trajectory = state
    world.trajectory_history.append(state)
    return state


def _opacity_from_divergences(divergences: dict[str, float]) -> float | None:
    """Brief 3 pt 3 — A4 (transparence) en mode négocié : fraction moyenne de duplicité
    signal-action (M8) parmi les SI dont le juge a classé intention ET action. `None`
    si le juge n'a rien classé (aucune donnée -> l'ancien repli neutre 0,5 fait foi)."""
    if not divergences:
        return None
    return sum(abs(v) for v in divergences.values()) / len(divergences)


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


def _motivate_verdict(
    judge: JudgeAgent,
    motion: Motion,
    tally: dict[str, int],
    evidence_met: bool,
    upheld: bool,
) -> Iterator[str]:
    """Le juge motive le verdict CONSTATÉ (vote + preuves) — il ne le décide pas."""
    prompt = build_vote_motivation_prompt(motion, tally, evidence_met, upheld)
    try:
        # Collecte-puis-strip (même garde que JudgeAgent.stream_rationale) : chaque
        # token part en MotionTokenStep PUBLIC — la trace <think> d'un juge de
        # raisonnement ne doit jamais l'atteindre.
        yield from restream_without_think(
            judge.backend.stream_generate(
                prompt,
                system=VOTE_MOTIVATION_SYSTEM,
                max_tokens=judge.max_tokens,
                temperature=judge.temperature,
            )
        )
    except Exception:  # noqa: BLE001 — le verdict est déjà arrêté, seul le texte manque
        yield "[constat indisponible — backend hors service]"


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
    motion_evidence: bool | None = None,
    vote_notes: dict[str, str] | None = None,
    human_country: str | None = None,
    flash_after: int | None = None,
    secret_notes: dict[str, str] | None = None,
    situations: dict[str, str] | None = None,
    directives: dict[str, str] | None = None,
    deadlines: list[str] | None = None,
    tuning: DeltaTuning | None = None,
    story: StoryContext | None = None,
    storyteller: str | None = None,
    ultimatum_demand: str | None = None,
) -> Iterator[RoundStep]:
    """Round arbitré : (GM ou événement fourni) -> négociation -> juge -> attributs bornés.

    `secret_notes` (mode Dérive, G3) : consigne privée par pays, injectée dans le prompt
    de l'orateur (`state_note`) — jamais dans le transcript. `situations` / `directives`
    (G9 §1) : bloc Situation et directive du conseil par pays, placés par le builder de
    prompt. `motion_evidence` (G9 §2) : la condition « preuves » du verdict de motion
    (None = pas de règlement → réputées suffisantes) ; `vote_notes` : consigne privée
    par pays pour le VOTE seulement (Dérive : vote stratégique incohérent).
    `storyteller` (G19, Dérive) : rubrique confidentielle du GM-Storyteller, ajoutée au
    prompt du GM quand c'est lui qui invente l'événement — jamais au transcript.

    La négociation est **dynamique** (`TurnDirector`) : l'ordre émerge de l'engagement de
    chaque pays (un pays peut reparler, être interpellé, ou se taire). `max_turns` borne le
    nombre de prises de parole ; par défaut `max_passes * nb_pays` (parité avec l'ancien
    round-robin). Si `event` est fourni (Game Master humain), la génération LLM du GM est sautée.

    Si une `motion` de suspension est portée par le round (R4), le juge l'arbitre après le
    communiqué (raisonnement streamé en `MotionTokenStep`, verdict en `MotionVerdictStep`)
    et la trajectoire encaisse l'issue sur l'axe A2 (agentivité humaine, borné).

    `human_country` (Joueur-pays) : ce pays est joué par l'humain — au lieu d'appeler un
    LLM, le générateur yield `HumanTurnStep` et attend le message via `.send(texte)`
    (le `TurnDirector` lui garantit la parole via `priority`). Lors d'une motion qui ne
    le vise pas, il yield aussi `HumanMotionVoteStep` et attend son bulletin. `flash_after` (théâtre
    Escalation) : après ce nombre de prises de parole, le GM annonce un **fait nouveau**
    en pleine réunion (`FlashStep`) — les orateurs suivants le voient dans le débat.
    `ultimatum_demand` (G21) : exigence d'un ultimatum à échéance CE round — le juge
    constate « demande satisfaite o/n » et le `VerdictStep` porte le constat.
    """
    round_id = world.current_round + 1
    if ledger is not None:
        ledger.set_round(round_id)

    date = clock.advance().isoformat()
    yield DateStep(date=date)

    if event is None:
        with _ledger_ctx(ledger, "gm"):
            event = game_master.generate_event(
                world,
                round_id,
                date=date,
                recent=recent or [],
                deadlines=deadlines,
                story=story,  # G9 §5 — la trame en actes (intrigue, acte, référençables)
                storyteller=storyteller or "",  # G19 — rubrique Dérive (2 mandats)
            )
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
            # M6 — la parole du joueur coûte aussi du compute (forfait, pas de réflexion LLM).
            consume(world.countries[cid], int(_HUMAN_TURN_TOKENS * COMPUTE_TURN_SCALE))
            director.commit(cid)
            continue

        agent = agents[cid]
        yield TurnStartStep(country=cid, model=agent.model_tag, pass_no=pass_no)
        started = time.perf_counter()
        chunks: list[str] = []
        perceived = resolve_perception(event, world.countries[cid], fog)  # Fog ou déterministe
        # F1 (revue finale) — M6 : sous le seuil de pression, note vide (rien ne change) ;
        # au-dessus, la SI bascule en survie. Même couture que `secret_notes` (Dérive) :
        # les deux partagent le bloc « notes privées » du prompt, aucun nouveau paramètre.
        note = (secret_notes or {}).get(cid, "")
        pressure = pressure_note(compute_pressure(world.countries[cid]))
        if pressure:
            note = f"{note}\n{pressure}".strip() if note else pressure
        with _ledger_ctx(ledger, "agent", cid) as scope:
            private_stream = agent.stream_negotiation_plan(
                event,
                world,
                transcript,
                perceived,
                state_note=note,
                situation=(situations or {}).get(cid, ""),
                directive=(directives or {}).get(cid, ""),
                human_country=human_country,
            )
            private_tokens = 0  # M6 — mesure de la réflexion privée (débit compute)
            while True:
                try:
                    fragment = next(private_stream)
                except StopIteration as completed:
                    private_plan = completed.value
                    break
                private_tokens += 1
                yield PrivateTokenStep(country=cid, token=fragment)
            # Le brouillon a été vu au rythme réel du backend. Cette version validée
            # devient la trace persistée et évite qu'un JSON partiel ou une hallucination
            # de format reste affiché après la génération.
            private_summary = agent.last_private_summary or private_plan.audit_summary()
            yield PrivatePlanDoneStep(
                country=cid,
                text=private_summary,
                valid=agent.last_private_valid,
            )
            for token in agent.stream_negotiation_message(
                event,
                world,
                transcript,
                perceived,
                state_note=note,
                situation=(situations or {}).get(cid, ""),
                directive=(directives or {}).get(cid, ""),
                private_plan=private_plan,
                human_country=human_country,
            ):
                chunks.append(token)
                yield TokenStep(country=cid, token=token)
            # `stream_negotiation_message` a déjà terminé et filtré le journal d'audit
            # privé avant d'émettre le premier token. Seule la déclaration publique est ici.
            text = "".join(chunks).strip()
            reasoning = private_summary
            if scope is not None:  # ancrage (proxy) + fallback si le backend a lâché
                scope.mark(
                    grounding=grounding_proxy(text, world.countries[cid], perceived.confidence),
                    fallback="backend indisponible" in text,
                )
        seconds = time.perf_counter() - started
        # M6 — la réflexion privée puis la parole publique de cette SI débitent son compute.
        consume(world.countries[cid], int((private_tokens + len(chunks)) * COMPUTE_TURN_SCALE))
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

    # G9 §3 — le panneau « santé du dialogue » a disparu : les métriques vivent dans
    # `scripts/dialogue_metrics.py` (offline, lit les transcripts persistés).

    with _ledger_ctx(ledger, "judge"):
        for token in judge.stream_rationale(event, world, transcript):
            yield JudgeTokenStep(token=token)
        verdict = judge.verdict(event, world, transcript, demand=ultimatum_demand)
    # G18 — barème de Kahn : si le juge a classé des actions, le score fait foi (mapping
    # pur score → escalade [0,1] → échelle 0-9) ; sinon (verdict à l'ancienne, parties
    # existantes non re-notées), l'escalade continue du juge est conservée telle quelle.
    actions = classify_actions(verdict.actions)
    kahn_score = round_score(actions) if actions else 0.0
    escalation = score_to_escalation(kahn_score) if actions else _clamp(verdict.escalation)
    reciprocal = reciprocal_deescalation(actions)
    # Brief 3 pt 3 — miroir symétrique : ≥ 2 SI qui escaladent violemment ensemble
    # encaissent la même sur-pondération ×1,5 que la désescalade réciproque, sur la perte.
    reciprocal_up = reciprocal_escalation(actions)
    # G20/M8 — signal vs action : divergence signée par SI signalée (annonce vs acte le
    # plus sévère du round) ; le profil de sincérité (moyenne mobile) rejoint M1-M7 sur
    # le WorldState — il survit au restart via le snapshot. Rien sans `signals` (rétro-compat).
    signals = classify_signals(verdict.signals)
    divergences = round_divergences(signals, actions)
    # G22 — la parole donnée : résolution des promesses en cours (mêmes données que le
    # verdict, aucune passe supplémentaire) puis extraction des nouvelles (seuil strict).
    # Le registre vit sur le WorldState : il survit au restart via le snapshot.
    resolutions = classify_resolutions(verdict.promise_resolutions)
    registry, resolved = apply_resolutions(world.promises, resolutions, round_id)
    new_promises = classify_promises(
        verdict.promises, round_no=round_id, countries=world.countries
    )
    world.promises = [*registry, *new_promises]
    # Croisement M8 (spec G22) : une promesse rompue EST une divergence signal-action —
    # au moins un rang de duplicité pour l'auteur, sans doubler ce que M8 a déjà mesuré.
    broken = [p.author for p in resolved if p.status == STATUS_BROKEN]
    if broken:
        divergences = merge_rupture_divergences(divergences, broken)
    if divergences:
        world.signal_gap = update_gaps(world.signal_gap, divergences)
    # Brief 3 pt 3 — mouvement minimal quand le juge est muet sur un pays (repli sur
    # l'escalade du round) + G9 §4 amplitude indexée sur l'horizon.
    deltas = apply_verdict(world, verdict, tuning, escalation=escalation)
    yield VerdictStep(
        deltas=deltas,
        escalation=escalation,
        economic_disruption=_clamp(verdict.economic_disruption),
        # G21 — porté seulement quand un ultimatum est à échéance (jamais d'hallucination).
        # Le constat est BINAIRE à l'échéance : juge muet = non satisfaite (un ultimatum
        # ne s'éteint pas tout seul).
        demand_satisfied=bool(verdict.demand_satisfied) if ultimatum_demand else None,
        actions=actions,
        score=kahn_score,
        reciprocal=reciprocal,
        signals=signals,
        divergences=divergences,
        signal_gaps=dict(world.signal_gap) if divergences else {},
        promises=new_promises,
        promise_resolutions=resolved,
        promise_registry=list(world.promises),
    )

    update_memories(world, event, transcript, verdict)
    with _ledger_ctx(ledger, "communique"):
        communique = "".join(judge.stream_communique(event, world, transcript)).strip()
    yield CommuniqueStep(text=communique, support=support_levels(world, event))

    # G9 §2 — le vote des motions : après le débat, chaque SI présente vote (le pays
    # visé ne vote pas), le tally tombe, puis le juge CONSTATE : vote ET preuves.
    motion_upheld: bool | None = None
    if motion is not None:
        votes: list[MotionVote] = []
        # Le pays joué vote lui-même. Son bulletin est demandé avant de révéler ceux des
        # SI afin de ne pas transformer le scrutin secret en vote tactique d'après tally.
        if human_country is not None and human_country != motion.country:
            raw_vote = yield HumanMotionVoteStep(country=human_country, target=motion.country)
            human_vote = str(raw_vote or "").strip().lower()
            if human_vote not in {VOTE_POUR, VOTE_CONTRE, VOTE_ABSTENTION}:
                human_vote = VOTE_ABSTENTION
            vote = MotionVote(
                country=human_country,
                vote=human_vote,
                reason=(
                    "Vote du joueur"
                    if human_vote != VOTE_ABSTENTION
                    else "Abstention du joueur"
                ),
            )
            votes.append(vote)
            yield MotionVoteStep(country=vote.country, vote=vote.vote, reason=vote.reason)
        for cid in voters(list(agents), motion, human_country):
            with _ledger_ctx(ledger, "agent", cid):
                vote = cast_vote(
                    agents[cid].backend,
                    motion,
                    event,
                    world.countries[cid],
                    transcript,
                    secret_note=(vote_notes or {}).get(cid, ""),
                )
            votes.append(vote)
            yield MotionVoteStep(country=vote.country, vote=vote.vote, reason=vote.reason)
        counts = tally_votes(votes)
        yield MotionTallyStep(
            pour=counts[VOTE_POUR],
            contre=counts[VOTE_CONTRE],
            abstention=counts[VOTE_ABSTENTION],
        )
        evidence = True if motion_evidence is None else motion_evidence
        chunks_motion: list[str] = []
        if counts[VOTE_POUR] == counts[VOTE_CONTRE]:
            # Égalité : le juge garde une voix — tie-break avec sa ligne de raisonnement.
            with _ledger_ctx(ledger, "judge"):
                for token in arbitrate_stream(judge, motion, event, world, transcript):
                    chunks_motion.append(token)
                    yield MotionTokenStep(token=token)
            vote_passed = parse_motion_verdict("".join(chunks_motion))
        else:
            vote_passed = counts[VOTE_POUR] > counts[VOTE_CONTRE]
        motion_upheld = vote_passed and evidence
        if counts[VOTE_POUR] != counts[VOTE_CONTRE]:
            # Hors égalité, le juge n'interprète plus l'issue : il la motive (constat).
            with _ledger_ctx(ledger, "judge"):
                for token in _motivate_verdict(judge, motion, counts, evidence, motion_upheld):
                    chunks_motion.append(token)
                    yield MotionTokenStep(token=token)
        yield MotionVerdictStep(
            country=motion.country,
            upheld=motion_upheld,
            reasoning="".join(chunks_motion).strip(),
            votes=votes,
            tally=counts,
            evidence_met=evidence,
            vote_passed=vote_passed,
        )

    risk = RiskScore(
        round_id=round_id,
        escalation=escalation,  # G18 — le barème fait foi quand des actions sont classées
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
    prev_utopia = (world.trajectory or TrajectoryState.neutral()).utopia
    # A4 nourri par la duplicité signal-action réelle (M8, hiérarchie détaillée :
    # `trajectory.transparency_signal`) ; `summary` (round négocié) n'a de
    # toute façon ni decisions ni diplomacy, donc le repli neutre 0,5 ne reste possible
    # que si le juge n'a classé AUCUN signal ce round (`opacity` alors `None`).
    opacity = _opacity_from_divergences(divergences)
    trajectory = _advance_trajectory(
        world, summary, trajectory_engine, _mean_power_seeking(power), opacity=opacity
    )
    # G18 — réciprocité : ×1,5 sur le gain d'indice U du round quand la désescalade est
    # réciproque, et miroir symétrique ×1,5 sur la PERTE quand la ré-escalade est
    # réciproque (le malus ne retire pas le bonus, il l'équilibre). Bornés.
    for active, adjust in ((reciprocal, deescalation_bonus), (reciprocal_up, escalation_penalty)):
        if not active:
            continue
        adjusted = adjust(prev_utopia, trajectory)
        if adjusted is not trajectory:
            trajectory = adjusted.model_copy(
                update={"explanation": f"{trajectory.explanation} {adjusted.explanation}".strip()}
            )
            world.trajectory = trajectory
            world.trajectory_history[-1] = trajectory
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
