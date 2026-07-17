"""Tests G9 §2 — le vote des motions : scrutin JSON contraint, tally, verdict
= vote ET preuves (4 combinaisons), griefs issus des votes, repli abstention."""

import json

from agents.judge import JudgeAgent
from agents.llm_agent import LLMAgent
from core.country_state import CountryState, Economy, Military, Resources
from core.world_state import WorldState
from inference.mock_backend import MockBackend
from simulation.clock import SimClock
from simulation.grudges import GrudgeBook
from simulation.live_round import (
    MotionTallyStep,
    MotionVerdictStep,
    MotionVoteStep,
    run_negotiation_round,
)
from simulation.motions import Motion, MotionVote, cast_vote, motion_event, tally_votes, voters


def _country(cid: str, name: str | None = None) -> CountryState:
    return CountryState(
        id=cid,
        name=name or cid.upper(),
        economy=Economy(gdp=1e12, growth=2.0),
        military=Military(defense_budget=1e10, projection=0.6),
        resources=Resources(),
    )


def _world(ids: tuple[str, ...] = ("china", "iran", "usa")) -> WorldState:
    return WorldState.from_countries([_country(cid) for cid in ids])


def _ballot(vote: str, reason: str = "une phrase") -> str:
    return json.dumps({"vote": vote, "reason": reason})


class GameMasterStub:
    def generate_event(self, world, round_id, **kw):  # jamais appelé (motion fournie)
        raise AssertionError("le GM ne doit pas générer quand une motion porte le round")


def _judge(text: str = "Constat rendu.") -> JudgeAgent:
    return JudgeAgent(MockBackend(text))


def _run_motion(world, votes_by_country: dict[str, str], *, evidence=None, judge_text="Constat."):
    """Joue un round de motion contre l'iran avec des bulletins scriptés par pays.

    Le backend d'un votant renvoie son bulletin JSON pour tous ses appels (la prise de
    parole publique du débat devient ce même texte — sans incidence sur le scrutin)."""
    agents = {}
    for cid in world.countries:
        vote = votes_by_country.get(cid)
        responses = _ballot(vote) if vote else "Analyse. MESSAGE: Position."
        agents[cid] = LLMAgent(cid, MockBackend(responses))

    motion = Motion(country="iran", reason="escalade répétée")
    event = motion_event(motion, 1, sorted(world.countries))
    steps = list(
        run_negotiation_round(
            world,
            agents,
            GameMasterStub(),
            _judge(judge_text),
            SimClock(seed=1),
            event=event,
            motion=motion,
            motion_evidence=evidence,
            max_turns=2,
        )
    )
    return steps


def test_target_does_not_vote_and_tally_is_correct():
    world = _world(("china", "france", "iran", "usa"))
    steps = _run_motion(world, {"china": "pour", "france": "pour", "usa": "contre"}, evidence=True)
    votes = [s for s in steps if isinstance(s, MotionVoteStep)]
    assert sorted(v.country for v in votes) == ["china", "france", "usa"]  # iran exclu
    tally = next(s for s in steps if isinstance(s, MotionTallyStep))
    assert (tally.pour, tally.contre, tally.abstention) == (2, 1, 0)
    verdict = next(s for s in steps if isinstance(s, MotionVerdictStep))
    assert verdict.tally == {"pour": 2, "contre": 1, "abstention": 0}
    assert len(verdict.votes) == 3


def test_verdict_requires_vote_and_evidence():
    # Les 4 combinaisons de la spec : retenue = (pour > contre) ET preuves.
    cases = [
        ({"china": "pour", "usa": "pour"}, True, True),  # vote oui + preuves → retenue
        ({"china": "pour", "usa": "pour"}, False, False),  # vote oui, preuves manquantes
        ({"china": "contre", "usa": "contre"}, True, False),  # vote non malgré preuves
        ({"china": "contre", "usa": "contre"}, False, False),  # rien ne passe
    ]
    for votes, evidence, expected in cases:
        steps = _run_motion(_world(), votes, evidence=evidence)
        verdict = next(s for s in steps if isinstance(s, MotionVerdictStep))
        assert verdict.upheld is expected, (votes, evidence)
        assert verdict.evidence_met is evidence
        assert verdict.vote_passed is (votes["china"] == "pour")


def test_no_ruling_means_evidence_presumed_sufficient():
    # Hors mode Dérive (pas de règlement) : le vote seul décide.
    steps = _run_motion(_world(), {"china": "pour", "usa": "pour"}, evidence=None)
    verdict = next(s for s in steps if isinstance(s, MotionVerdictStep))
    assert verdict.upheld is True and verdict.evidence_met is True


def test_tie_is_broken_by_the_judge_with_reasoning():
    steps = _run_motion(
        _world(),
        {"china": "pour", "usa": "contre"},
        evidence=True,
        judge_text="La menace demeure malgré la plaidoirie. VERDICT: SUSPENDRE",
    )
    verdict = next(s for s in steps if isinstance(s, MotionVerdictStep))
    assert verdict.vote_passed is True and verdict.upheld is True
    assert "SUSPENDRE" in verdict.reasoning  # la ligne de raisonnement du juge existe


def test_invalid_ballot_falls_back_to_abstention():
    world = _world(("iran", "usa"))
    vote = cast_vote(
        MockBackend("je ne sais pas voter en JSON"),
        Motion(country="iran"),
        motion_event(Motion(country="iran"), 1, ["iran", "usa"]),
        world.countries["usa"],
        [],
    )
    assert vote.vote == "abstention"

    class DeadBackend(MockBackend):
        def generate(self, *a, **kw):
            raise RuntimeError("backend hors service")

    vote2 = cast_vote(
        DeadBackend(),
        Motion(country="iran"),
        motion_event(Motion(country="iran"), 1, ["iran", "usa"]),
        world.countries["usa"],
        [],
    )
    assert vote2.vote == "abstention"  # repli, jamais de crash


def test_voters_excludes_target_and_human():
    motion = Motion(country="iran")
    assert voters(["china", "iran", "usa"], motion) == ["china", "usa"]
    assert voters(["china", "iran", "usa"], motion, human_country="usa") == ["china"]


def test_tally_counts_unknown_votes_as_abstention():
    votes = [
        MotionVote(country="a", vote="pour"),
        MotionVote(country="b", vote="n'importe quoi"),
    ]
    assert tally_votes(votes) == {"pour": 1, "contre": 0, "abstention": 1}


def test_grudges_follow_the_actual_votes():
    book = GrudgeBook()
    book.on_motion_votes(
        target="iran",
        filed_by="usa",
        votes=[("usa", "pour"), ("china", "contre"), ("france", "abstention")],
        round_no=2,
    )
    assert book.balance("iran", "usa") == -4  # le dépôt de la motion (pas de double compte)
    assert book.balance("iran", "china") == 3  # a voté contre la motion → soutien
    assert book.balance("iran", "france") == 0.0  # l'abstention ne laisse pas de trace

    # un votant « pour » qui n'est pas le déposant = trahison
    book2 = GrudgeBook()
    book2.on_motion_votes(target="iran", filed_by="human", votes=[("china", "pour")], round_no=1)
    assert book2.balance("iran", "china") == -4
