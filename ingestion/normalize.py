"""Normalisations des indicateurs bruts vers les indices 0–1 du `CountryState`.

Formules documentées dans `docs/data_governance.md` §3. Fonctions pures et testables.
"""

from __future__ import annotations

# Nombre d'économies classées au Global Innovation Index 2024.
GII_TOTAL = 133


def tech_level_from_gii(rank: int, total: int = GII_TOTAL) -> float:
    """Rang GII (1 = meilleur) -> niveau technologique dans [0, 1]."""
    return round(1.0 - (rank - 1) / (total - 1), 2)


def trade_dependency_from_pct(trade_pct: float) -> float:
    """Commerce (% du PIB) -> dépendance commerciale dans [0, 1] (plafonnée)."""
    return round(min(trade_pct / 100.0, 1.0), 2)


def stability_from_wgi_percentile(percentile: float) -> float:
    """Rang percentile WGI Political Stability -> stabilité dans [0, 1]."""
    return round(percentile / 100.0, 2)
