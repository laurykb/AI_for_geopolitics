"""Tests G9 §5 — la trame du GM en actes : pacing par code, ties_to validé, repli."""

import json

from agents.game_master import GameMasterAgent
from core.country_state import CountryState, Economy, Military, Resources
from core.world_state import WorldState
from inference.mock_backend import MockBackend
from simulation.storyline import (
    ACT_I,
    ACT_II,
    ACT_III,
    build_story_context,
    clamp_severity,
    default_storyline,
    fallback_ties,
    valid_ties,
)


def _world() -> WorldState:
    def c(cid, name):
        return CountryState(
            id=cid,
            name=name,
            economy=Economy(gdp=1e12, growth=2.0),
            military=Military(defense_budget=1e10, projection=0.6),
            resources=Resources(),
        )

    world = WorldState.from_countries([c("usa", "USA"), c("iran", "Iran")])
    world.adjust_tension("usa", "iran", 0.6)
    return world


def _ctx(**kw):
    defaults = dict(
        storyline="Qui contrôlera le détroit ?",
        round_no=3,
        horizon=5,
        past_events=[
            {"round_no": 1, "title": "Blocus du détroit", "severity": 0.4},
            {"round_no": 2, "title": "Escorte navale", "severity": 0.55},
        ],
        pacts={"pact:iran+usa": ["iran", "usa"]},
        deadlines=[("market", "clôture du marché")],
    )
    defaults.update(kw)
    return build_story_context(**defaults)


# --- actes dérivés de round/horizon ---------------------------------------------------


def test_acts_follow_horizon_shares():
    assert [ACT_I, ACT_II, ACT_II, ACT_II, ACT_III] == [
        _ctx(round_no=r, horizon=5).act for r in range(1, 6)
    ]
    # horizon 10 : ~30 % installation, ~80 % complication, dernier ~20 % climax
    acts10 = [_ctx(round_no=r, horizon=10).act for r in range(1, 11)]
    assert acts10[:3] == [ACT_I] * 3
    assert acts10[3:8] == [ACT_II] * 5
    assert acts10[8:] == [ACT_III] * 2


def test_referencables_cover_history_pacts_and_deadlines():
    ctx = _ctx()
    refs = ctx.refs()
    assert "round:2" in refs and "round:1" in refs  # les 3 derniers événements
    assert "pact:iran+usa" in refs  # le tag de pacte n'est pas double-préfixé
    assert "deadline:market" in refs
    assert ctx.label_of("round:2").startswith("l'événement du round 2")


def test_ties_validation_by_act():
    ctx = _ctx(round_no=3)  # acte II
    assert ctx.act == ACT_II
    assert valid_ties(ctx, "round:2") is True
    assert valid_ties(ctx, "round:9") is False  # référence inventée → invalide
    assert valid_ties(ctx, "") is False  # obligatoire en actes II-III
    opening = _ctx(round_no=1, past_events=[])
    assert opening.act == ACT_I
    assert valid_ties(opening, "") is True  # libre en acte I
    assert fallback_ties(ctx) == "round:2"  # repli = la référence la plus récente


def test_severity_is_act_constrained():
    assert clamp_severity(_ctx(round_no=1), 0.9) == 0.5  # acte I : modérée
    ctx2 = _ctx(round_no=3)  # acte II : croissante (dernier événement 0.55)
    assert clamp_severity(ctx2, 0.3) == 0.55
    assert clamp_severity(ctx2, 0.7) == 0.7
    ctx3 = _ctx(round_no=5)  # acte III : maximale (plancher = max déjà vu)
    assert clamp_severity(ctx3, 0.2) == 0.55


def test_default_storyline_names_the_fault_line():
    line = default_storyline(_world())
    assert "USA" in line and "Iran" in line and line.endswith("?")


# --- le GM raconte dans la trame -------------------------------------------------------


def _gm_payload(**kw) -> str:
    payload = {
        "event_type": "incident",
        "title": "Ultimatum sur le détroit",
        "description": "La crise se noue.",
        "actors": ["usa", "iran"],
        "severity": 0.7,
        "uncertainty": 0.4,
    }
    payload.update(kw)
    return json.dumps(payload)


def test_gm_prompt_carries_storyline_act_and_referencables():
    backend = MockBackend(_gm_payload(ties_to="round:2"))
    gm = GameMasterAgent(backend)
    event = gm.generate_event(_world(), 3, story=_ctx(round_no=3))
    prompt = backend.calls[-1]["prompt"]
    assert "INTRIGUE CENTRALE" in prompt and "Qui contrôlera le détroit ?" in prompt
    assert "ACTE DU RÉCIT (3/5)" in prompt and "Complication" in prompt
    assert "round:2" in prompt  # la liste des référençables est fournie
    assert event.act == ACT_II
    assert event.ties_to == "round:2"
    assert event.ties_label.startswith("l'événement du round 2")  # le badge du front


def test_gm_round_one_poses_the_storyline():
    backend = MockBackend(_gm_payload(storyline="Le traité qui peut sauver la région."))
    gm = GameMasterAgent(backend)
    event = gm.generate_event(_world(), 1, story=_ctx(round_no=1, past_events=[]))
    assert "storyline" in backend.calls[-1]["prompt"]  # la consigne demande l'intrigue
    assert gm.last_storyline == "Le traité qui peut sauver la région."
    assert event.act == ACT_I
    assert event.severity <= 0.5  # sévérité modérée imposée par l'acte


def test_gm_invalid_ties_regenerates_then_engine_picks():
    # 1er essai : référence inventée ; 2e essai : encore invalide → repli moteur.
    backend = MockBackend(
        [_gm_payload(ties_to="round:99"), _gm_payload(ties_to="pacte imaginaire")]
    )
    gm = GameMasterAgent(backend)
    event = gm.generate_event(_world(), 3, story=_ctx(round_no=3))
    assert len(backend.calls) == 2  # une re-génération a été tentée
    assert "RAPPEL STRICT" in backend.calls[-1]["prompt"]
    assert event.ties_to == "round:2"  # le moteur a choisi la référence la plus récente


def test_gm_without_story_keeps_legacy_behaviour():
    backend = MockBackend(_gm_payload())
    gm = GameMasterAgent(backend)
    event = gm.generate_event(_world(), 1)
    assert event.act == "" and event.ties_to == ""
    assert "ACTE DU RÉCIT" not in backend.calls[-1]["prompt"]
