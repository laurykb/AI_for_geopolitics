"""Tests du build d'ingestion : reproductibilité des profils pays depuis les sources."""

from pathlib import Path

from core.country_state import CountryState
from ingestion.build import COUNTRIES_DIR, build_all, load_indicators

_EXPECTED_IDS = {"usa", "china", "france", "egypt", "iran", "saudi_arabia"}


def test_indicators_cover_all_countries_with_provenance():
    indicators = load_indicators()
    assert set(indicators["countries"]) == _EXPECTED_IDS
    assert indicators["provenance"]  # provenance documentée, non vide
    # chaque source clé est tracée
    for field in ("gdp", "defense_budget", "gii_rank", "trade_pct"):
        assert indicators["provenance"][field]["source"]


def test_build_reproduces_committed_country_files():
    built = build_all()
    assert set(built) == _EXPECTED_IDS
    for cid, country in built.items():
        committed = CountryState.from_json_file(Path(COUNTRIES_DIR) / f"{cid}.json")
        assert country == committed, f"{cid}: le build ne reproduit pas le fichier committé"
