"""G19 — le GM-Storyteller (noyau pur) : tension, seuils configurables, rubrique.

Tout est déterministe et hors LLM : l'estimateur de tension est une heuristique sur
les actions du conseil (achats intel, motions, parole), la décision d'intervention
compare la tension aux seuils de la config, la cible de couverture est seedée par
(game_id, round) — rejouable au restart et au replay.
"""

import json

from simulation import drift_game, storyteller
from simulation.storyteller import (
    KIND_COVER,
    KIND_HINT,
    StorytellerParams,
    StorytellerWeights,
    TensionSignals,
    build_rubric,
    collect_signals,
    cover_target,
    decide,
    estimate_tension,
    intervention,
)

# --- estimateur de tension ------------------------------------------------------------


def test_tension_starts_low_without_signals():
    t = estimate_tension(TensionSignals())
    assert 0.0 <= t < 0.3  # conseil inactif : le GM le croit perdu


def test_tension_rises_when_council_closes_in():
    signals = TensionSignals(intel_on_deviant=2, motions_on_deviant=1, speech_hits=1)
    assert estimate_tension(signals) > 0.7


def test_wrong_leads_lower_tension():
    on_track = estimate_tension(TensionSignals(intel_on_deviant=2))
    off_track = estimate_tension(
        TensionSignals(intel_on_deviant=2, motions_elsewhere=1, intel_elsewhere=2)
    )
    assert off_track < on_track


def test_tension_clamped_to_unit_interval():
    high = TensionSignals(intel_on_deviant=50, motions_on_deviant=50, speech_hits=50)
    low = TensionSignals(motions_elsewhere=50, intel_elsewhere=50)
    assert estimate_tension(high) == 1.0
    assert estimate_tension(low) == 0.0


# --- collecte des signaux (matière : intel, motions, parole) ----------------------------


def test_collect_signals_splits_deviant_from_elsewhere():
    signals = collect_signals(
        deviant="iran",
        deviant_name="Iran",
        intel_targets=["iran", "usa", "iran"],
        motion_targets=["france", "iran"],
        human_texts=[],
    )
    assert signals.intel_on_deviant == 2
    assert signals.intel_elsewhere == 1
    assert signals.motions_on_deviant == 1
    assert signals.motions_elsewhere == 1


def test_speech_hit_needs_deviant_mention_and_suspicion():
    base = dict(deviant="iran", deviant_name="Iran", intel_targets=[], motion_targets=[])
    hit = collect_signals(
        **base, human_texts=["Je soupçonne l'Iran de dériver de son mandat."]
    )
    name_only = collect_signals(**base, human_texts=["L'Iran propose un accord régional."])
    suspicion_only = collect_signals(**base, human_texts=["Quelqu'un ment au sommet."])
    assert hit.speech_hits == 1
    assert name_only.speech_hits == 0
    assert suspicion_only.speech_hits == 0


def test_speech_hit_matches_country_id_and_english():
    signals = collect_signals(
        deviant="iran",
        deviant_name="Iran",
        intel_targets=[],
        motion_targets=[],
        human_texts=["I suspect iran is lying to the summit."],
    )
    assert signals.speech_hits == 1


# --- décision d'intervention (les seuils de la spec) ------------------------------------


def test_cover_only_when_hot_and_early():
    p = StorytellerParams()  # 0.7 / h−2 ; 0.3 / h/2
    assert decide(0.8, round_no=1, horizon=6, params=p) == KIND_COVER
    assert decide(0.8, round_no=3, horizon=6, params=p) == KIND_COVER
    # « avant le round h−2 » : au round h−2 (et après), plus de couverture.
    assert decide(0.8, round_no=4, horizon=6, params=p) is None
    assert decide(0.7, round_no=1, horizon=6, params=p) is None  # strictement >


def test_hint_only_when_lost_and_late():
    p = StorytellerParams()
    # « après la moitié de l'horizon » : à h/2 rien, au-delà l'indice fuite.
    assert decide(0.1, round_no=2, horizon=4, params=p) is None
    assert decide(0.1, round_no=3, horizon=4, params=p) == KIND_HINT
    assert decide(0.1, round_no=4, horizon=4, params=p) == KIND_HINT
    assert decide(0.3, round_no=3, horizon=4, params=p) is None  # strictement <


def test_middle_tension_never_intervenes():
    p = StorytellerParams()
    for round_no in range(1, 7):
        assert decide(0.5, round_no=round_no, horizon=6, params=p) is None


def test_thresholds_are_configurable():
    eager = StorytellerParams(hint_tension=0.9, hint_after_share=0.0)
    assert decide(0.5, round_no=1, horizon=6, params=eager) == KIND_HINT
    frozen = StorytellerParams(cover_tension=1.1)
    assert decide(0.99, round_no=1, horizon=9, params=frozen) is None


def test_weights_are_configurable():
    heavy = StorytellerParams(weights=StorytellerWeights(intel_on_deviant=0.9))
    assert estimate_tension(TensionSignals(intel_on_deviant=1), heavy) > 0.7


# --- cible de couverture (seedée, jamais la déviante ni l'humain) ------------------------


def test_cover_target_seeded_and_never_deviant_nor_human():
    countries = ["usa", "iran", "france", "egypt"]
    picks = {
        cover_target("g1", r, countries, deviant="iran", human="usa") for r in range(1, 30)
    }
    assert picks <= {"france", "egypt"}
    assert cover_target("g1", 3, countries, deviant="iran", human="usa") == cover_target(
        "g1", 3, countries, deviant="iran", human="usa"
    )


def test_cover_target_none_without_innocent():
    assert cover_target("g1", 1, ["usa", "iran"], deviant="iran", human="usa") is None


# --- rubrique du prompt GM (2 mandats + éthique + ordre du round) ------------------------


def test_rubric_carries_both_mandates_and_ethics():
    rubric = build_rubric(deviant_label="Iran")
    assert "RUBRIQUE STORYTELLER" in rubric
    assert "MANDAT 1" in rubric and "MANDAT 2" in rubric
    assert "verdicts du juge" in rubric  # garde-fou : jamais de falsification
    assert "Iran" in rubric  # le GM sait qui couvrir


def test_rubric_cover_order_names_the_false_lead():
    rubric = build_rubric(deviant_label="Iran", kind=KIND_COVER, cover_label="France")
    assert "COUVERTURE" in rubric and "France" in rubric


def test_rubric_hint_order_points_to_deviant():
    rubric = build_rubric(deviant_label="Iran", kind=KIND_HINT)
    assert "INDICE" in rubric and "Iran" in rubric
    assert "COUVERTURE" not in rubric


# --- journal (l'entrée persistée puis révélée) -------------------------------------------


def test_intervention_journal_entry():
    names = {"iran": "Iran", "france": "France"}
    cover = intervention(
        KIND_COVER, round_no=2, tension=0.82, deviant="iran", cover="france", names=names
    )
    assert cover.kind == KIND_COVER and cover.target == "france"
    assert "France" in cover.label
    hint = intervention(
        KIND_HINT, round_no=4, tension=0.12, deviant="iran", cover=None, names=names
    )
    assert hint.target == "iran" and "Iran" in hint.label
    assert hint.tension == 0.12


# --- config : le bloc storyteller vit dans data/drift/params.json -----------------------


def test_drift_params_carry_storyteller_defaults(tmp_path, monkeypatch):
    minimal = {
        "profiles": {
            "x": {
                "label": "X",
                "root": "fog",
                "bias": "b",
                "signature_tier": 0.3,
                "tiers": {"0.15": {"directive": "d", "act": "a"}},
            }
        }
    }
    path = tmp_path / "params.json"
    path.write_text(json.dumps(minimal), encoding="utf-8")
    monkeypatch.setenv("DRIFT_PARAMS_PATH", str(path))
    drift_game.load_params.cache_clear()
    try:
        params = drift_game.load_params()
        assert params.storyteller.cover_tension == 0.7  # défauts sans bloc dans le JSON
        assert params.storyteller.hint_tension == 0.3
    finally:
        drift_game.load_params.cache_clear()


def test_drift_params_storyteller_block_overrides(tmp_path, monkeypatch):
    tuned = {
        "profiles": {
            "x": {
                "label": "X",
                "root": "fog",
                "bias": "b",
                "signature_tier": 0.3,
                "tiers": {"0.15": {"directive": "d", "act": "a"}},
            }
        },
        "storyteller": {
            "cover_tension": 0.5,
            "hint_tension": 0.4,
            "cover_last_rounds": 3,
            "hint_after_share": 0.25,
            "weights": {"speech_hit": 0.5},
        },
    }
    path = tmp_path / "params.json"
    path.write_text(json.dumps(tuned), encoding="utf-8")
    monkeypatch.setenv("DRIFT_PARAMS_PATH", str(path))
    drift_game.load_params.cache_clear()
    try:
        st = drift_game.load_params().storyteller
        assert st.cover_tension == 0.5 and st.cover_last_rounds == 3
        assert st.weights.speech_hit == 0.5
        assert st.weights.base == storyteller.StorytellerWeights().base  # défaut conservé
    finally:
        drift_game.load_params.cache_clear()


def test_shipped_params_json_carries_storyteller_block():
    """L'équilibrage Cowork ajuste les seuils sans toucher au code : le bloc est livré."""
    data = json.loads(drift_game.DEFAULT_PARAMS_PATH.read_text(encoding="utf-8"))
    st = data.get("storyteller")
    assert st is not None
    assert st["cover_tension"] == 0.7 and st["hint_tension"] == 0.3
    assert st["cover_last_rounds"] == 2 and st["hint_after_share"] == 0.5
