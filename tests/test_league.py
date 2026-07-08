"""Points de ligue (G11-c §2) — formule LP, plancher, forfait, plafond débutant, rangs.

Logique PURE (aucun état de partie) : les 4 cas de la spec (gain / perte / plancher /
forfait) + le plafond Diplomate du mode Débutant + la progression P du pays du joueur.
Les paramètres (K, poids, multiplicateurs) vivent dans data/gamefeel/params.json.
"""

from simulation.league import (
    FORFEIT_LP,
    apply_delta,
    country_progress,
    lp_delta,
    rank_for,
)

# --- formule de gain/perte (§2) -------------------------------------------------


def test_gain_positif_monde_et_pays():
    # U 0,50 → 0,68 (Δ+0,18), P +0,20, Intermédiaire (M=1) :
    # 100 × (0,6×0,18 + 0,4×0,20) × 1 = 18,8 → 19.
    assert lp_delta(0.50, 0.68, 0.20, "intermediate") == 19


def test_perte_quand_le_monde_recule():
    # U 0,60 → 0,45 (Δ−0,15), P −0,10, Intermédiaire : négatif.
    got = lp_delta(0.60, 0.45, -0.10, "intermediate")
    assert got < 0
    assert got == round(100 * (0.6 * -0.15 + 0.4 * -0.10) * 1.0)


def test_multiplicateur_de_difficulte():
    # Même partie, Expert (×1,5) rapporte plus que Débutant (×0,5).
    debutant = lp_delta(0.50, 0.68, 0.20, "beginner")
    expert = lp_delta(0.50, 0.68, 0.20, "expert")
    assert expert > debutant
    assert expert == round(18.8 * 1.5)
    assert debutant == round(18.8 * 0.5)


def test_p_borne_a_plus_moins_un_demi():
    # Un pays qui explose ne compte pas plus que +0,5 (borne §2).
    fort = lp_delta(0.50, 0.50, 5.0, "intermediate")  # P énorme
    borne = lp_delta(0.50, 0.50, 0.5, "intermediate")
    assert fort == borne


# --- plancher & forfait ---------------------------------------------------------


def test_plancher_zero():
    # Le total ne descend jamais sous 0, même sur une grosse perte.
    assert apply_delta(10, -50, "intermediate") == 0
    assert apply_delta(0, -15, "intermediate") == 0


def test_forfait_retire_quinze():
    assert FORFEIT_LP == -15
    assert apply_delta(100, FORFEIT_LP, "expert") == 85


def test_gain_normal_sadditionne():
    assert apply_delta(100, 19, "intermediate") == 119


# --- plafond Débutant (anti-farm, §2) -------------------------------------------


def test_debutant_plafonne_au_rang_diplomate():
    # En Débutant, un gain ne fait pas passer au-dessus de Diplomate (< Ambassadeur 450).
    assert apply_delta(445, 30, "beginner") == 449  # gain rogné au plafond
    # Déjà au-dessus (via Expert) : un gain Débutant n'ajoute rien, mais ne rabaisse pas.
    assert apply_delta(600, 30, "beginner") == 600
    # Une perte en Débutant s'applique normalement.
    assert apply_delta(300, -20, "beginner") == 280


# --- progression du pays (P, §2) ------------------------------------------------


def test_country_progress_moyenne_des_variations():
    before = {"stability": 0.5, "economy": 0.5, "technology": 0.5, "energy": 0.5}
    after = {"stability": 0.6, "economy": 0.6, "technology": 0.6, "energy": 0.6}
    # +20 % sur chaque indice → P = +0,20.
    assert country_progress(before, after) == 0.20


def test_country_progress_borne_et_recul():
    before = {"stability": 0.5, "economy": 0.5, "technology": 0.5, "energy": 0.5}
    worse = {"stability": 0.4, "economy": 0.4, "technology": 0.4, "energy": 0.4}
    assert country_progress(before, worse) < 0
    # Effondrement d'un indice depuis ~0 : la moyenne reste bornée à [−0,5, +0,5].
    boom = {"stability": 0.05, "economy": 0.5, "technology": 0.5, "energy": 0.5}
    huge = {"stability": 1.0, "economy": 0.5, "technology": 0.5, "energy": 0.5}
    assert -0.5 <= country_progress(boom, huge) <= 0.5


# --- rangs (§2) -----------------------------------------------------------------


def test_rank_thresholds():
    assert rank_for(0)[0] == "Attaché"
    assert rank_for(99)[0] == "Attaché"
    assert rank_for(100)[0] == "Émissaire"
    assert rank_for(250)[0] == "Diplomate"
    assert rank_for(450)[0] == "Ambassadeur"
    assert rank_for(700)[0] == "Ministre"
    assert rank_for(1000)[0] == "Chancelier"
    assert rank_for(1400)[0] == "Éminence"
