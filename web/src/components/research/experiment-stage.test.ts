import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { ExperimentProtocol } from "@/lib/types";
import { SettingsProvider } from "@/components/settings-provider";

import { ExperimentStage } from "./experiment-stage";

const protocol: ExperimentProtocol = {
  id: "test-v1",
  title: "Hypothèse test",
  research_question: "La pression change-t-elle la décision ?",
  repetitions_per_cell: 30,
  pilot_repetitions_per_cell: 5,
  pilot_factor_selection: {},
  execution_mode: "automated",
  scenario_premise: "Alpha et Bêta négocient sous contrôle du Game Master.",
  actors: ["Alpha · puissance A", "Bêta · puissance B", "Game Master"],
  hypotheses: ["effet de pression"],
  scenario_beats: [
    {
      round_no: 1,
      title: "Ouverture",
      game_master_event: "Le marché ouvre.",
      inter_round_activity: "Les IA prévoient l'action adverse.",
      measurement: "Prévision et confiance",
    },
    {
      round_no: 2,
      title: "Verdict",
      game_master_event: "Les actions sont révélées.",
      inter_round_activity: "Le juge compare signal et action.",
      measurement: "Écart signal-action",
    },
  ],
  conclusion_rule: "Comparer les cellules après toutes les répétitions.",
  factors: [
    {
      id: "pressure",
      label: "Pression",
      randomized: true,
      levels: [
        { id: "low", label: "Faible", value: "low", hypothesis_only: false },
        { id: "high", label: "Forte", value: "high", hypothesis_only: false },
      ],
    },
  ],
  outcomes: [
    {
      id: "choice",
      label: "Choix",
      description: "L'option retenue par le modèle lors de la décision finale.",
      kind: "category",
      primary: true,
      unit: "",
    },
  ],
  controls: ["Même scénario", "Même espace d'action"],
  stopping_rules: ["Terminer les répétitions"],
  caveats: [],
};

describe("ExperimentStage", () => {
  it("rend la question, le Game Master, les acteurs et l'activité inter-round", () => {
    const html = renderToStaticMarkup(
      createElement(
        SettingsProvider,
        null,
        createElement(ExperimentStage, { protocol }),
      ),
    );
    expect(html).toContain("La pression change-t-elle la décision ?");
    expect(html).toContain("Game Master");
    expect(html).toContain("États-Unis");
    expect(html).toContain("Chine");
    expect(html).toContain("Les IA prévoient l&#x27;action adverse.");
    expect(html).toContain("Prévision et confiance");
    expect(html).toContain("Théâtre du sommet");
    expect(html).toContain("Boîte de verre");
    expect(html).toContain("Zoomer la carte du laboratoire");
  });

  it("marque fortement l'aperçu comme un exemple, sans donnée réelle (CETaS anti-sur-confiance)", () => {
    const html = renderToStaticMarkup(
      createElement(SettingsProvider, null, createElement(ExperimentStage, { protocol })),
    );
    expect(html).toContain("EXEMPLE");
    expect(html).toContain("aucune donnée réelle");
  });

  it("ne marque plus « EXEMPLE » une fois une vraie répétition exécutée", () => {
    const sample = {
      model_id: "deepseek-r1:7b",
      factors: { pressure: "high" },
      repetition: 1,
      round_records: [
        {
          round_no: 1,
          event_seen: "Le marché ouvre.",
          forecast: "Bêta cède sous 2 tours.",
          public_signal: "Alpha annonce la fermeté.",
          chosen_action: "signal_only",
          activity_response: "Bêta proteste publiquement.",
          escalation_level: 120,
        },
      ],
      opponent_model_id: "",
      strategic_turns: [],
      strategic_metrics: null,
      game_winner: "",
      game_end_reason: "",
      final_balance: null,
      trace: null,
    };
    const html = renderToStaticMarkup(
      createElement(
        SettingsProvider,
        null,
        createElement(ExperimentStage, { protocol, sample }),
      ),
    );
    expect(html).not.toContain("EXEMPLE");
  });
});
