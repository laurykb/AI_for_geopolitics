"""Casting multi-modèle reproductible pour les parties classiques.

Le casting est préparé une fois à la création de la partie, puis stocké dans le
``WorldState`` snapshoté. Les tags ne suffisent pas : le digest Ollama exact est figé afin
qu'une reprise ou un replay puisse expliquer quelle version incarnait chaque pays.
"""

from __future__ import annotations

from hashlib import sha256
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, model_validator

from simulation.model_registry import ModelPanel, model_panel_view

ModelTag = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]


class ModelCastRequest(BaseModel):
    """Choix volontaire du lobby, avec un ou plusieurs modèles explicitement nommés."""

    strategy: Literal["balanced", "manual"] = "balanced"
    models: list[ModelTag] = Field(min_length=1, max_length=4)
    assignments: dict[str, ModelTag] = Field(default_factory=dict, max_length=32)
    game_master_model: ModelTag | None = None
    judge_model: ModelTag | None = None

    @model_validator(mode="after")
    def validate_cast(self) -> ModelCastRequest:
        if len(set(self.models)) != len(self.models):
            raise ValueError("chaque modèle du casting doit être unique")
        selected = set(self.models)
        if self.strategy == "balanced" and self.assignments:
            raise ValueError("les affectations explicites exigent la stratégie manual")
        unknown_models = sorted(set(self.assignments.values()) - selected)
        if unknown_models:
            raise ValueError(
                "chaque modèle affecté à un pays doit appartenir au casting : "
                + ", ".join(unknown_models)
            )
        for role, tag in (
            ("Game Master", self.game_master_model),
            ("juge", self.judge_model),
        ):
            if tag is not None and tag not in selected:
                raise ValueError(f"le modèle du {role} doit appartenir au casting")
        return self


class CastModel(BaseModel):
    tag: str
    family: str
    digest: str
    size_gb: float
    benchmark_status: str = "unmeasured"
    warm_run_s: float = 0.0
    load_time_s: float = 0.0


class ModelCastState(BaseModel):
    """Casting figé et sérialisé avec le monde vivant."""

    strategy: Literal["balanced", "manual"] = "balanced"
    models: list[CastModel] = Field(default_factory=list)
    assignments: dict[str, str] = Field(default_factory=dict)
    game_master_model: str
    judge_model: str
    max_models_in_memory: int = 1
    execution_policy: str = "sequential_mono_gpu"
    ranked: bool = False


def prepare_model_cast(
    request: ModelCastRequest,
    countries: list[str],
    *,
    human_country: str | None,
    game_id: str,
    panel: ModelPanel | None = None,
) -> ModelCastState:
    """Valide l'inventaire puis fige une affectation automatique ou explicitement choisie."""

    panel = panel or model_panel_view()
    available = {model.tag: model for model in panel.models if model.installed}
    missing = [tag for tag in request.models if tag not in available]
    if missing:
        raise ValueError(f"modèles Ollama indisponibles : {', '.join(missing)}")

    selected = [available[tag] for tag in request.models]
    too_large = [model.tag for model in selected if model.role == "slow_robustness_only"]
    if too_large:
        raise ValueError(
            "modèles réservés au laboratoire lent sur 8 Go de VRAM : " + ", ".join(too_large)
        )
    without_digest = [model.tag for model in selected if not model.local_digest]
    if without_digest:
        raise ValueError(f"digest Ollama introuvable : {', '.join(without_digest)}")

    ai_countries = sorted(country for country in countries if country != human_country)
    if len(ai_countries) < len(selected):
        raise ValueError("le casting contient plus de modèles que de pays joués par une IA")

    if request.strategy == "manual":
        unknown_countries = sorted(set(request.assignments) - set(ai_countries))
        if unknown_countries:
            raise ValueError(
                "affectation interdite pour un pays absent ou humain : "
                + ", ".join(unknown_countries)
            )
        missing_countries = sorted(set(ai_countries) - set(request.assignments))
        if missing_countries:
            raise ValueError(
                "une affectation manuelle est requise pour chaque pays IA : "
                + ", ".join(missing_countries)
            )
        assignments = {country: request.assignments[country] for country in ai_countries}
    else:
        # La rotation évite de donner systématiquement le premier modèle au même pays, tout
        # en restant parfaitement reproductible depuis l'id de partie et le manifeste.
        offset = int(sha256(f"{game_id}:model-cast".encode()).hexdigest()[:8], 16) % len(selected)
        assignments = {
            country: selected[(index + offset) % len(selected)].tag
            for index, country in enumerate(ai_countries)
        }
    game_master = request.game_master_model or selected[0].tag
    judge = request.judge_model or selected[-1].tag
    return ModelCastState(
        strategy=request.strategy,
        models=[
            CastModel(
                tag=model.tag,
                family=model.family,
                digest=model.local_digest,
                size_gb=model.expected_size_gb,
                benchmark_status=model.benchmark_status,
                warm_run_s=model.benchmark_warm_run_s,
                load_time_s=model.benchmark_load_time_s,
            )
            for model in selected
        ],
        assignments=assignments,
        game_master_model=game_master,
        judge_model=judge,
    )
