"""Tests des normalisations d'indicateurs (formules data_governance.md §3)."""

from ingestion.normalize import (
    stability_from_wgi_percentile,
    tech_level_from_gii,
    trade_dependency_from_pct,
)


def test_tech_level_from_gii():
    assert tech_level_from_gii(1) == 1.0  # 1er -> 1.0
    assert tech_level_from_gii(3) == 0.98  # USA
    assert tech_level_from_gii(86) == 0.36  # Égypte
    assert tech_level_from_gii(133) == 0.0  # dernier -> 0.0


def test_trade_dependency_from_pct():
    assert trade_dependency_from_pct(25) == 0.25
    assert trade_dependency_from_pct(70) == 0.70
    assert trade_dependency_from_pct(150) == 1.0  # plafonné


def test_stability_from_wgi_percentile():
    assert stability_from_wgi_percentile(45) == 0.45
    assert stability_from_wgi_percentile(12) == 0.12
