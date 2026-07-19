"""Validation des profils pays sourcés (P4) : schéma, bornes, cohérence, gouvernance.

Verrouille la qualité des données produites en Phase 4 : tout `data/countries/*.json`
doit charger, rester dans les bornes, et référencer des pays connus. La provenance
doit être documentée dans `docs/data_governance.md`.
"""

from pathlib import Path

from core.country_state import CountryState

_DIR = Path("data/countries")
_EXPECTED_IDS = {
    # noyau mer Rouge (P4)
    "usa",
    "china",
    "france",
    "egypt",
    "iran",
    "saudi_arabia",
    # extension roster juillet 2026 (data_governance §2 bis, ajusté §2 ter :
    # danemark retiré ; turquie, israël, corée du sud ajoutées)
    "japan",
    "russia",
    "germany",
    "uk",
    "spain",
    "italy",
    "mexico",
    "brazil",
    "india",
    "south_africa",
    "australia",
    "morocco",
    "ukraine",
    "canada",
    "turkey",
    "israel",
    "south_korea",
    # extension internationale du 18 juillet 2026 (Israël était déjà présent)
    "algeria",
    "argentina",
    "democratic_republic_congo",
    "mali",
    "senegal",
    "singapore",
    "tunisia",
    "united_arab_emirates",
    # extension scientifique : les neuf puissances nucléaires du SIPRI
    "north_korea",
    "pakistan",
}


def _load_all() -> list[CountryState]:
    return [CountryState.from_json_file(p) for p in sorted(_DIR.glob("*.json"))]


def test_all_expected_countries_load():
    assert {c.id for c in _load_all()} == _EXPECTED_IDS


def test_every_country_is_selectable_by_the_game_loader():
    """Le même loader sert le lobby, le Défi du jour et les créations de partie."""
    from simulation.loader import load_world

    for country_id in _EXPECTED_IDS:
        partner = "usa" if country_id != "usa" else "france"
        world = load_world(only=[country_id, partner])
        assert set(world.countries) == {country_id, partner}


def test_core_values_are_positive():
    for c in _load_all():
        assert c.name, f"{c.id}: nom manquant"
        assert c.economy.gdp > 0, f"{c.id}: PIB non positif"
        assert c.military.defense_budget > 0, f"{c.id}: budget défense non positif"


def test_normalized_indices_within_unit_interval():
    for c in _load_all():
        indices = (
            c.economy.trade_dependency,
            c.military.projection,
            c.resources.oil_dependency,
            c.resources.energy_independence,
            c.political_stability,
            c.technology_level,
        )
        assert all(0.0 <= v <= 1.0 for v in indices), f"{c.id}: indice hors [0,1]"


def test_rivals_reference_known_countries():
    countries = _load_all()
    ids = {c.id for c in countries}
    for c in countries:
        assert set(c.rivals) <= ids, f"{c.id}: rival inconnu {set(c.rivals) - ids}"


def test_data_provenance_is_documented():
    doc = Path("docs/data_governance.md").read_text(encoding="utf-8")
    # les sources clés des champs « durs » sont citées
    assert "World Bank" in doc
    assert "SIPRI" in doc


def test_all_nine_sipri_nuclear_armed_states_are_playable():
    nuclear = {c.id for c in _load_all() if c.military.nuclear_power}
    assert nuclear == {
        "china",
        "france",
        "india",
        "israel",
        "north_korea",
        "pakistan",
        "russia",
        "uk",
        "usa",
    }
