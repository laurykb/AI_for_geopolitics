"""Build déterministe des profils pays depuis `data/sources/indicators.json`.

CLI :
    python -m ingestion.build            # --check (défaut) : vérifie la reproductibilité
    python -m ingestion.build --write    # (re)génère data/countries/*.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from core.country_state import CountryState, Economy, Military, Resources
from ingestion.normalize import (
    stability_from_wgi_percentile,
    tech_level_from_gii,
    trade_dependency_from_pct,
)
from simulation.alliances import AllianceInfo, load_alliances, memberships

SOURCES_FILE = Path("data/sources/indicators.json")
COUNTRIES_DIR = Path("data/countries")


def load_indicators(path: str | Path = SOURCES_FILE) -> dict:
    """Charge les indicateurs sourcés (entrées brutes + provenance)."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def build_country(
    country_id: str, entry: dict, alliances: dict[str, AllianceInfo] | None = None
) -> CountryState:
    """Assemble un `CountryState` à partir d'une entrée d'indicateurs.

    `alliances` (registre sourcé) dérive l'attribut du même nom depuis les adhésions
    réelles ; sans registre, on retombe sur le codage du profil (compat tests).
    """
    raw = entry["raw"]
    profile = entry["profile"]
    return CountryState(
        id=country_id,
        name=entry["name"],
        economy=Economy(
            gdp=raw["gdp"],
            growth=raw["growth_pct"],
            trade_dependency=trade_dependency_from_pct(raw["trade_pct"]),
        ),
        military=Military(
            defense_budget=raw["defense_budget"],
            nuclear_power=raw["nuclear_power"],
            projection=raw["projection"],
        ),
        resources=Resources(
            oil_dependency=raw["oil_dependency"],
            energy_independence=raw["energy_independence"],
        ),
        alliances=(
            memberships(country_id, alliances)
            if alliances is not None
            else profile.get("alliances", [])
        ),
        rivals=profile["rivals"],
        political_system=profile["political_system"],
        political_stability=stability_from_wgi_percentile(raw["wgi_stability_percentile"]),
        technology_level=tech_level_from_gii(raw["gii_rank"]),
        compute=raw["compute"],  # M6 : capacité de calcul (le « pétrole » de l'ère IA)
        ideology=profile["ideology"],
        strategic_priorities=profile["strategic_priorities"],
    )


def build_all(path: str | Path = SOURCES_FILE) -> dict[str, CountryState]:
    """Construit tous les pays : indicateurs sourcés + alliances dérivées du registre."""
    indicators = load_indicators(path)
    alliances = load_alliances()
    return {
        cid: build_country(cid, entry, alliances)
        for cid, entry in indicators["countries"].items()
    }


def _check() -> int:
    """Vérifie que chaque data/countries/*.json est reproductible depuis les sources."""
    built = build_all()
    mismatches: list[str] = []
    for cid, country in sorted(built.items()):
        committed_path = COUNTRIES_DIR / f"{cid}.json"
        if not committed_path.exists():
            mismatches.append(f"{cid}: fichier committé manquant")
            continue
        if CountryState.from_json_file(committed_path) != country:
            mismatches.append(f"{cid}: divergence build vs committé")

    if mismatches:
        print("ÉCHEC reproductibilité :")
        for m in mismatches:
            print(f"  - {m}")
        return 1
    print(f"OK : {len(built)} profils reproductibles depuis {SOURCES_FILE}")
    return 0


def _write() -> int:
    """(Re)génère les data/countries/*.json depuis les sources (JSON canonique)."""
    COUNTRIES_DIR.mkdir(parents=True, exist_ok=True)
    built = build_all()
    for cid, country in sorted(built.items()):
        path = COUNTRIES_DIR / f"{cid}.json"
        payload = country.model_dump()
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"écrit {path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Build des profils pays depuis les sources.")
    parser.add_argument(
        "--write", action="store_true", help="(re)génère data/countries/*.json (sinon : --check)"
    )
    args = parser.parse_args()
    return _write() if args.write else _check()


if __name__ == "__main__":
    raise SystemExit(main())
