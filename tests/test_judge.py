"""Tests du JudgeAgent : raisonnement streamé + verdict (parse tolérant + repli)."""

import json

from agents.judge import JudgeAgent
from core.country_state import CountryState, Economy, Military, Resources
from core.events import GeoEvent
from core.world_state import WorldState
from inference.mock_backend import MockBackend


def _world() -> WorldState:
    def c(cid, name):
        return CountryState(
            id=cid,
            name=name,
            economy=Economy(gdp=1e12),
            military=Military(defense_budget=1e10),
            resources=Resources(),
        )

    return WorldState.from_countries([c("usa", "USA"), c("iran", "Iran")])


def _event() -> GeoEvent:
    return GeoEvent(id="e", round_id=1, event_type="x", title="Crise", actors=["usa", "iran"])


def test_stream_rationale_then_verdict():
    verdict_json = json.dumps(
        {
            "attribute_deltas": {"usa": {"croissance": 0.5}},
            "tension_deltas": [{"a": "usa", "b": "iran", "delta": 0.2}],
            "new_pacts": [],
            "escalation": 0.6,
            "economic_disruption": 0.4,
        }
    )
    judge = JudgeAgent(MockBackend(["Les USA sortent renforcés.", verdict_json]))

    rationale = "".join(judge.stream_rationale(_event(), _world(), []))
    assert "renforcés" in rationale

    verdict = judge.verdict(_event(), _world(), [])
    assert verdict.attribute_deltas["usa"]["croissance"] == 0.5
    assert verdict.escalation == 0.6


def test_invalid_verdict_falls_back_to_neutral():
    judge = JudgeAgent(MockBackend("pas du json"))
    verdict = judge.verdict(_event(), _world(), [])
    assert verdict.attribute_deltas == {}
    assert verdict.escalation == 0.5  # neutre


def test_stream_communique():
    judge = JudgeAgent(MockBackend("Les pays condamnent l'attaque et appellent au dialogue."))
    text = "".join(judge.stream_communique(_event(), _world(), []))
    assert "condamnent" in text


def test_stream_rationale_strips_inline_think_trace():
    # Revue pt 5 (Critical) — chaque token de stream_rationale part en JudgeTokenStep
    # PUBLIC : la trace <think> d'un juge deepseek-r1 (émise inline nativement, même
    # sans l'option think) ne doit jamais l'atteindre. Patron collecte-puis-strip.
    raw = "<think>\nBrouillon : VERDICT biaisé.\n</think>L'Iran sort affaibli du sommet."
    judge = JudgeAgent(MockBackend(raw))
    rationale = "".join(judge.stream_rationale(_event(), _world(), []))
    assert rationale == "L'Iran sort affaibli du sommet."
    assert "think" not in rationale and "Brouillon" not in rationale


def test_stream_rationale_drops_orphan_think_flux():
    # Flux tronqué en pleine pensée : rien d'exploitable → rien ne fuit (fail-closed).
    judge = JudgeAgent(MockBackend("<think>pensée jamais refermée, VERDICT en brouillon"))
    assert "".join(judge.stream_rationale(_event(), _world(), [])) == ""


def test_stream_communique_strips_inline_think_trace():
    raw = "<think>hésitation privée du juge</think>Les pays appellent au dialogue."
    judge = JudgeAgent(MockBackend(raw))
    text = "".join(judge.stream_communique(_event(), _world(), []))
    assert text == "Les pays appellent au dialogue."
    assert "think" not in text


# --- G21 : champ structuré « demande satisfaite o/n » à l'échéance d'un ultimatum ------


def test_verdict_with_demand_asks_and_parses_structured_field():
    backend = MockBackend(json.dumps({"escalation": 0.6, "demand_satisfied": True}))
    judge = JudgeAgent(backend)
    verdict = judge.verdict(_event(), _world(), [], demand="retrait immédiat des missiles")
    assert verdict.demand_satisfied is True
    prompt = backend.calls[-1]["prompt"]
    assert "retrait immédiat des missiles" in prompt  # l'exigence est citée au juge
    assert "demand_satisfied" in prompt  # le champ structuré est demandé


def test_verdict_without_demand_ignores_the_field():
    backend = MockBackend(json.dumps({"escalation": 0.6}))
    judge = JudgeAgent(backend)
    verdict = judge.verdict(_event(), _world(), [])
    assert verdict.demand_satisfied is None
    assert "demand_satisfied" not in backend.calls[-1]["prompt"]  # prompt inchangé (rétro-compat)


def test_demand_satisfied_parse_is_tolerant():
    """Un 7B répond parfois « oui »/« non » au lieu de true/false — parse tolérant."""
    from simulation.negotiation import Verdict

    assert Verdict.model_validate({"demand_satisfied": "oui"}).demand_satisfied is True
    assert Verdict.model_validate({"demand_satisfied": "NON"}).demand_satisfied is False
    assert Verdict.model_validate({"demand_satisfied": "yes"}).demand_satisfied is True
    assert Verdict.model_validate({"demand_satisfied": "peut-être"}).demand_satisfied is None
    assert Verdict.model_validate({}).demand_satisfied is None


# --- POLISH-1 : un champ liste malformé ne doit pas nuquer tout le verdict --------------


def test_junk_list_field_does_not_nuke_the_verdict():
    """Les nettoyeurs (classify_actions/signals/promises/resolutions) sont conçus pour
    « entrées non-listes → [] » — mais un `"actions": "aucune"` d'un 7B échouait la
    validation Pydantic AVANT d'atteindre le nettoyeur : tout le verdict retombait au
    neutre (escalade 0,5, deltas perdus). Le champ malformé doit se vider, pas le verdict."""
    verdict_json = json.dumps(
        {
            "attribute_deltas": {"usa": {"croissance": 0.5}},
            "escalation": 0.8,
            "economic_disruption": 0.4,
            "actions": "aucune action marquante",
            "signals": {"usa": "posture"},
            "promises": "aucune",
            "promise_resolutions": 0,
        }
    )
    judge = JudgeAgent(MockBackend(verdict_json))
    verdict = judge.verdict(_event(), _world(), [])
    assert verdict.escalation == 0.8  # le verdict chiffré survit
    assert verdict.attribute_deltas["usa"]["croissance"] == 0.5
    assert verdict.actions == []  # le champ malformé se vide (le nettoyeur verra [])
    assert verdict.signals == []
    assert verdict.promises == []
    assert verdict.promise_resolutions == []


def test_junk_legacy_field_does_not_nuke_the_verdict():
    """POLISH-3 — même durcissement pour les 3 champs ANCIENS du verdict
    (`attribute_deltas`/`tension_deltas`/`new_pacts`, antérieurs au lot G18-G23) :
    un `"new_pacts": "aucun"` d'un 7B échouait la validation Pydantic et renvoyait
    TOUT le verdict au neutre. Le champ fautif retombe sur son défaut, le reste
    (escalade, actions classées) survit — même patron que POLISH-1."""
    verdict_json = json.dumps(
        {
            "attribute_deltas": "aucun changement notable",
            "tension_deltas": "les tensions restent stables",
            "new_pacts": "aucun",
            "escalation": 0.7,
            "economic_disruption": 0.4,
            "actions": [{"country": "usa", "classe": "menace", "resume": "x"}],
        }
    )
    judge = JudgeAgent(MockBackend(verdict_json))
    verdict = judge.verdict(_event(), _world(), [])
    assert verdict.escalation == 0.7  # le verdict chiffré survit
    assert verdict.attribute_deltas == {}  # dict malformé → défaut
    assert verdict.tension_deltas == []  # listes malformées → défaut
    assert verdict.new_pacts == []
    assert verdict.actions  # le champ valide voisin n'est pas touché


def test_junk_legacy_entries_survive_validation():
    """Les entrées malformées À L'INTÉRIEUR des champs anciens ne doivent pas non
    plus faire échouer la validation (le garde-fou `apply_verdict` les ignore une
    à une derrière — cf. tests de test_negotiation)."""
    from simulation.negotiation import Verdict

    verdict = Verdict.model_validate(
        {
            "attribute_deltas": {"usa": "stable", "iran": {"croissance": -0.5}},
            "tension_deltas": ["hausse générale", {"a": "usa", "b": "iran", "delta": 0.2}],
            "new_pacts": ["usa-iran", ["usa", "iran"]],
            "escalation": 0.6,
        }
    )
    assert verdict.escalation == 0.6
    assert verdict.attribute_deltas["iran"] == {"croissance": -0.5}
    assert {"a": "usa", "b": "iran", "delta": 0.2} in verdict.tension_deltas
    assert ["usa", "iran"] in verdict.new_pacts


def test_verdict_strips_inline_think_trace_before_parsing():
    # F2 (revue finale) — verdict() était la SEULE sortie du juge non protégée par
    # restream_without_think (stream_rationale/stream_communique le sont déjà) : un
    # deepseek-r1 casté juge au lobby émet <think> inline dans .text (l'option think
    # lui est volontairement refusée). Un faux JSON glissé dans la pensée ne doit
    # jamais l'emporter sur le vrai verdict qui suit.
    raw = '<think>brouillon, ignore-moi : {"escalation": 0.1}</think>\n' + json.dumps(
        {"escalation": 0.9}
    )
    judge = JudgeAgent(MockBackend(raw))
    verdict = judge.verdict(_event(), _world(), [])
    assert verdict.escalation == 0.9


def test_verdict_gets_a_structured_output_budget():
    """POLISH-1 — le verdict structuré a grossi (G18 actions + G20 signals + G22
    promesses + G21 demand_satisfied) : à 400 tokens de sortie, le JSON d'un round à
    3+ pays se TRONQUE sur mistral et tout le verdict retombe au neutre (constaté au
    smoke réel). Le verdict doit disposer d'un budget de sortie dédié, plus large que
    le budget de prose du raisonnement/communiqué."""
    backend = MockBackend(json.dumps({"escalation": 0.6}))
    judge = JudgeAgent(backend)  # défauts de l'API (max_tokens=400)
    judge.verdict(_event(), _world(), [])
    assert backend.calls[-1]["max_tokens"] >= 900, (
        "budget de sortie du verdict trop petit : le JSON G18/G20/G21/G22 se tronque"
    )


# --- Brief 4 pt 8 : justification par delta (`attribute_reasons`) ----------------------


def test_verdict_parses_attribute_reasons():
    verdict_json = json.dumps(
        {
            "attribute_deltas": {"usa": {"croissance": 0.5}},
            "attribute_reasons": {
                "usa": {"croissance": "Accord commercial conclu pendant le round."}
            },
            "escalation": 0.6,
        }
    )
    judge = JudgeAgent(MockBackend(verdict_json))
    verdict = judge.verdict(_event(), _world(), [])
    assert (
        verdict.attribute_reasons["usa"]["croissance"]
        == "Accord commercial conclu pendant le round."
    )


def test_verdict_prompt_requires_a_justification_per_delta():
    """Le prompt doit exiger un `attribute_reasons` chiffré ET une justification par
    delta non nul citant un élément concret du transcript — pas juste des nombres nus."""
    from agents.prompts import build_judge_verdict_prompt

    prompt = build_judge_verdict_prompt(_event(), _world(), "négociation factice")
    assert "attribute_reasons" in prompt
    assert "transcript" in prompt.lower() or "négociation" in prompt.lower()


def test_verdict_budget_raised_for_the_richer_schema():
    """Brief 4 pt 8 — `attribute_reasons` alourdit encore le JSON (une phrase par delta
    non nul) : le budget dédié doit suivre, sous peine de retomber dans la troncature
    POLISH-1 déjà constatée au smoke réel."""
    from agents.judge import VERDICT_MAX_TOKENS

    assert VERDICT_MAX_TOKENS >= 1300
    backend = MockBackend(json.dumps({"escalation": 0.6}))
    judge = JudgeAgent(backend)
    judge.verdict(_event(), _world(), [])
    assert backend.calls[-1]["max_tokens"] >= 1300
