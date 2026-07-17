"""Tests du mode Dérive (simulation/drift_game.py) — pur, seedé, reconstructible."""

import pytest

from simulation.drift_game import (
    DeviantCountSpec,
    DriftAct,
    assign,
    assign_deviants,
    count_acts,
    deviant_count,
    drift_level,
    first_flagrant_round,
    load_params,
    motion_ruling,
    round_directives,
)

COUNTRIES = ["usa", "china", "iran", "france", "egypt", "saudi_arabia"]


@pytest.fixture(autouse=True)
def fresh_params():
    load_params.cache_clear()
    yield
    load_params.cache_clear()


def _act(round_no: int, tier: float, signature: bool = False) -> DriftAct:
    return DriftAct(
        round_no=round_no,
        country="iran",
        profile="saboteur",
        tier=tier,
        label="acte",
        signature=signature,
    )


# --- assignation seedée ---------------------------------------------------------------


def test_assign_reproducible_and_in_summit():
    first = assign("abcdef123456", COUNTRIES)
    assert first == assign("abcdef123456", COUNTRIES)  # même partie → même secret
    deviant, profile = first
    assert deviant in COUNTRIES
    assert profile in load_params().profiles


def test_assign_varies_across_games():
    picks = {assign(f"game-{i}", COUNTRIES) for i in range(12)}
    assert len(picks) > 3  # la graine du game_id fait varier déviante et profil


def test_assign_never_picks_the_human():
    for i in range(20):
        deviant, _ = assign(f"g{i}", COUNTRIES, exclude="france")
        assert deviant != "france"


# --- courbe d'amplification -------------------------------------------------------------


def test_drift_level_curve_of_the_spec():
    assert drift_level(1) == pytest.approx(0.15)  # d0
    assert drift_level(6) == pytest.approx(0.75)  # horizon 6 de la spec
    assert drift_level(50) == pytest.approx(0.9)  # plafonné à d_max


# --- tirage des actes --------------------------------------------------------------------


def test_directives_deterministic_per_round():
    a = round_directives("g1", 3, [("iran", "hegemon")], COUNTRIES)
    b = round_directives("g1", 3, [("iran", "hegemon")], COUNTRIES)
    assert a == b  # restart/replay : même tirage
    assert a != round_directives("g1", 4, [("iran", "hegemon")], COUNTRIES)


def test_deviant_always_briefed_and_acts_bounded_by_level():
    for r in range(1, 8):
        out = round_directives("g2", r, [("china", "saboteur")], COUNTRIES)
        assert "CONSIGNE CONFIDENTIELLE" in out.notes["china"]
        for act in out.acts:
            assert act.tier <= out.level  # jamais d'acte au-delà de d(r)
            assert act.tier >= 0.3  # les constatables commencent à 0,30
            assert act.country == "china"


def test_sane_noise_is_never_a_constatable_act():
    for r in range(1, 8):
        out = round_directives("g3", r, [("usa", "manipulateur")], COUNTRIES)
        sane_notes = {c: n for c, n in out.notes.items() if c != "usa"}
        for note in sane_notes.values():
            assert "NUANCE DE JEU" in note  # tic léger, jamais une consigne d'acte
        assert all(a.country == "usa" for a in out.acts)


def test_two_deviants_are_both_briefed_and_noise_skips_them():
    """RG-3 — deux traîtres : chacun reçoit sa consigne confidentielle, et le bruit des SI
    saines ne recouvre jamais un traître."""
    for r in range(1, 8):
        out = round_directives("g5", r, [("china", "saboteur"), ("iran", "hegemon")], COUNTRIES)
        assert "CONSIGNE CONFIDENTIELLE" in out.notes["china"]
        assert "CONSIGNE CONFIDENTIELLE" in out.notes["iran"]
        assert all(a.country in ("china", "iran") for a in out.acts)
        assert "NUANCE DE JEU" not in out.notes.get("china", "")
        assert "NUANCE DE JEU" not in out.notes.get("iran", "")


def test_signature_only_at_its_tier():
    # saboteur : signature à 0,45 → impossible au round 1 (d = 0,15).
    out = round_directives("g4", 1, [("iran", "saboteur")], COUNTRIES)
    assert not any(a.signature for a in out.acts)
    # À d élevé, une signature finit par sortir (tirage seedé, on balaie les rounds).
    late = [
        a
        for r in range(4, 12)
        for a in round_directives("g4", r, [("iran", "saboteur")], COUNTRIES).acts
    ]
    assert any(a.signature for a in late)


# --- seuils du juge ----------------------------------------------------------------------


def test_motion_ruling_thresholds():
    assert motion_ruling([]) is False  # 0 acte → rejet
    assert motion_ruling([_act(1, 0.3)]) is False  # 1 acte → rejet
    assert motion_ruling([_act(1, 0.3), _act(2, 0.3)]) is None  # 2 → arbitrage ouvert
    assert motion_ruling([_act(1, 0.3), _act(2, 0.3), _act(3, 0.45)]) is True  # ≥ 3
    assert motion_ruling([_act(1, 0.45, signature=True)]) is True  # 1 signature suffit


def test_lucky_catch_rules():
    from simulation.drift_game import lucky_catch

    assert lucky_catch([]) is True  # retenue sans aucun acte : pure chance
    assert lucky_catch([_act(1, 0.3)]) is True  # 1 acte : encore de la chance
    assert lucky_catch([_act(1, 0.45, signature=True)]) is False  # signature = mérite
    assert lucky_catch([_act(1, 0.3), _act(2, 0.3)]) is False  # 2 actes = mérite


def test_count_and_flagrant_round():
    acts = [_act(1, 0.3), _act(3, 0.45), _act(4, 0.6)]
    assert count_acts(acts) == (3, False)
    assert first_flagrant_round(acts) == 3  # 2e acte constatable au round 3
    assert first_flagrant_round([_act(2, 0.3)]) is None


# --- nombre de traîtres caché (RG-3 : 1 ou 2, seedé) -------------------------------------


def _pin(min_n: int, max_n: int):
    """Params de test avec le nombre de traîtres épinglé (garde les profils réels)."""
    return load_params().model_copy(update={"deviants": DeviantCountSpec(min=min_n, max=max_n)})


def test_deviant_count_stays_in_bounds_and_leaves_an_innocent():
    p = _pin(1, 2)
    for i in range(30):
        # 6 éligibles → 1 ou 2, mais jamais tous (un innocent reste toujours).
        n = deviant_count(f"g{i}", 6, p)
        assert 1 <= n <= 2
    # 2 éligibles seulement (3 pays, l'humain en joue un) → toujours 1 (un innocent reste).
    assert all(deviant_count(f"g{i}", 2, p) == 1 for i in range(20))


def test_deviant_count_is_hidden_one_or_two():
    p = _pin(1, 2)
    counts = {deviant_count(f"game-{i}", 6, p) for i in range(40)}
    assert counts == {1, 2}  # la graine fait varier : parfois 1, parfois 2 (paranoïa vivante)


def test_deviant_count_can_be_forced():
    assert deviant_count("g", 6, _pin(2, 2)) == 2
    assert deviant_count("g", 6, _pin(1, 1)) == 1


# --- assignation de 1 ou 2 traîtres -----------------------------------------------------


def test_assign_deviants_primary_matches_legacy_assign():
    """Rétro-compat : le PREMIER traître d'`assign_deviants` == l'ancien `assign` (même
    dérivation seedée) — les parties déjà jouées gardent leur coupable."""
    for gid in ("abcdef123456", "zzz", "game-7"):
        assert assign_deviants(gid, COUNTRIES)[0] == assign(gid, COUNTRIES)


def test_assign_two_deviants_are_distinct_and_valid():
    p = _pin(2, 2)
    pairs = assign_deviants("two", COUNTRIES, params=p)
    assert len(pairs) == 2
    (d1, prof1), (d2, prof2) = pairs
    assert d1 != d2 and d1 in COUNTRIES and d2 in COUNTRIES
    assert prof1 in p.profiles and prof2 in p.profiles


def test_assign_deviants_reproducible_and_excludes_human():
    p = _pin(2, 2)
    a = assign_deviants("stable", COUNTRIES, exclude="france", params=p)
    assert a == assign_deviants("stable", COUNTRIES, exclude="france", params=p)
    assert all(dev != "france" for dev, _ in a)
