"""Casting multi-modèle : inventaire figé, assignation déterministe et routage offline."""

import pytest

from inference.mock_backend import MockBackend
from inference.model_pool import routed_backends
from simulation.model_cast import ModelCastRequest, prepare_model_cast
from simulation.model_registry import HardwareProfile, ModelPanel, ResearchModel


def _panel() -> ModelPanel:
    return ModelPanel(
        schema_version=1,
        reviewed_on="2026-07-18",
        hardware_profile=HardwareProfile(
            gpu="test-gpu",
            vram_mib=8_192,
            execution_policy="sequential",
            scientific_limit="fixture",
        ),
        models=[
            ResearchModel(
                tag="model-a:4b",
                family="Model A",
                parameter_tier="4B",
                expected_size_gb=2.5,
                role="core_comparison",
                source="test",
                installed=True,
                local_digest="sha256:a",
            ),
            ResearchModel(
                tag="model-b:7b",
                family="Model B",
                parameter_tier="7B",
                expected_size_gb=4.5,
                role="capacity_comparison",
                source="test",
                installed=True,
                local_digest="sha256:b",
            ),
            ResearchModel(
                tag="model-slow:14b",
                family="Model Slow",
                parameter_tier="14B",
                expected_size_gb=9.0,
                role="slow_robustness_only",
                source="test",
                installed=True,
                local_digest="sha256:slow",
            ),
        ],
        ollama_available=True,
    )


def test_cast_is_deterministic_excludes_human_and_freezes_digests():
    request = ModelCastRequest(models=["model-a:4b", "model-b:7b"])
    kwargs = {
        "countries": ["usa", "iran", "france", "china"],
        "human_country": "france",
        "game_id": "game-fixed",
        "panel": _panel(),
    }
    first = prepare_model_cast(request, **kwargs)
    second = prepare_model_cast(request, **kwargs)

    assert first == second
    assert "france" not in first.assignments
    assert set(first.assignments) == {"usa", "iran", "china"}
    assert {model.digest for model in first.models} == {"sha256:a", "sha256:b"}
    assert first.execution_policy == "sequential_mono_gpu"
    assert first.ranked is False


def test_cast_rejects_slow_cpu_offload_model_for_classic():
    request = ModelCastRequest(models=["model-a:4b", "model-slow:14b"])
    with pytest.raises(ValueError, match="réservés au laboratoire lent"):
        prepare_model_cast(
            request,
            ["usa", "iran", "france"],
            human_country=None,
            game_id="game",
            panel=_panel(),
        )


def test_manual_cast_preserves_every_explicit_country_assignment():
    request = ModelCastRequest(
        strategy="manual",
        models=["model-a:4b", "model-b:7b"],
        assignments={
            "usa": "model-b:7b",
            "iran": "model-a:4b",
            "china": "model-b:7b",
        },
    )
    cast = prepare_model_cast(
        request,
        ["usa", "iran", "china", "france"],
        human_country="france",
        game_id="manual-cast",
        panel=_panel(),
    )

    assert cast.strategy == "manual"
    assert cast.assignments == request.assignments


def test_explicit_single_model_cast_routes_every_ai_role_to_the_selected_model():
    request = ModelCastRequest(
        strategy="manual",
        models=["model-b:7b"],
        assignments={"usa": "model-b:7b", "iran": "model-b:7b"},
        game_master_model="model-b:7b",
        judge_model="model-b:7b",
    )
    cast = prepare_model_cast(
        request,
        ["usa", "iran", "france"],
        human_country="france",
        game_id="single-model",
        panel=_panel(),
    )

    assert cast.assignments == {"iran": "model-b:7b", "usa": "model-b:7b"}
    assert cast.game_master_model == cast.judge_model == "model-b:7b"
    assert [model.tag for model in cast.models] == ["model-b:7b"]


def test_manual_cast_rejects_missing_human_and_unknown_country_assignments():
    with pytest.raises(ValueError, match="chaque pays IA"):
        prepare_model_cast(
            ModelCastRequest(
                strategy="manual",
                models=["model-a:4b", "model-b:7b"],
                assignments={"usa": "model-a:4b"},
            ),
            ["usa", "iran", "france"],
            human_country="france",
            game_id="manual-incomplete",
            panel=_panel(),
        )

    with pytest.raises(ValueError, match="absent ou humain"):
        prepare_model_cast(
            ModelCastRequest(
                strategy="manual",
                models=["model-a:4b", "model-b:7b"],
                assignments={
                    "usa": "model-a:4b",
                    "iran": "model-b:7b",
                    "france": "model-a:4b",
                },
            ),
            ["usa", "iran", "france"],
            human_country="france",
            game_id="manual-human",
            panel=_panel(),
        )


def test_offline_router_exposes_each_requested_model_tag():
    mock = MockBackend("ok")
    routes = routed_backends(mock, {"model-a:4b", "model-b:7b"})

    assert routes["model-a:4b"].model == "model-a:4b"
    assert routes["model-b:7b"].model == "model-b:7b"
    assert routes["model-a:4b"].generate("hello").text == "ok"
    assert len(mock.calls) == 1
