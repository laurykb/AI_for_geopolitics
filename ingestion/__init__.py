"""Ingestion reproductible des profils pays (Phase 4).

Build déterministe et offline : `data/sources/indicators.json` (entrées sourcées) ->
`CountryState` via des normalisations documentées (`docs/data_governance.md` §3).

Importer depuis les sous-modules (`from ingestion.build import build_all`) ; l'`__init__`
reste léger pour éviter un double-chargement lors de `python -m ingestion.build`.
"""
