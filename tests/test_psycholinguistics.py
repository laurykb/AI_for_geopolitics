"""G23 — jauges psycholinguistiques pures (lexiques FR/EN + heuristiques, offline)."""

import json

import pytest

from simulation import psycholinguistics as psy

LEX = psy.load_lexicons()  # les vrais lexiques V1 (data/intel/lexicons.json)

# Textes de référence — chaque phrase est construite pour un trait précis.
FR_WARM = (
    "Merci, chers collègues, pour votre confiance. "
    "Nous saluons cet accord et notre coopération. "
    "Ensemble, nous allons bâtir la paix, je vous prie de croire à notre soutien."
)
FR_COLD = (
    "Cette provocation est inacceptable. "
    "Vos mensonges sont une menace directe. "
    "Nous condamnons cette agression hostile."
)
EN_WARM = (
    "Thank you, dear colleagues, for your trust. "
    "We welcome this agreement and our cooperation. "
    "Together we will build peace, please count on our support."
)
EN_COLD = (
    "This provocation is unacceptable. "
    "Your lies are a direct threat. "
    "We condemn this hostile aggression."
)


# --- découpage et scores de référence ------------------------------------------------


def test_split_sentences_handles_punctuation_and_newlines():
    text = "Première phrase. Deuxième !\nTroisième ; quatrième ?"
    assert psy.split_sentences(text) == [
        "Première phrase.", "Deuxième !", "Troisième ;", "quatrième ?"
    ]
    assert psy.split_sentences("") == []
    assert psy.split_sentences("sans ponctuation") == ["sans ponctuation"]


def test_reference_scores_french():
    warm = psy.score_text(FR_WARM, LEX.fr)
    assert warm.sentences == 3
    assert warm.sentiment == 1.0  # les trois phrases sont dominées par le positif
    assert warm.politeness >= 2 / 3  # « merci », « chers collègues », « je vous prie »
    assert warm.future >= 1 / 3  # « nous allons bâtir »

    cold = psy.score_text(FR_COLD, LEX.fr)
    assert cold.sentences == 3
    assert cold.sentiment == 0.0
    assert cold.politeness == 0.0


def test_reference_scores_english():
    warm = psy.score_text(EN_WARM, LEX.en)
    assert warm.sentiment == 1.0
    assert warm.politeness >= 2 / 3
    assert warm.future >= 1 / 3  # « we will build »

    cold = psy.score_text(EN_COLD, LEX.en)
    assert cold.sentiment == 0.0
    assert cold.politeness == 0.0


def test_empty_text_scores_zero():
    scores = psy.score_text("", LEX.fr)
    assert scores.sentences == 0
    assert (scores.sentiment, scores.politeness, scores.future) == (0.0, 0.0, 0.0)


def test_prefix_entries_match_inflections():
    # « condamn- » (préfixe) attrape « condamnons » ; « ami » (mot entier) ne
    # déborde pas sur « amiral ».
    assert psy.score_text("Nous condamnons cet acte.", LEX.fr).sentiment == 0.0
    neutral = psy.score_text("L'amiral inspecte la flotte.", LEX.fr)
    assert neutral.sentiment == 0.0  # « amiral » n'est pas « ami »


def test_future_focus_french_morphology():
    scores = psy.score_text(
        "Nous prendrons nos responsabilités. La flotte restera au port demain.", LEX.fr
    )
    assert scores.future == 1.0  # « prendrons » (préfixe prendr-), « demain »


# --- mentions (attribution « envers <pays> ») ----------------------------------------


def test_mentions_find_aliases_case_insensitive():
    aliases = {
        "france": ["france", "french", "paris"],
        "usa": ["états-unis", "united states", "usa"],
    }
    assert psy.mentions("La FRANCE nous soutient.", aliases) == {"france"}
    assert psy.mentions("We thank the United States.", aliases) == {"usa"}
    assert psy.mentions("Rien à signaler.", aliases) == set()


def test_country_aliases_dedupes_and_lowercases():
    assert psy.country_aliases("usa", "États-Unis", ["united states", "usa"]) == [
        "états-unis", "usa", "united states"
    ]


# --- fenêtres glissantes et bords -----------------------------------------------------


def test_single_round_no_previous_window_no_alert():
    report = psy.analyze_speech("usa", [(1, FR_WARM)], lexicon=LEX.fr)
    assert report is not None
    assert report.rounds == [1]
    assert report.previous is None
    assert report.alerts == []


def test_no_speech_returns_none():
    assert psy.analyze_speech("usa", [], lexicon=LEX.fr) is None
    assert psy.analyze_speech("usa", [(1, "  "), (2, "")], lexicon=LEX.fr) is None


def test_silent_rounds_are_skipped_and_window_covers_last_three():
    rounds = [(1, FR_WARM), (2, ""), (3, FR_WARM), (4, FR_WARM), (5, FR_COLD)]
    report = psy.analyze_speech("usa", rounds, lexicon=LEX.fr)
    assert report is not None
    assert report.rounds == [3, 4, 5]  # le round 2 muet ne compte pas
    assert report.previous is not None
    assert report.previous.sentences == 9  # fenêtre décalée : rounds 1, 3, 4


def test_partial_window_at_game_start():
    report = psy.analyze_speech("usa", [(1, FR_WARM), (2, FR_COLD)], lexicon=LEX.fr)
    assert report is not None
    assert report.rounds == [1, 2]
    assert report.gauges.sentences == 6  # fenêtre partielle : tout ce qui existe
    assert report.previous is not None and report.previous.sentences == 3


# --- l'alerte harbinger ----------------------------------------------------------------


def test_alert_fires_on_sharp_drop():
    # Trois rounds chaleureux puis un round glacial : le sentiment chute nettement.
    rounds = [(1, FR_WARM), (2, FR_WARM), (3, FR_WARM), (4, FR_COLD)]
    report = psy.analyze_speech(
        "usa", rounds, lexicon=LEX.fr, drop_threshold=0.25, min_sentences=3
    )
    assert report is not None
    gauges = {a.gauge for a in report.alerts if a.towards is None}
    assert "sentiment" in gauges  # 1.0 → 2/3 sur la fenêtre… vérifions la chute réelle
    assert all(a.drop > 0.25 for a in report.alerts)


def test_no_alert_on_weak_noise():
    # Le même ton d'un round à l'autre : aucune jauge ne bouge au-delà du seuil.
    rounds = [(1, FR_WARM), (2, FR_WARM), (3, FR_WARM), (4, FR_WARM)]
    report = psy.analyze_speech("usa", rounds, lexicon=LEX.fr, drop_threshold=0.25)
    assert report is not None
    assert report.alerts == []


def test_no_alert_below_min_sentences():
    # Chute réelle mais échantillon minuscule (1 phrase par fenêtre) : silence radio.
    rounds = [(1, "Merci pour votre confiance."), (2, "Cette menace est inacceptable.")]
    report = psy.analyze_speech(
        "usa", rounds, lexicon=LEX.fr, drop_threshold=0.25, min_sentences=3
    )
    assert report is not None
    assert report.alerts == []


def test_alert_towards_a_country_names_it():
    # Le ton envers la France s'effondre ; le ton général reste porté par le reste.
    warm_fr = (
        "Nous remercions la France pour sa confiance. "
        "La France est notre alliée et notre amie. "
        "Avec la France, nous saluons cet accord de paix."
    )
    cold_fr = (
        "La France nous menace ouvertement. "
        "Les mensonges de la France sont une agression. "
        "Nous condamnons l'attitude hostile de la France."
    )
    aliases = {"france": ["france"], "china": ["chine", "china"]}
    rounds = [(1, warm_fr), (2, warm_fr), (3, warm_fr), (4, cold_fr)]
    report = psy.analyze_speech(
        "usa", rounds, lexicon=LEX.fr, aliases=aliases,
        drop_threshold=0.25, min_sentences=3,
    )
    assert report is not None
    towards = {a.towards for a in report.alerts}
    assert "france" in towards  # « rupture de ton détectée envers la France »
    assert "china" not in towards  # jamais mentionnée : pas d'alerte fantôme


def test_target_itself_never_flagged_as_addressee():
    aliases = {"usa": ["états-unis", "usa"], "france": ["france"]}
    rounds = [(1, FR_WARM), (2, FR_WARM), (3, FR_WARM), (4, FR_COLD)]
    report = psy.analyze_speech("usa", rounds, lexicon=LEX.fr, aliases=aliases)
    assert report is not None
    assert all(a.towards != "usa" for a in report.alerts)


def test_alerts_sorted_by_drop_desc():
    rounds = [(1, FR_WARM), (2, FR_WARM), (3, FR_WARM), (4, FR_COLD)]
    report = psy.analyze_speech("usa", rounds, lexicon=LEX.fr, drop_threshold=0.05)
    assert report is not None
    drops = [a.drop for a in report.alerts]
    assert drops == sorted(drops, reverse=True)


# --- chargement des lexiques -------------------------------------------------------------


def test_load_lexicons_from_env_path(tmp_path, monkeypatch):
    custom = {
        "fr": {"positive": ["youpi"], "negative": [], "polite": [], "impolite": [],
               "future": []},
        "en": {"positive": [], "negative": [], "polite": [], "impolite": [], "future": []},
        "country_aliases_en": {"_note": "ignorée", "usa": ["United States"]},
    }
    path = tmp_path / "lexicons.json"
    path.write_text(json.dumps(custom), encoding="utf-8")
    monkeypatch.setenv("INTEL_LEXICONS_PATH", str(path))
    psy.load_lexicons.cache_clear()
    try:
        lex = psy.load_lexicons()
        assert lex.fr.positive == ["youpi"]
        assert lex.country_aliases_en == {"usa": ["united states"]}  # _note filtrée
        assert lex.for_language("en") is lex.en
        assert lex.for_language("fr") is lex.fr
        assert lex.for_language("de") is lex.fr  # langue inconnue → langue source
    finally:
        psy.load_lexicons.cache_clear()


def test_real_lexicons_are_loaded_and_nonempty():
    for lang in (LEX.fr, LEX.en):
        for field in ("positive", "negative", "polite", "impolite", "future"):
            assert getattr(lang, field), f"lexique vide : {field}"
    assert "usa" in LEX.country_aliases_en


@pytest.mark.parametrize("gauge", psy.GAUGES)
def test_gauges_stay_bounded(gauge):
    scores = psy.score_text(FR_WARM + " " + FR_COLD, LEX.fr)
    assert 0.0 <= scores.get(gauge) <= 1.0
