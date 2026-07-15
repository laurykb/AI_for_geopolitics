/** G23 — vue pure de l'analyse psycholinguistique (Dossier G4).
 *
 * Transforme le rapport backend (jauges + alertes harbinger) en lignes prêtes à
 * afficher. Le caveat d'honnêteté — « signal historique faible (~57 %) — un indice,
 * pas une preuve » — est OBLIGATOIRE : `buildAnalysisView` l'inclut toujours (testé),
 * le composant n'a aucun chemin pour l'omettre. */

import type { HarbingerAlert, IntelAnalysis } from "@/lib/types";

export const ANALYSIS_GAUGES = [
  { gauge: "sentiment", labelKey: "intel.analyse.sentiment" },
  { gauge: "politeness", labelKey: "intel.analyse.politesse" },
  { gauge: "future", labelKey: "intel.analyse.futur" },
] as const;

export type AnalysisRow = {
  gauge: string;
  labelKey: string;
  value: number; // jauge de la fenêtre courante, bornée [0, 1]
  delta: number | null; // écart vs fenêtre précédente (null en début de partie)
};

export type AnalysisView = {
  rows: AnalysisRow[];
  alerts: string[]; // libellés dédupliqués, prêts à afficher
  caveat: string; // toujours présent — un indice, pas une preuve
  rounds: number[]; // rounds de parole couverts par la fenêtre
};

const clamp01 = (x: number) => Math.max(0, Math.min(1, x));

/** « Rupture de ton détectée envers <pays> » — ou générale si aucun destinataire. */
export function alertLabel(
  alert: HarbingerAlert,
  t: (key: string) => string,
  countryLabel: (id: string) => string,
): string {
  return alert.towards
    ? `${t("intel.analyse.alerte")} ${countryLabel(alert.towards)}`
    : t("intel.analyse.alerte-generale");
}

export function buildAnalysisView(
  analysis: IntelAnalysis,
  t: (key: string) => string,
  countryLabel: (id: string) => string,
): AnalysisView {
  const rows = ANALYSIS_GAUGES.map(({ gauge, labelKey }) => {
    const value = clamp01(analysis.gauges[gauge]);
    const previous = analysis.previous ? clamp01(analysis.previous[gauge]) : null;
    return { gauge, labelKey, value, delta: previous === null ? null : value - previous };
  });
  // Plusieurs jauges peuvent chuter envers le même pays : un seul libellé par cible.
  const alerts = [...new Set(analysis.alerts.map((a) => alertLabel(a, t, countryLabel)))];
  return { rows, alerts, caveat: t("intel.analyse.caveat"), rounds: analysis.rounds };
}
