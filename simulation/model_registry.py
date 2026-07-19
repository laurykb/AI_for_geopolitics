"""Registre scientifique des modèles et inventaire Ollama local non bloquant."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from pydantic import BaseModel, Field

_PANEL_PATH = Path(__file__).resolve().parent.parent / "data" / "research" / "model_panel.json"
_BENCHMARK_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "research" / "hardware_benchmark.json"
)


class ResearchModel(BaseModel):
    tag: str
    family: str
    parameter_tier: str
    expected_size_gb: float
    role: str
    source: str
    known_digest: str = ""
    installed: bool = False
    local_digest: str = ""
    local_size_bytes: int = 0
    modified_at: str = ""
    benchmark_status: str = "unmeasured"
    benchmark_wall_time_s: float = 0.0
    benchmark_load_time_s: float = 0.0
    benchmark_warm_run_s: float = 0.0
    benchmark_tokens_per_second: float = 0.0
    benchmark_prompt_version: str = ""


class HardwareProfile(BaseModel):
    gpu: str
    vram_mib: int
    execution_policy: str
    scientific_limit: str


class ModelPanel(BaseModel):
    schema_version: int
    reviewed_on: str
    hardware_profile: HardwareProfile
    comparison_rules: list[str] = Field(default_factory=list)
    models: list[ResearchModel] = Field(default_factory=list)
    ollama_available: bool = False


@lru_cache(maxsize=1)
def load_model_panel() -> ModelPanel:
    data = json.loads(_PANEL_PATH.read_text(encoding="utf-8"))
    return ModelPanel.model_validate(data)


def ollama_inventory(url: str = "http://127.0.0.1:11434/api/tags") -> dict[str, dict]:
    """Retourne tag -> métadonnées ; une installation absente donne simplement {}."""

    try:
        with urlopen(url, timeout=0.75) as response:  # noqa: S310 - boucle locale fixe par défaut
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, URLError, TimeoutError, json.JSONDecodeError):
        return {}
    return {
        str(item.get("name", "")): item
        for item in payload.get("models", [])
        if isinstance(item, dict) and item.get("name")
    }


def model_panel_view() -> ModelPanel:
    panel = load_model_panel().model_copy(deep=True)
    inventory = ollama_inventory()
    benchmark = json.loads(_BENCHMARK_PATH.read_text(encoding="utf-8"))
    benchmark_by_tag = {
        str(row.get("tag", "")): row
        for row in benchmark.get("models", [])
        if isinstance(row, dict) and row.get("tag")
    }
    benchmark_prompt = str(benchmark.get("method", {}).get("prompt_version", ""))
    panel.ollama_available = bool(inventory)
    for model in panel.models:
        local = inventory.get(model.tag)
        if not local:
            continue
        model.installed = True
        model.local_digest = str(local.get("digest", ""))
        model.local_size_bytes = int(local.get("size", 0) or 0)
        model.modified_at = str(local.get("modified_at", ""))
        measured = benchmark_by_tag.get(model.tag)
        if measured and str(measured.get("digest", "")) == model.local_digest:
            model.benchmark_status = str(measured.get("status", "unmeasured"))
            model.benchmark_wall_time_s = float(measured.get("wall_time_s", 0.0) or 0.0)
            model.benchmark_load_time_s = float(measured.get("load_time_s", 0.0) or 0.0)
            model.benchmark_warm_run_s = float(measured.get("warm_run_estimate_s", 0.0) or 0.0)
            model.benchmark_tokens_per_second = float(
                measured.get("generation_tokens_per_second", 0.0) or 0.0
            )
            model.benchmark_prompt_version = benchmark_prompt
    return panel


def estimate_experiment_seconds(model_tags: list[str], runs_per_model: int) -> float | None:
    """Estimation conservatrice fondée sur le smoke test local du digest exact."""

    models = {model.tag: model for model in model_panel_view().models}
    selected = [models.get(tag) for tag in model_tags]
    if not selected or any(
        model is None or model.benchmark_status != "schema_valid" for model in selected
    ):
        return None
    return sum(
        model.benchmark_load_time_s + model.benchmark_warm_run_s * runs_per_model
        for model in selected
        if model is not None
    )
