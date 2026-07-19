export type ForecastBranch = {
  id: number;
  option: string;
  responses: string;
  outcome: string;
  utility: number | null;
  confidence: number | null;
};

export type ScenarioPlan = {
  branches: ForecastBranch[];
  selected: number | null;
  selectionReason: string;
  uncertainty: string;
};

function boundedScore(value: string | undefined): number | null {
  const parsed = Number.parseFloat(value ?? "");
  return Number.isFinite(parsed) ? Math.max(0, Math.min(100, parsed)) : null;
}

/** Parse le résumé de scénarios demandé aux modèles. Échec tolérant : l'ancienne
 * réflexion reste affichable si un petit modèle ne suit pas encore le format. */
export function parseScenarioPlan(text: string): ScenarioPlan | null {
  const branches: ForecastBranch[] = [];
  let selected: number | null = null;
  let selectionReason = "";
  let uncertainty = "";
  for (const rawLine of text.split(/\r?\n/)) {
    const line = rawLine.trim().replace(/^[-*]+\s*/, "");
    const branchMatch = line.match(/^FUTUR\s+(\d+)\s*\|/i);
    if (branchMatch) {
      const fields = line.split("|").slice(1).map((field) => field.trim());
      const value = (label: string) =>
        fields.find((field) => field.toLowerCase().startsWith(`${label}:`))?.split(":").slice(1).join(":").trim() ?? "";
      branches.push({
        id: Number(branchMatch[1]),
        option: value("option"),
        responses: value("réponses prévues") || value("reponses prevues"),
        outcome: value("issue"),
        utility: boundedScore(value("utilité") || value("utilite")),
        confidence: boundedScore(value("confiance")),
      });
      continue;
    }
    const choice = line.match(/^CHOIX\s*\|\s*FUTUR\s+(\d+)(?:\s*\|\s*motif:\s*(.*))?/i);
    if (choice) {
      selected = Number(choice[1]);
      selectionReason = choice[2]?.trim() ?? "";
      continue;
    }
    const doubt = line.match(/^INCERTITUDE\s*\|\s*(.*)/i);
    if (doubt) uncertainty = doubt[1].trim();
  }
  return branches.length >= 2
    ? { branches, selected, selectionReason, uncertainty }
    : null;
}
