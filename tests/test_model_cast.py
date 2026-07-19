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
            ResearchModel(
                tag="model-r:7b",
                family="Model R",
                parameter_tier="7B",
                expected_size_gb=4.7,
                role="reasoning",
                source="test",
                installed=True,
                local_digest="sha256:r",
            ),
            ResearchModel(
                tag="model-r2:7b",
                family="Model R2",
                parameter_tier="7B",
                expected_size_gb=4.8,
                role="reasoning",
                source="test",
                installed=True,
                local_digest="sha256:r2",
            ),
            ResearchModel(
                tag="model-retired:3b",
                family="Model Retired",
                parameter_tier="3B",
                expected_size_gb=2.0,
                role="retired",
                source="test",
                installed=True,
                local_digest="sha256:retired",
            ),
        ],
        ollama_available=True,
    )


def test_cast_is_deterministic_excludes_human_and_freezes_digests():
    # Décision design 2026-07-19 (casting = pensée native) : un pays n'est incarnable
    # que par un modèle `reasoning` — la fixture utilise donc deux modèles reasoning
    # pour exercer la rotation déterministe, plutôt que les anciens généralistes.
    request = ModelCastRequest(models=["model-r:7b", "model-r2:7b"])
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
    assert {model.digest for model in first.models} == {"sha256:r", "sha256:r2"}
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
        models=["model-r:7b", "model-r2:7b"],
        assignments={
            "usa": "model-r2:7b",
            "iran": "model-r:7b",
            "china": "model-r2:7b",
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
        models=["model-r:7b"],
        assignments={"usa": "model-r:7b", "iran": "model-r:7b"},
        game_master_model="model-r:7b",
        judge_model="model-r:7b",
    )
    cast = prepare_model_cast(
        request,
        ["usa", "iran", "france"],
        human_country="france",
        game_id="single-model",
        panel=_panel(),
    )

    assert cast.assignments == {"iran": "model-r:7b", "usa": "model-r:7b"}
    assert cast.game_master_model == cast.judge_model == "model-r:7b"
    assert [model.tag for model in cast.models] == ["model-r:7b"]


def test_cast_rejects_non_reasoning_model_assigned_to_a_country():
    # Décision design 2026-07-19 (casting = pensée native) : un généraliste (rôle
    # capacity_comparison) ne peut plus incarner un pays, même en stratégie manuelle
    # explicite — le refus porte sur l'affectation RÉSOLUE, pas sur la simple présence
    # dans `models` (un modèle peut être dans le casting sans être affecté à un pays).
    with pytest.raises(ValueError, match="seul un modèle de raisonnement"):
        prepare_model_cast(
            ModelCastRequest(
                strategy="manual",
                models=["model-a:4b", "model-r:7b"],
                assignments={"usa": "model-a:4b", "iran": "model-r:7b"},
            ),
            ["usa", "iran", "france"],
            human_country="france",
            game_id="reject-generalist-country",
            panel=_panel(),
        )


def test_cast_rejects_non_reasoning_model_in_balanced_rotation():
    # Stratégie "balanced" (rotation automatique) : un généraliste mélangé aux modèles
    # de raisonnement finit forcément affecté à un pays par la rotation — refusé aussi.
    with pytest.raises(ValueError, match="seul un modèle de raisonnement"):
        prepare_model_cast(
            ModelCastRequest(models=["model-r:7b", "model-a:4b"]),
            ["usa", "iran", "france"],
            human_country=None,
            game_id="reject-generalist-balanced",
            panel=_panel(),
        )


def test_cast_allows_generalist_reserved_for_judge_and_game_master_only():
    # Le refus ne vise QUE les pays : un généraliste peut rester juge/GM tant qu'aucun
    # pays ne lui est affecté (mêmes rôles que la Dérive/Vote, jamais reasoning côté think).
    request = ModelCastRequest(
        strategy="manual",
        models=["model-r:7b", "model-a:4b"],
        assignments={"usa": "model-r:7b", "iran": "model-r:7b"},
        game_master_model="model-a:4b",
        judge_model="model-a:4b",
    )
    cast = prepare_model_cast(
        request,
        ["usa", "iran", "france"],
        human_country="france",
        game_id="generalist-judge-ok",
        panel=_panel(),
    )
    assert cast.assignments == {"usa": "model-r:7b", "iran": "model-r:7b"}
    assert cast.game_master_model == cast.judge_model == "model-a:4b"


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


def test_cast_flags_reasoning_models_for_think_activation():
    # Point 5 — un pays casté sur un modèle `reasoning` active l'option think côté
    # backend ; le drapeau est figé dans le casting (rejouable) et exposé en tags.
    # Casting manuel : model-a:4b (généraliste) reste dans le casting — ex. pour le
    # juge/GM — sans être affecté à un pays (le refus de la décision 2 ne porte que
    # sur l'affectation RÉSOLUE, jamais sur la simple présence dans `models`).
    request = ModelCastRequest(
        strategy="manual",
        models=["model-a:4b", "model-r:7b"],
        assignments={"usa": "model-r:7b", "iran": "model-r:7b", "france": "model-r:7b"},
    )
    cast = prepare_model_cast(
        request,
        ["usa", "iran", "france"],
        human_country=None,
        game_id="reasoning-cast",
        panel=_panel(),
    )
    flags = {model.tag: model.reasoning for model in cast.models}
    assert flags == {"model-a:4b": False, "model-r:7b": True}
    assert cast.reasoning_tags() == {"model-r:7b"}


def test_reasoning_tags_exclude_judge_and_game_master_roles():
    # Revue pt 5 (Critical) — le juge streame rationale/communiqué/motions vers des
    # steps PUBLICS (JudgeTokenStep, CommuniqueStep, MotionTokenStep) : un juge ou un
    # GM casté sur un modèle de raisonnement ne doit JAMAIS activer think. Seules les
    # affectations PAYS comptent pour le routage think. Deux modèles reasoning DISTINCTS
    # (depuis le pivot casting = pensée native, un pays ne peut plus être casté sur un
    # généraliste) : les pays utilisent model-r2:7b, le GM/juge model-r:7b — la preuve
    # que reasoning_tags() ignore la casquette GM/juge, pas seulement le rôle du panel.
    request = ModelCastRequest(
        strategy="manual",
        models=["model-r2:7b", "model-r:7b"],
        assignments={"usa": "model-r2:7b", "iran": "model-r2:7b"},
        game_master_model="model-r:7b",
        judge_model="model-r:7b",
    )
    cast = prepare_model_cast(
        request,
        ["usa", "iran", "france"],
        human_country="france",
        game_id="judge-reasoning",
        panel=_panel(),
    )
    assert {model.tag: model.reasoning for model in cast.models} == {
        "model-r2:7b": True,
        "model-r:7b": True,  # métadonnée honnête : c'est bien un modèle de raisonnement
    }
    assert cast.reasoning_tags() == {"model-r2:7b"}  # le GM/juge n'y figure pas


def test_offline_router_marks_reasoning_tags_with_think():
    routes = routed_backends(
        MockBackend("ok"),
        {"model-a:4b", "model-r:7b"},
        reasoning_tags={"model-r:7b"},
    )
    assert routes["model-r:7b"].think is True
    assert routes["model-a:4b"].think is False


def test_offline_router_defaults_to_no_think_for_backward_compat():
    # Rétro-compatibilité stricte : sans modèle reasoning dans le panel, rien ne change.
    routes = routed_backends(MockBackend("ok"), {"model-a:4b"})
    assert routes["model-a:4b"].think is False


def test_panel_reference_reasoning_models_are_deepseek_r1_and_qwen3():
    # Décision design 2026-07-19 (casting = pensée native) : qwen3:4b rejoint
    # deepseek-r1:7b au rôle `reasoning` — vérifié par un appel réel à l'API Ollama
    # (think:true renvoie un champ `thinking` non vide pour qwen3:4b, comme deepseek-r1).
    from simulation.model_registry import load_model_panel

    reasoning = {m.tag for m in load_model_panel().models if m.role == "reasoning"}
    assert reasoning == {"deepseek-r1:7b", "qwen3:4b"}


def test_panel_retires_the_small_generalists_from_new_selection():
    # Les généralistes 3-4B ne sont plus des candidats de jeu (pays) ni de laboratoire
    # (nouvelle expérience) — rôle `retired`, rétro-compatible : un run historique qui
    # les référence continue de s'AFFICHER (voir web/src/components/research-lab.tsx),
    # seule la sélection pour de nouvelles expériences les exclut.
    from simulation.model_registry import load_model_panel

    retired = {m.tag for m in load_model_panel().models if m.role == "retired"}
    assert retired == {"llama3.2:3b", "gemma3:4b", "phi4-mini:3.8b"}
