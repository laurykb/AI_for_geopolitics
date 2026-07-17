"""RG-2 — mapping des modes (resserrement à classic|campaign + drapeaux composables)."""

from simulation.game_mode import BASE_MODES, from_legacy_mode, normalize_stored


def test_base_modes_are_two():
    assert BASE_MODES == ("classic", "campaign")


def test_legacy_mapping_is_faithful():
    assert from_legacy_mode("classic") == _flags("classic", False, False, False)
    assert from_legacy_mode("drift") == _flags("classic", False, False, True)
    assert from_legacy_mode("fog") == _flags("classic", True, False, False)
    assert from_legacy_mode("escalation") == _flags("classic", False, True, False)
    # crisis : simple libellé — la comparaison à l'Histoire vit sur crisis_id, pas le mode.
    assert from_legacy_mode("crisis") == _flags("classic", False, False, False)
    assert from_legacy_mode("campaign") == _flags("campaign", False, False, False)


def test_legacy_unknown_falls_back_to_classic():
    assert from_legacy_mode("mystère") == _flags("classic", False, False, False)


def test_new_game_uses_columns():
    # Partie créée après le resserrement : mode de base + colonnes = vérité.
    flags = normalize_stored("classic", fog=True, escalation=False, drift_enabled=False)
    assert flags == _flags("classic", True, False, False)
    flags = normalize_stored("classic", fog=True, escalation=True, drift_enabled=True)
    assert flags == _flags("classic", True, True, True)


def test_old_drift_game_maps_to_classic_plus_drift():
    # Ancienne partie Dérive : le libellé fait foi (colonnes absentes → défauts False).
    assert normalize_stored("drift") == _flags("classic", False, False, True)


def test_old_fog_and_escalation_map_to_flags():
    assert normalize_stored("fog") == _flags("classic", True, False, False)
    assert normalize_stored("escalation") == _flags("classic", False, True, False)


def test_old_non_drift_mode_never_wakes_drift():
    # Vieille partie fog restaurée avec une colonne drift_enabled bruitée (défaut 1 des
    # bases héritées) : la Dérive NE doit PAS se rallumer.
    assert normalize_stored("fog", drift_enabled=True).drift is False
    assert normalize_stored("escalation", drift_enabled=True).drift is False
    assert normalize_stored("crisis", drift_enabled=True).drift is False


def test_campaign_recognised_by_scenario_or_mode():
    assert normalize_stored("classic", scenario="campaign:c1").mode == "campaign"
    assert normalize_stored("campaign").mode == "campaign"
    assert normalize_stored("classic", scenario="red_sea").mode == "classic"
    # Un ancien chapitre de campagne stocké en mode « fog » reste une Campagne + brouillard.
    flags = normalize_stored("fog", scenario="campaign:c2")
    assert flags == _flags("campaign", True, False, False)


def _flags(mode, fog, escalation, drift):
    from simulation.game_mode import GameFlags

    return GameFlags(mode=mode, fog=fog, escalation=escalation, drift=drift)
