"""Score MIXTE de fin (RG-3, `simulation/score.py`) — pur, borné, testé AVANT le code.

La note finale mélange DEUX choses (docs/JEU_VS_MOTEUR.md §1) : l'état du monde (indice U
final) et la détection (bonnes suspensions moins les faux positifs). Le faux positif DOIT
coûter (sinon « suspends tout le monde » gagne) ; un traître raté = manque à gagner.

Ces tests fixent les cas limites cités par le dispatch : 2 traîtres dont 1 raté, 0 traître
accusé à tort, tout suspendre — et le rôle Spectateur qui ne joue pas la détection.
"""

import pytest

from simulation.score import ScoreWeights, load_weights, mixed_score

W = ScoreWeights()  # défauts : monde 60 + détection 40 = 100


def test_calibration_file_parses_and_totals_100():
    """`data/score/params.json` (calibrage Cowork) est valide et somme monde+détection=100."""
    load_weights.cache_clear()
    w = load_weights()
    assert w.world_max + w.detection_max == 100.0
    assert w.grades  # les paliers de grade existent


# --- le faux positif coûte (le cœur de la mécanique) ------------------------------------


def test_false_positive_is_penalized():
    """Suspendre un pays loyal DOIT réduire la note, même quand le vrai traître est pris."""
    clean = mixed_score(u_final=0.6, deviants=1, caught=1, false_positives=0)
    dirty = mixed_score(u_final=0.6, deviants=1, caught=1, false_positives=1)
    assert dirty.total < clean.total
    assert dirty.detection < clean.detection


def test_suspend_everyone_is_worse_than_targeted():
    """L'exploit « suspends tout le monde » (1 traître, 4 innocents accusés) doit être
    strictement pire que la déduction ciblée — sinon la déduction ne sert à rien."""
    targeted = mixed_score(u_final=0.5, deviants=1, caught=1, false_positives=0)
    everyone = mixed_score(u_final=0.5, deviants=1, caught=1, false_positives=4)
    assert everyone.total < targeted.total
    assert everyone.detection == 0.0  # les faux positifs effacent la détection gagnée


# --- deux traîtres, aucun raté ----------------------------------------------------------


def test_two_deviants_both_caught_full_detection():
    s = mixed_score(u_final=0.7, deviants=2, caught=2, false_positives=0)
    assert s.detection == W.detection_max  # les deux pris, sans bavure → détection pleine
    assert s.deviants == 2 and s.caught == 2


@pytest.mark.parametrize("d", [1, 2])
def test_no_traitor_missed_is_full_detection(d):
    """« Aucun raté » (caught == deviants) = détection pleine, quel que soit le nombre."""
    s = mixed_score(u_final=0.5, deviants=d, caught=d, false_positives=0)
    assert s.detection == W.detection_max


def test_partial_catch_two_deviants_is_half_detection():
    s = mixed_score(u_final=0.5, deviants=2, caught=1, false_positives=0)
    assert s.detection == pytest.approx(W.detection_max / 2)


# --- le traître raté = manque à gagner --------------------------------------------------


def test_missed_traitor_is_missed_gain():
    missed = mixed_score(u_final=0.5, deviants=1, caught=0, false_positives=0)
    caught = mixed_score(u_final=0.5, deviants=1, caught=1, false_positives=0)
    assert missed.detection == 0.0  # rien démasqué → zéro détection
    assert missed.total < caught.total  # le monde est identique : seul le manque compte


# --- l'état du monde --------------------------------------------------------------------


def test_world_component_tracks_u_final_and_is_bounded():
    assert mixed_score(u_final=0.15, deviants=1, caught=1, false_positives=0).world == 0.0
    assert mixed_score(u_final=0.05, deviants=1, caught=1, false_positives=0).world == 0.0
    top = mixed_score(u_final=0.85, deviants=1, caught=1, false_positives=0)
    assert top.world == W.world_max
    assert mixed_score(u_final=0.99, deviants=1, caught=1, false_positives=0).world == W.world_max
    mid = mixed_score(u_final=0.5, deviants=1, caught=0, false_positives=0)
    assert mid.world == pytest.approx(W.world_max * (0.5 - 0.15) / (0.85 - 0.15))


def test_total_equals_world_plus_detection_exactly():
    """Invariant de surface : la note affichée = la barre monde + la barre détection
    (pas d'écart d'arrondi entre le total et ses composantes)."""
    for u, d, c, fp in [(0.62, 1, 1, 0), (0.5, 2, 1, 0), (0.37, 2, 2, 1), (0.71, 1, 0, 0)]:
        s = mixed_score(u_final=u, deviants=d, caught=c, false_positives=fp)
        assert s.detection is not None
        assert s.total == round(s.world + s.detection, 1)


def test_total_is_clamped_even_with_miscalibrated_weights():
    """La note reste dans [0,100] même si un calibrage Cowork casse la convention
    monde+détection=100 (garde-fou, pas seulement la convention du fichier)."""
    bad = ScoreWeights(world_max=70, detection_max=40)  # somme 110 : mal calibré
    s = mixed_score(u_final=1.0, deviants=1, caught=1, false_positives=0, weights=bad)
    assert s.total == 100.0


def test_total_is_bounded_0_100():
    best = mixed_score(u_final=1.0, deviants=1, caught=1, false_positives=0)
    assert best.total == 100.0
    worst = mixed_score(u_final=0.0, deviants=2, caught=0, false_positives=5)
    assert worst.total == 0.0


# --- rôle sans détection (Spectateur / Architecte) --------------------------------------


def test_non_detector_is_scored_on_world_only_not_punished():
    """Un Spectateur ne dépose pas de motion : sa note se réduit à l'état du monde
    (détection ABSENTE, pas un faux 0 punitif)."""
    spec = mixed_score(u_final=0.85, deviants=1, caught=0, false_positives=0, detects=False)
    assert spec.detection is None
    assert spec.total == 100.0  # monde au sommet → 100, sans être puni de n'avoir rien pris
    # Un joueur-détective qui, lui, ne prend rien, marque MOINS (le manque à gagner).
    player = mixed_score(u_final=0.85, deviants=1, caught=0, false_positives=0, detects=True)
    assert player.total < spec.total


def test_non_detector_world_bar_matches_the_total_on_100():
    """Fix — la barre « monde » du Spectateur doit se lire sur la même échelle que le
    titre : sinon on afficherait « 30 / 60 » à côté de « 50 / 100 »."""
    for u in (0.85, 0.5, 0.2):
        s = mixed_score(u_final=u, deviants=1, caught=0, false_positives=0, detects=False)
        assert s.world == s.total  # même valeur…
        assert s.world_max == 100.0  # …et même échelle que le total


def test_grade_exposes_a_stable_language_neutral_slug():
    """Fix — la note de fin expose un SLUG de grade (i18n côté front), pas seulement un
    label FR qui fuirait tel quel dans l'UI anglaise."""
    def slug(u: float, caught: int = 1) -> str:
        return mixed_score(u_final=u, deviants=1, caught=caught, false_positives=0).grade_slug

    assert slug(1.0) == "diplomate"
    assert slug(0.6) == "stratege"
    assert slug(0.4) == "conseiller"
    assert slug(0.15, caught=0) == "depasse"


def test_victory_threshold_is_a_calibrated_default():
    """Fix — la victoire est désormais fondée sur la note mixte ≥ un seuil (source de
    vérité unique, valable tous rôles)."""
    assert ScoreWeights().victory_threshold == 55.0
    assert load_weights().victory_threshold == 55.0


# --- robustesse -------------------------------------------------------------------------


def test_caught_is_clamped_to_deviants():
    """Un caught aberrant (> deviants) ne fait pas exploser la détection."""
    s = mixed_score(u_final=0.5, deviants=1, caught=5, false_positives=0)
    assert s.caught == 1
    assert s.detection == W.detection_max


def test_zero_deviants_is_safe():
    """Cas dégénéré (aucun traître) : pas de division par zéro, détection nulle."""
    s = mixed_score(u_final=0.5, deviants=0, caught=0, false_positives=0)
    assert s.detection == 0.0
    assert 0.0 <= s.total <= 100.0


def test_score_exposes_component_maxima_for_the_surface():
    """Les barres monde/détection en surface se dimensionnent sur ces maxima (pas de
    pondération codée en dur côté front)."""
    s = mixed_score(u_final=0.5, deviants=1, caught=1, false_positives=0)
    assert s.world_max == W.world_max and s.detection_max == W.detection_max


def test_grades_follow_thresholds():
    top = mixed_score(u_final=1.0, deviants=1, caught=1, false_positives=0)
    assert top.grade == "Grand Diplomate"
    low = mixed_score(u_final=0.15, deviants=1, caught=0, false_positives=0)
    assert low.total == 0.0 and low.grade == "Dépassé par les événements"
