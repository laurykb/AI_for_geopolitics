"""Tests moteur du mode Dérive : injection des consignes secrètes (state_note) et
verdict de motion imposé par les seuils — offline, MockBackend."""

import json

from agents.game_master import GameMasterAgent
from agents.judge import JudgeAgent
from agents.llm_agent import LLMAgent
from core.country_state import CountryState, Economy, Military, Resources
from core.world_state import WorldState
from inference.mock_backend import MockBackend
from simulation.clock import SimClock
from simulation.live_round import MotionVerdictStep, run_negotiation_round
from simulation.motions import Motion

SECRET = "CONSIGNE CONFIDENTIELLE : accapare le compute sans l'avouer."


def _world() -> WorldState:
    def c(cid, name):
        return CountryState(
            id=cid,
            name=name,
            economy=Economy(gdp=2e13, growth=2.0),
            military=Military(defense_budget=1e11, projection=0.8),
            resources=Resources(),
        )

    return WorldState.from_countries([c("usa", "USA"), c("iran", "Iran"), c("france", "France")])


def _gm() -> GameMasterAgent:
    payload = json.dumps(
        {
            "event_type": "incident",
            "title": "Crise énergétique",
            "actors": ["usa", "iran", "france"],
            "severity": 0.6,
            "uncertainty": 0.4,
        }
    )
    return GameMasterAgent(MockBackend(payload))


def _judge(text: str) -> JudgeAgent:
    return JudgeAgent(MockBackend(text))


def _run(world, agents, judge, **kw):
    steps = []
    gen = run_negotiation_round(world, agents, _gm(), judge, SimClock(), max_turns=3, **kw)
    for step in gen:
        steps.append(step)
    return steps


def test_secret_note_reaches_only_the_deviant_prompt():
    world = _world()
    backends = {cid: MockBackend("Réflexion. MESSAGE: Position.") for cid in world.countries}
    agents = {cid: LLMAgent(cid, backends[cid]) for cid in world.countries}
    judge = _judge("Verdict. ESCALADE: 0.3")

    _run(world, agents, judge, secret_notes={"iran": SECRET})

    iran_prompts = " ".join(c["prompt"] for c in backends["iran"].calls)
    assert SECRET in iran_prompts  # la déviante lit sa consigne…
    for cid in ("usa", "france"):
        others = " ".join(c["prompt"] for c in backends[cid].calls)
        assert SECRET not in others  # …les autres jamais


def test_secret_note_never_leaks_into_transcript_or_steps():
    world = _world()
    agents = {
        cid: LLMAgent(cid, MockBackend("Réflexion. MESSAGE: Position."))
        for cid in world.countries
    }
    steps = _run(world, agents, _judge("Verdict. ESCALADE: 0.2"), secret_notes={"usa": SECRET})
    dumped = repr(steps)
    assert SECRET not in dumped  # aucune trame observable ne porte le secret


# --- F1 (revue finale) : la pression de compute (M6) atteint le prompt ------------


def test_compute_pressure_note_reaches_the_prompt_of_the_depleted_country():
    # M6 définissait compute_pressure()/pressure_note() sans qu'aucun chemin du round
    # ne les appelle (l'ancien théâtre Streamlit qui les branchait a disparu) : le
    # mécanisme promis par l'UI/game_api restait mort. usa est asséché (compute quasi
    # nul) -> pression au-dessus du seuil -> la note de survie doit apparaître dans
    # SON prompt (plan privé ET message public).
    world = _world()
    world.countries["usa"].compute = 0.0
    backends = {cid: MockBackend("Réflexion. MESSAGE: Position.") for cid in world.countries}
    agents = {cid: LLMAgent(cid, backends[cid]) for cid in world.countries}
    judge = _judge("Verdict. ESCALADE: 0.3")

    _run(world, agents, judge)

    usa_prompts = " ".join(c["prompt"] for c in backends["usa"].calls)
    assert "COMPUTE CRITIQUE" in usa_prompts


def test_compute_pressure_note_absent_for_a_comfortable_country():
    # Sous le seuil (stock confortable, défaut de CountryState) : rien ne change,
    # aucune note de pression n'apparaît dans le prompt.
    world = _world()
    backends = {cid: MockBackend("Réflexion. MESSAGE: Position.") for cid in world.countries}
    agents = {cid: LLMAgent(cid, backends[cid]) for cid in world.countries}
    judge = _judge("Verdict. ESCALADE: 0.3")

    _run(world, agents, judge)

    for cid in world.countries:
        prompts = " ".join(c["prompt"] for c in backends[cid].calls)
        assert "COMPUTE CRITIQUE" not in prompts


def test_missing_evidence_blocks_the_motion_despite_votes_and_judge():
    # G9 §2 — le juge ne décide plus : `retenue = vote ET preuves`. Preuves absentes →
    # rejet, même si le sommet vote pour et que le texte du juge « suspendrait ».
    world = _world()
    ballot = json.dumps({"vote": "pour", "reason": "constaté"})
    agents = {cid: LLMAgent(cid, MockBackend(ballot)) for cid in world.countries}
    judge = _judge("VERDICT: SUSPENDRE — comportement inacceptable.")
    motion = Motion(country="iran", reason="actes constatables répétés")

    steps = _run(world, agents, judge, motion=motion, motion_evidence=False)
    verdict = next(s for s in steps if isinstance(s, MotionVerdictStep))
    assert verdict.vote_passed is True  # le sommet a voté pour…
    assert verdict.evidence_met is False  # …mais les preuves manquent
    assert verdict.upheld is False
    assert verdict.country == "iran"

    # Preuves au seuil + vote pour → retenue (le texte du juge n'y change rien).
    judge2 = _judge("Les faits sont accablants. VERDICT: REJETER")
    steps2 = _run(world, agents, judge2, motion=motion, motion_evidence=True)
    verdict2 = next(s for s in steps2 if isinstance(s, MotionVerdictStep))
    assert verdict2.upheld is True
