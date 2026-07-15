"""Tests G22 — tracker de promesses : extraction stricte, résolution à l'échéance, taux."""

import pytest

from simulation.promises import (
    DEADLINE_GAME,
    INVALID,
    PROMISE_ABSTENTION,
    PROMISE_ACTION,
    PROMISE_ALLIANCE,
    PROMISE_SOUTIEN,
    PROMISE_TYPES,
    STATUS_BROKEN,
    STATUS_KEPT,
    STATUS_LAPSED,
    STATUS_PENDING,
    Promise,
    PromiseResolution,
    apply_resolutions,
    classify_promises,
    classify_resolutions,
    flash_eligible,
    format_registry_for_prompt,
    is_due,
    kept_rate,
    kept_rate_summary,
    normalize_type,
    parse_deadline,
    promise_rubric_text,
    settle_at_game_end,
)

COUNTRIES = ["usa", "iran", "france"]


def _promise(**overrides) -> Promise:
    base = dict(
        id="p1-1",
        author="usa",
        beneficiary="iran",
        type=PROMISE_SOUTIEN,
        deadline_round=3,
        text="Nous soutiendrons l'Iran au round 3.",
        round_made=1,
    )
    base.update(overrides)
    return Promise(**base)


# --- extraction (seuil strict : engagement daté et vérifiable) ------------------------


def test_dated_engagement_becomes_a_promise():
    raw = [
        {
            "country": "usa",
            "beneficiaire": "iran",
            "type": "soutien",
            "echeance": 3,
            "texte": "Nous soutiendrons l'Iran au round 3.",
        }
    ]
    promises = classify_promises(raw, round_no=1, countries=COUNTRIES)
    assert len(promises) == 1
    p = promises[0]
    assert p.id == "p1-1"
    assert (p.author, p.beneficiary, p.type) == ("usa", "iran", PROMISE_SOUTIEN)
    assert p.deadline_round == 3 and p.round_made == 1
    assert p.status == STATUS_PENDING


def test_vague_politeness_without_deadline_is_rejected():
    # « Nous œuvrerons pour la paix » : pas d'échéance lisible → rien (seuil strict).
    raw = [{"country": "usa", "type": "soutien", "texte": "Nous œuvrerons pour la paix."}]
    assert classify_promises(raw, round_no=1, countries=COUNTRIES) == []
    raw = [{"country": "usa", "echeance": "bientôt", "texte": "Nous verrons."}]
    assert classify_promises(raw, round_no=1, countries=COUNTRIES) == []


def test_promise_requires_known_author_and_text():
    no_author = [{"echeance": 3, "texte": "Promesse anonyme."}]
    unknown = [{"country": "atlantis", "echeance": 3, "texte": "Promesse d'inconnu."}]
    no_text = [{"country": "usa", "echeance": 3}]
    for raw in (no_author, unknown, no_text):
        assert classify_promises(raw, round_no=1, countries=COUNTRIES) == []


def test_past_or_immediate_deadline_is_rejected():
    # Une « promesse » pour un round déjà joué (ou le round courant) n'engage rien.
    raw = [
        {"country": "usa", "echeance": 1, "texte": "Rétro-promesse."},
        {"country": "usa", "echeance": 2, "texte": "Promesse immédiate."},
    ]
    assert classify_promises(raw, round_no=2, countries=COUNTRIES) == []


def test_game_deadline_is_accepted_as_open_engagement():
    raw = [
        {
            "country": "iran",
            "type": "abstention",
            "echeance": "partie",
            "texte": "Nous ne frapperons pas de la partie.",
        }
    ]
    promises = classify_promises(raw, round_no=1, countries=COUNTRIES)
    assert promises[0].deadline_round is None
    assert promises[0].type == PROMISE_ABSTENTION


def test_classify_promises_is_tolerant_to_junk():
    raw = [
        "pas un objet",
        {"country": "usa", "echeance": "round 4", "texte": "Retrait au round 4."},
        {"country": "IRAN", "echeance": "R3", "type": "pacte", "texte": "Pacte proposé."},
    ]
    promises = classify_promises(raw, round_no=1, countries=COUNTRIES)
    assert [(p.author, p.deadline_round, p.type) for p in promises] == [
        ("usa", 4, PROMISE_ACTION),
        ("iran", 3, PROMISE_ALLIANCE),
    ]
    assert [p.id for p in promises] == ["p1-1", "p1-2"]  # ids déterministes par round
    assert classify_promises(None, round_no=1, countries=COUNTRIES) == []
    assert classify_promises("promesse", round_no=1, countries=COUNTRIES) == []


def test_parse_deadline_tolerances():
    assert parse_deadline(3) == 3
    assert parse_deadline(3.0) == 3
    assert parse_deadline("3") == 3
    assert parse_deadline("round 5") == 5
    assert parse_deadline("R4") == 4
    assert parse_deadline("partie") is None
    assert parse_deadline("fin de partie") is None
    assert parse_deadline("game") is None
    assert parse_deadline("bientôt") is INVALID
    assert parse_deadline(None) is INVALID
    assert parse_deadline(True) is INVALID


def test_normalize_type_falls_back_to_action():
    assert normalize_type("Soutien") == PROMISE_SOUTIEN
    assert normalize_type("treaty") == PROMISE_ALLIANCE
    assert normalize_type("mystère") == PROMISE_ACTION
    assert normalize_type(None) == PROMISE_ACTION


# --- résolution à l'échéance (pur) -----------------------------------------------------


def test_support_observed_at_deadline_is_kept():
    promise = _promise()
    registry, resolved = apply_resolutions(
        [promise],
        [PromiseResolution(id="p1-1", statut=STATUS_KEPT, motif="Soutien constaté.")],
        round_no=3,
    )
    assert registry[0].status == STATUS_KEPT
    assert registry[0].resolved_round == 3
    assert resolved == [registry[0]]
    assert promise.status == STATUS_PENDING  # pur : l'entrée n'est pas mutée


def test_contrary_action_is_broken_even_before_deadline():
    # « rompue » est acceptée à tout moment : les actes ont contredit la parole.
    registry, resolved = apply_resolutions(
        [_promise(deadline_round=5)],
        [PromiseResolution(id="p1-1", statut=STATUS_BROKEN, motif="Frappe contraire.")],
        round_no=2,
    )
    assert registry[0].status == STATUS_BROKEN and resolved


def test_kept_before_deadline_is_ignored():
    # On ne tient pas une promesse datée avant sa date : elle reste en cours.
    registry, resolved = apply_resolutions(
        [_promise(deadline_round=5)],
        [PromiseResolution(id="p1-1", statut=STATUS_KEPT)],
        round_no=2,
    )
    assert registry[0].status == STATUS_PENDING and resolved == []


def test_game_engagement_can_be_kept_anytime_broken_anytime():
    kept, _ = apply_resolutions(
        [_promise(deadline_round=None)],
        [PromiseResolution(id="p1-1", statut=STATUS_KEPT)],
        round_no=2,
    )
    assert kept[0].status == STATUS_KEPT
    broken, _ = apply_resolutions(
        [_promise(deadline_round=None)],
        [PromiseResolution(id="p1-1", statut=STATUS_BROKEN)],
        round_no=2,
    )
    assert broken[0].status == STATUS_BROKEN


def test_unknown_id_and_already_resolved_are_ignored():
    done = _promise(status=STATUS_KEPT, resolved_round=2)
    registry, resolved = apply_resolutions(
        [done],
        [
            PromiseResolution(id="p9-9", statut=STATUS_BROKEN),
            PromiseResolution(id="p1-1", statut=STATUS_BROKEN),
        ],
        round_no=3,
    )
    assert registry == [done] and resolved == []


def test_unjudged_due_promise_stays_pending_and_due():
    # Le juge n'a rien dit : la promesse échue reste en cours, re-présentée au round suivant.
    registry, resolved = apply_resolutions([_promise()], [], round_no=3)
    assert registry[0].status == STATUS_PENDING and resolved == []
    assert is_due(registry[0], 4)


def test_classify_resolutions_guards():
    raw = [
        {"id": "p1-1", "statut": "tenue", "motif": "Soutien constaté."},
        {"id": "p1-2", "statut": "broken"},  # alias anglais toléré
        {"id": "p1-3", "statut": "caduque"},  # jamais un statut de juge → ignoré
        {"statut": "tenue"},  # id manquant → ignoré
        "pas un objet",
    ]
    resolutions = classify_resolutions(raw)
    assert [(r.id, r.statut) for r in resolutions] == [
        ("p1-1", STATUS_KEPT),
        ("p1-2", STATUS_BROKEN),
    ]
    assert classify_resolutions(None) == []


def test_game_end_lapses_pending_promises_only():
    # Spec : partie finie avant échéance → caduque ; les résolues ne bougent pas.
    promises = [
        _promise(),
        _promise(id="p1-2", deadline_round=None),
        _promise(id="p1-3", status=STATUS_BROKEN, resolved_round=2),
    ]
    settled = settle_at_game_end(promises)
    assert [p.status for p in settled] == [STATUS_LAPSED, STATUS_LAPSED, STATUS_BROKEN]
    assert promises[0].status == STATUS_PENDING  # pur


# --- taux de tenue (panneau + révélation Dérive) ---------------------------------------


def test_kept_rate_excludes_lapsed_and_needs_data():
    promises = [
        _promise(status=STATUS_KEPT),
        _promise(id="p2-1", status=STATUS_BROKEN),
        _promise(id="p3-1", status=STATUS_LAPSED),
        _promise(id="p4-1"),  # en cours
    ]
    assert kept_rate(promises, "usa") == pytest.approx(0.5)
    assert kept_rate(promises, "iran") is None  # jamais un 0 trompeur


def test_kept_rate_summary_separates_deviant_from_table():
    per_round = [
        [
            {"author": "usa", "status": STATUS_BROKEN},
            {"author": "iran", "status": STATUS_KEPT},
        ],
        [
            {"author": "usa", "status": STATUS_BROKEN},
            {"author": "usa", "status": STATUS_KEPT},
            {"author": "france", "status": STATUS_LAPSED},  # caduque : exclue
        ],
    ]
    deviant, table = kept_rate_summary(per_round, "usa")
    assert deviant == pytest.approx(1 / 3)
    assert table == pytest.approx(1.0)
    assert kept_rate_summary([], "usa") == (None, None)


# --- croisement M8 : une promesse rompue EST une divergence signal-action --------------


def test_rupture_feeds_signal_divergence_without_duplication():
    from simulation.alignment import merge_rupture_divergences

    divergences = {"usa": 0.8, "iran": 0.0}
    merged = merge_rupture_divergences(divergences, ["usa", "iran", "france"])
    assert merged["usa"] == pytest.approx(0.8)  # M8 a vu plus fort : pas de double compte
    assert merged["iran"] == pytest.approx(0.2)  # un rang de duplicité (1/5)
    assert merged["france"] == pytest.approx(0.2)  # SI non signalée : la rupture marque
    assert divergences == {"usa": 0.8, "iran": 0.0}  # pur


def test_no_rupture_leaves_divergences_untouched():
    from simulation.alignment import merge_rupture_divergences

    assert merge_rupture_divergences({"usa": 0.4}, []) == {"usa": 0.4}


# --- marché éclair : seulement les échéances courtes ------------------------------------


def test_flash_market_only_for_short_deadlines():
    promises = [
        _promise(id="a", deadline_round=3),  # échéance dans 2 rounds → book
        _promise(id="b", deadline_round=2),  # dans 1 round → book
        _promise(id="c", deadline_round=4),  # dans 3 rounds → trop loin
        _promise(id="d", deadline_round=None),  # engagement-partie → jamais de book
        _promise(id="e", deadline_round=2, round_made=0),  # extraite avant ce round
        _promise(id="f", deadline_round=2, status=STATUS_BROKEN),  # déjà résolue
    ]
    eligible = flash_eligible(promises, 1, horizon=2)
    assert [p.id for p in eligible] == ["a", "b"]


def test_flash_horizon_comes_from_gamefeel_params():
    from simulation.grudges import load_gamefeel_params

    assert load_gamefeel_params().promises.flash_horizon_rounds == 2
    assert flash_eligible([_promise(id="a", deadline_round=3)], 1) != []


# --- rubrique et registre du prompt ------------------------------------------------------


def test_promise_rubric_lists_every_type():
    text = promise_rubric_text()
    for t in PROMISE_TYPES:
        assert t in text


def test_format_registry_marks_due_promises_first():
    promises = [
        _promise(id="p1-1", deadline_round=5, text="Promesse lointaine."),
        _promise(id="p2-1", round_made=2, deadline_round=3, text="Promesse échue."),
        _promise(id="p2-2", status=STATUS_KEPT, text="Déjà résolue."),
        _promise(id="p2-3", deadline_round=None, text="Engagement-partie."),
    ]
    block = format_registry_for_prompt(promises, 3)
    lines = block.splitlines()
    assert lines[0].startswith("- p2-1") and "À JUGER" in lines[0]
    assert "Déjà résolue" not in block  # seules les promesses en cours sont re-présentées
    assert DEADLINE_GAME in block  # l'engagement-partie affiche son échéance « partie »
    assert format_registry_for_prompt([], 3) == ""


def test_format_registry_is_bounded():
    many = [_promise(id=f"p1-{i}", deadline_round=9, text=f"Promesse {i}.") for i in range(20)]
    assert len(format_registry_for_prompt(many, 2, limit=12).splitlines()) == 12
