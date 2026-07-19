import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import {
  completeCountryAssignments,
  CountryModelAssignments,
  ModelCastSelector,
} from "./model-cast-selector";

describe("ModelCastSelector", () => {
  it("rend le dialogue multi-modèle et les rôles du casting en Campagne", () => {
    const html = renderToStaticMarkup(
      createElement(ModelCastSelector, {
        models: [
          {
            tag: "model-a:4b",
            family: "Model A",
            parameter_tier: "4b",
            expected_size_gb: 3,
            role: "core_comparison",
            source: "test",
            installed: true,
            local_digest: "sha-a",
            known_digest: "",
            local_size_bytes: 1,
            modified_at: "",
            benchmark_status: "schema_valid",
            benchmark_wall_time_s: 2,
            benchmark_tokens_per_second: 12,
            benchmark_warm_run_s: 1,
            benchmark_load_time_s: 1,
            benchmark_prompt_version: "test",
          },
          {
            tag: "model-b:7b",
            family: "Model B",
            parameter_tier: "7b",
            expected_size_gb: 5,
            role: "core_comparison",
            source: "test",
            installed: true,
            local_digest: "sha-b",
            known_digest: "",
            local_size_bytes: 1,
            modified_at: "",
            benchmark_status: "unmeasured",
            benchmark_wall_time_s: 0,
            benchmark_tokens_per_second: 0,
            benchmark_warm_run_s: 0,
            benchmark_load_time_s: 0,
            benchmark_prompt_version: "test",
          },
        ],
        enabled: true,
        selected: ["model-a:4b", "model-b:7b"],
        onEnabled: () => undefined,
        onSelected: () => undefined,
        context: "campaign",
      }),
    );

    expect(html).toContain("Faire dialoguer plusieurs modèles");
    expect(html).toContain("Pays IA");
    expect(html).toContain("Game Master");
    expect(html).toContain("model-b:7b");
    expect(html).toContain('data-tour="model-cast"');
  });

  it("rend un sélecteur explicite quand le mode reste mono-modèle", () => {
    const model = {
      tag: "model-b:7b",
      family: "Model B",
      parameter_tier: "7b",
      expected_size_gb: 5,
      role: "core_comparison",
      source: "test",
      installed: true,
      local_digest: "sha-b",
      known_digest: "",
      local_size_bytes: 1,
      modified_at: "",
      benchmark_status: "unmeasured",
      benchmark_wall_time_s: 0,
      benchmark_tokens_per_second: 0,
      benchmark_warm_run_s: 0,
      benchmark_load_time_s: 0,
      benchmark_prompt_version: "test",
    };
    const html = renderToStaticMarkup(
      createElement(ModelCastSelector, {
        models: [model],
        enabled: false,
        selected: [model.tag],
        onEnabled: () => undefined,
        onSelected: () => undefined,
        context: "classic",
      }),
    );

    expect(html).toContain("Modèle unique de la partie");
    expect(html).toContain("model-b:7b");
    expect(html).toContain('aria-label="Modèle unique de la partie"');
  });
});

describe("CountryModelAssignments", () => {
  it("complète le casting, exclut le pays humain et permet le choix par pays", () => {
    expect(
      completeCountryAssignments(
        ["usa", "france", "iran"],
        ["model-a:4b", "model-b:7b"],
        { usa: "model-b:7b" },
        "france",
      ),
    ).toEqual({ iran: "model-a:4b", usa: "model-b:7b" });

    const html = renderToStaticMarkup(
      createElement(CountryModelAssignments, {
        countries: ["usa", "france", "iran"],
        humanCountry: "france",
        selectedModels: ["model-a:4b", "model-b:7b"],
        assignments: { usa: "model-b:7b", iran: "model-a:4b" },
        onAssignments: () => undefined,
      }),
    );
    expect(html).toContain("Quelle IA incarne quel pays ?");
    expect(html).toContain("Modèle de États-Unis");
    expect(html).toContain("joué par l’humain");
    expect(html).toContain('data-tour="model-assignments"');
  });
});
