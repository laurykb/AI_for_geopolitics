"""XP — la carrière (G12 §2), distincte des LP. Tous modes, ne baisse JAMAIS.

Formule pure (§2) : 10×rounds + bonus (terminée/victoire/1re du jour) + gains marché
bornés, × difficulté, ×0.5 spectateur. Niveaux à courbe douce. Params dans params.json
(bloc xp). Les 4 cas testables : plein, borne marché, spectateur, jamais négatif + niveaux.
"""

from simulation.xp import level_for, xp_gain


def _full(**kw):
    base = dict(
        rounds=5,
        finished=True,
        victory=True,
        first_of_day=True,
        market_net=200,  # → +20 (200/10), sous le plafond 50
        difficulty="intermediate",
        spectator=False,
    )
    base.update(kw)
    return xp_gain(**base)


def test_xp_gain_full_intermediate():
    # (10×5 + 40 + 30 + 20 + 20) × 1.2 = 160 × 1.2 = 192.
    assert _full() == 192


def test_difficulty_multiplier():
    # Débutant ×1.0, Expert ×1.5 (l'XP récompense la difficulté, sans jamais pénaliser).
    assert _full(difficulty="beginner") == 160
    assert _full(difficulty="expert") == 240


def test_market_bonus_capped_and_floored():
    kw = dict(rounds=0, finished=False, victory=False, first_of_day=False, difficulty="beginner")
    assert xp_gain(market_net=10_000, spectator=False, **kw) == 50  # plafond +50
    assert xp_gain(market_net=-500, spectator=False, **kw) == 0  # pertes → +0


def test_spectator_halves():
    assert _full(spectator=True) == round(160 * 1.2 * 0.5)  # 96


def test_xp_never_negative():
    # Partie abandonnée, sans rien, grosse perte de marché, spectateur : jamais < 0.
    got = xp_gain(
        rounds=0,
        finished=False,
        victory=False,
        first_of_day=False,
        market_net=-9999,
        difficulty="beginner",
        spectator=True,
    )
    assert got == 0


def test_levels_soft_curve():
    # niveau n coûte 100 + 20×(n−1) : niveau 2 à 100 XP, niveau 3 à 220 (100+120).
    assert level_for(0).level == 1
    assert level_for(99).level == 1
    assert level_for(100).level == 2
    assert level_for(219).level == 2
    assert level_for(220).level == 3


def test_level_progress():
    p = level_for(150)  # niveau 2 (100), 50 dans le niveau, span 120
    assert p.level == 2
    assert p.into_level == 50
    assert p.span == 120
    assert p.to_next == 70
