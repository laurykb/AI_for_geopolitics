"""API des sources — d'où vient chaque attribut de chaque pays (onglet Informations).

Expose la chaîne de provenance P4 telle quelle : `data/sources/indicators.json`
(valeurs brutes + source par indicateur) et les valeurs **dérivées** du jeu, calculées
par les mêmes fonctions que le build reproductible (`ingestion.build`, vérifiable via
`python -m ingestion.build --check`). Aucune valeur n'est ressaisie ici : si le build
change, l'onglet change avec lui.
"""

from __future__ import annotations

from functools import lru_cache

from fastapi import APIRouter
from pydantic import BaseModel, Field

from ingestion.build import build_all, load_indicators
from ingestion.normalize import GII_TOTAL
from simulation.alliances import AllianceInfo, load_alliances
from simulation.grudges import load_gamefeel_params

router = APIRouter(prefix="/api", tags=["sources"])

# Formules de normalisation (docs/data_governance.md §3) — décrites pour l'affichage.
TRANSFORMATIONS: dict[str, str] = {
    "technology_level": (
        f"1 − (rang GII − 1) / {GII_TOTAL - 1} : rang 1 (meilleur) → 1,0 ; rang {GII_TOTAL} → 0,0"
    ),
    "political_stability": "percentile WGI / 100",
    "trade_dependency": "commerce (% du PIB) / 100, plafonné à 1",
}

BUILD_COMMAND = "python -m ingestion.build --check"


class AttributeSource(BaseModel):
    """Une ligne de l'onglet : un attribut du jeu, sa valeur, sa donnée brute, sa source."""

    key: str  # clé de l'indicateur dans `provenance` ("" si non renseignée)
    label: str  # libellé du jeu
    game_value: float | bool
    raw_value: float | bool | None = None  # donnée brute si différente de la valeur jeu
    raw_unit: str = ""  # unité de la donnée brute (%, % du PIB, rang, USD…)
    transformation: str = ""  # clé dans TRANSFORMATIONS si une formule s'applique


class CountrySources(BaseModel):
    id: str
    name: str
    attributes: list[AttributeSource]
    profile: dict  # rivaux, système, idéologie, priorités (profil analyste)
    # Attribut à part entière, DÉRIVÉ du registre sourcé (data/sources/alliances.json).
    alliances: list[str] = Field(default_factory=list)


class SourcesView(BaseModel):
    provenance: dict[str, dict]  # indicateur -> {source, year?, note?, of?}
    transformations: dict[str, str]
    build_command: str
    countries: list[CountrySources] = Field(default_factory=list)
    # Registre des accords/traités réels : tag -> {name, domain, basis, url, members…}.
    alliances: dict[str, AllianceInfo] = Field(default_factory=dict)
    # G18 — barème d'escalade du juge (transparence des règles, comme la provenance) :
    # {weights, score_floor, score_ceiling, reciprocal_multiplier, source}.
    judge_rubric: dict = Field(default_factory=dict)


def _country_rows(country, raw: dict) -> list[AttributeSource]:
    """Les attributs du jeu d'un pays, alignés sur leurs indicateurs sources."""
    return [
        AttributeSource(key="gdp", label="PIB", game_value=country.economy.gdp, raw_unit="USD"),
        AttributeSource(
            key="growth_pct",
            label="Croissance",
            game_value=country.economy.growth,
            raw_unit="%",
        ),
        AttributeSource(
            key="trade_pct",
            label="Dépendance commerciale",
            game_value=country.economy.trade_dependency,
            raw_value=raw["trade_pct"],
            raw_unit="% du PIB",
            transformation="trade_dependency",
        ),
        AttributeSource(
            key="defense_budget",
            label="Budget défense",
            game_value=country.military.defense_budget,
            raw_unit="USD",
        ),
        AttributeSource(
            key="",  # statut public, pas d'indicateur chiffré dans provenance
            label="Puissance nucléaire",
            game_value=country.military.nuclear_power,
        ),
        AttributeSource(
            key="projection",
            label="Projection militaire",
            game_value=country.military.projection,
        ),
        AttributeSource(
            key="wgi_stability_percentile",
            label="Stabilité politique",
            game_value=country.political_stability,
            raw_value=raw["wgi_stability_percentile"],
            raw_unit="percentile",
            transformation="political_stability",
        ),
        AttributeSource(
            key="gii_rank",
            label="Niveau technologique",
            game_value=country.technology_level,
            raw_value=raw["gii_rank"],
            raw_unit=f"rang / {GII_TOTAL}",
            transformation="technology_level",
        ),
        AttributeSource(
            key="oil_dependency",
            label="Dépendance pétrolière",
            game_value=country.resources.oil_dependency,
        ),
        AttributeSource(
            key="energy_independence",
            label="Indépendance énergétique",
            game_value=country.resources.energy_independence,
        ),
        AttributeSource(key="compute", label="Compute (M6)", game_value=country.compute),
    ]


@lru_cache(maxsize=1)
def _sources_view() -> SourcesView:
    indicators = load_indicators()
    built = build_all()
    countries = [
        CountrySources(
            id=cid,
            name=entry["name"],
            attributes=_country_rows(built[cid], entry["raw"]),
            profile=entry["profile"],
            alliances=built[cid].alliances,
        )
        for cid, entry in sorted(indicators["countries"].items())
    ]
    kahn = load_gamefeel_params().kahn
    return SourcesView(
        provenance=indicators["provenance"],
        transformations=TRANSFORMATIONS,
        build_command=BUILD_COMMAND,
        countries=countries,
        alliances=load_alliances(),
        judge_rubric={
            "weights": kahn.weights,
            "score_floor": kahn.score_floor,
            "score_ceiling": kahn.score_ceiling,
            "reciprocal_multiplier": kahn.reciprocal_multiplier,
            "source": "Rivera et al., FAccT 2024 (arXiv 2401.03408)",
        },
    )


@router.get("/sources", response_model=SourcesView)
def sources() -> SourcesView:
    """La provenance de chaque attribut pays : brut, source, transformation, valeur jeu."""
    return _sources_view()
