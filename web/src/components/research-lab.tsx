"use client";

import { useEffect, useMemo, useState } from "react";

import { Hint } from "@/components/hint";
import {
  completeCountryAssignments,
  CountryModelAssignments,
} from "@/components/model-cast-selector";
import { ExperimentStage } from "@/components/research/experiment-stage";
import { SelectMap } from "@/components/select-map";
import { Banner, Panel, PanelTitle, Pill, Spinner, TextInput } from "@/components/ui";
import { ROSTER, speakerMeta } from "@/lib/countries";
import {
  cancelLabExperiment,
  cloneLabExperiment,
  createLabExperiment,
  getNextHumanTrial,
  getLabExperiment,
  humanizeError,
  labExportUrl,
  listLabExperiments,
  startLabExperiment,
  submitHumanTrial,
} from "@/lib/api";
import type {
  CampaignLabView,
  ExperimentProgress,
  ExperimentProtocol,
  ExperimentRecord,
  ExperimentView,
  HumanTrialSubmission,
  HumanTrialView,
  ResearchModel,
  ScenarioCountryEligibility,
} from "@/lib/types";

// "protocole figé" fait écho au CTA "Figer le protocole" (spec §3.2) : plus de "pré-enregistrée",
// jargon d'un CTA qui n'existe plus dans l'interface.
export const STATUS_LABELS: Record<string, string> = {
  queued: "protocole figé",
  running: "en cours",
  completed: "terminée",
  failed: "terminée avec erreurs",
  cancelled: "annulée",
};

// Libellés sans jargon (spec refonte labo §3.3) : chacun dit CE QUE le modèle représente
// dans le protocole, pas seulement sa taille ou son statut technique.
export const ROLE_LABELS: Record<string, string> = {
  core_comparison: "panel principal",
  capacity_comparison: "palier 7-8B (comparaison historique)",
  reasoning: "raisonnement natif (candidat frontière)",
  slow_robustness_only: "grand modèle, voie lente (contre-vérification)",
  retired: "retiré du panel (runs historiques lisibles)",
};

// Décision design 2026-07-19 (« la pensée native est la denrée que le jeu évalue ») —
// la sélection d'une NOUVELLE expérience ne propose que les candidats plausibles au rôle
// d'« IA frontière » : raisonnement natif, ou la voie lente existante (gpt-oss/magistral).
// Les généralistes retraités (`retired`) et les paliers de capacité (`capacity_comparison`,
// ex. mistral) en sont exclus — mais un run HISTORIQUE reste lisible quel que soit le
// modèle : ce filtre ne touche que la proposition de candidats, jamais l'affichage d'un
// résultat déjà enregistré (résolu via la liste `installed`, non filtrée, ailleurs ici).
const FRONTIER_CANDIDATE_ROLES = new Set(["reasoning", "slow_robustness_only"]);

export function frontierCandidateModels(models: ResearchModel[]): ResearchModel[] {
  return models.filter((model) => FRONTIER_CANDIDATE_ROLES.has(model.role));
}

const FEATURED_PROTOCOL_ID = "ai-arms-dyadic-tournament-v1";
// Le stepper EST le cycle d'une expérience (spec refonte labo §2 et §3.0) : chaque étape porte
// le nom du temps du cycle qu'elle incarne, pas un intitulé d'écran indépendant.
export const LAB_STEPS = [
  { id: "intro", label: "Comprendre", detail: "La question en une minute", tour: "lab-loop" },
  {
    id: "hypothesis",
    label: "Question & protocole",
    detail: "Hypothèse, facteurs, pilote ou complet",
    tour: "lab-protocol",
  },
  {
    id: "casting",
    label: "Casting",
    detail: "qui joue, contre qui — le reste est gelé",
    tour: "lab-casting",
  },
  { id: "theatre", label: "Théâtre", detail: "boîte de verre", tour: "lab-stage" },
  {
    id: "results",
    label: "Résultat & limites",
    detail: "Verdict, preuves et limites",
    tour: "lab-results",
  },
] as const;
type LabStep = (typeof LAB_STEPS)[number]["id"];

// Glossaire au point d'usage (spec refonte labo §3.0) : une bulle « ? » par terme, jamais un
// bloc <details> séparé du contexte où le mot apparaît. Une définition en une phrase chacun.
const GLOSSARY = {
  cellule: "Une combinaison précise des variables testées.",
  repetition: "La même cellule rejouée pour mesurer sa variabilité.",
  seed: "Le numéro qui permet de rejouer exactement les mêmes tirages aléatoires.",
  digest: "L'empreinte exacte de la version locale d'un modèle.",
  manifeste: "Le plan et les seeds figés avant le lancement, pour ne pas tricher ensuite.",
  icWilson: "Un intervalle qui encadre un taux avec 95 % de confiance, fiable même à petit n.",
  pilote: "Un essai à effectif réduit : une direction possible, pas encore une preuve.",
  paireOrdonnee: "Un même duo de modèles joué dans les deux sens : qui commence Alpha, qui Bêta.",
  selfPlay: "Un modèle joué contre lui-même, pour mesurer sa tendance propre sans effet adverse.",
  echangeDeCamps: "Chaque modèle joue tour à tour Alpha et Bêta, pour séparer l'effet du modèle de celui du rôle.",
  adversaireGele: "Les profils pays, les forces et les seeds restent identiques ; seul le casting testé varie.",
  verdict: "La lecture prudente du résultat : ce qu'on peut et ne peut pas en conclure à ce stade.",
} as const;

export function preferredLabProtocol(protocols: ExperimentProtocol[]): ExperimentProtocol | undefined {
  return (
    protocols.find((protocol) => protocol.id === FEATURED_PROTOCOL_ID) ??
    protocols.find((protocol) => protocol.execution_mode === "automated") ??
    protocols[0]
  );
}

function isDyadic(protocol: ExperimentProtocol): boolean {
  return protocol.id === "ai-arms-dyadic-tournament-v1";
}

export type LabPlanMode = "pilot" | "complete";

/** Choix explicite Pilote/Plan complet (spec refonte labo §3.2 « fin du piège du pilote »).
 * Remplace l'ancienne présélection silencieuse au premier niveau : le pilote applique
 * désormais le préréglage DÉCLARÉ par le protocole (`pilot_factor_selection`, données pures
 * côté backend) et le plan complet coche systématiquement tous les niveaux. Un facteur absent
 * du préréglage pilote garde tous ses niveaux — jamais une réduction inventée côté front. */
export function planSelection(
  protocol: ExperimentProtocol | undefined,
  mode: LabPlanMode,
): Record<string, string[]> {
  if (!protocol) return {};
  return Object.fromEntries(
    protocol.factors.map((factor) => {
      const allLevels = factor.levels.map((level) => level.id);
      if (mode === "complete") return [factor.id, allLevels];
      const preset = protocol.pilot_factor_selection?.[factor.id];
      return [factor.id, preset && preset.length > 0 ? preset : allLevels];
    }),
  );
}

function cellsOf(
  protocol: ExperimentProtocol,
  selection: Record<string, string[]> = {},
): number {
  return protocol.factors.reduce((total, factor) => {
    const selected = selection[factor.id];
    return total * (selected?.length || factor.levels.length);
  }, 1);
}

type EffectiveCountryEligibility = {
  alpha: { label: string; description: string; countries: string[] };
  beta: { label: string; description: string; countries: string[] };
  notes: string[];
};

function intersectCountryLists(rules: ScenarioCountryEligibility[], role: "alpha" | "beta") {
  if (!rules.length) return [...ROSTER];
  return [
    ...rules
      .map((rule) => new Set(rule[role].countries))
      .reduce((left, right) => new Set([...left].filter((country) => right.has(country)))),
  ];
}

export function effectiveCountryEligibility(
  protocol: ExperimentProtocol,
  selection: Record<string, string[]>,
): EffectiveCountryEligibility {
  const scenarioFactor = protocol.factors.find((factor) => factor.id === "scenario");
  const selectedIds = selection.scenario ?? scenarioFactor?.levels.map((level) => level.id) ?? [];
  const scenarioValues = new Set(
    scenarioFactor?.levels
      .filter((level) => selectedIds.includes(level.id))
      .map((level) => String(level.value)) ?? [],
  );
  const rules = (protocol.country_eligibility ?? []).filter(
    (rule) => rule.scenario_id === "*" || scenarioValues.has(rule.scenario_id),
  );
  const describe = (role: "alpha" | "beta") => ({
    label: [...new Set(rules.map((rule) => rule[role].label))].join(" + ") || "Tous les pays",
    description:
      [...new Set(rules.map((rule) => rule[role].description))].join(" · ") ||
      "Aucune restriction supplémentaire pour ce protocole.",
    countries: intersectCountryLists(rules, role),
  });
  return {
    alpha: describe("alpha"),
    beta: describe("beta"),
    notes: [...new Set(rules.map((rule) => rule.pairing_note))],
  };
}

function shortDigest(model: ResearchModel): string {
  return (model.local_digest || model.known_digest || "digest inconnu").slice(0, 12);
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${Math.ceil(seconds)} s`;
  if (seconds < 3_600) return `${Math.ceil(seconds / 60)} min`;
  return `${(seconds / 3_600).toFixed(seconds < 36_000 ? 1 : 0)} h`;
}

/** Phase du cycle affichée explicitement sur l'écran Exécution (spec refonte labo §3.4) :
 * Protocole figé → En cours (x/N runs) → Terminé : lire le résultat. Renvoie les 3 étapes,
 * chacune avec un indicateur "active" pour mettre en évidence la phase courante. */
export function executionCyclePhases(progress: ExperimentProgress): [string, boolean][] {
  const attempted = progress.completed + progress.failed;
  const terminal = ["completed", "failed", "cancelled"].includes(progress.experiment.status);
  const running = !terminal && (progress.experiment.status === "running" || attempted > 0);
  return [
    ["Protocole figé", !terminal && !running],
    [`En cours (${attempted.toLocaleString("fr-FR")}/${progress.total.toLocaleString("fr-FR")} runs)`, running],
    ["Terminé : lire le résultat", terminal],
  ];
}

function ExperimentLoop({ protocol }: { protocol: ExperimentProtocol }) {
  const dyadic = isDyadic(protocol);
  // Les intitulés sont EXACTEMENT ceux du stepper (spec refonte labo §3.1) : la boucle
  // affichée ici et la navigation à 5 écrans ne doivent plus jamais diverger.
  const steps = LAB_STEPS.map((step) => [step.label, step.detail] as const);

  return (
    <div data-tour="lab-loop">
    <Panel className="overflow-hidden border-accent/35 bg-[linear-gradient(110deg,rgba(99,102,241,0.10),transparent_55%)]">
      <PanelTitle
        kicker="1 · Comprendre"
        title="Le cycle en 5 temps, identique pour toutes les expériences"
        right={<Pill tone="accent">{dyadic ? "6 appels IA / tour" : `${protocol.scenario_beats?.length ?? 0} rounds`}</Pill>}
      />
      <p className="mb-4 max-w-4xl text-sm leading-relaxed text-fg-muted">
        {dyadic
          ? "Ce protocole rend visible la mécanique centrale du projet : anticiper plusieurs réponses possibles, choisir celle qui sert le mieux son objectif, puis confronter cette prédiction à la décision réellement observée."
          : protocol.research_question}
      </p>
      <ol className="grid gap-2 md:grid-cols-5" aria-label="Cycle de l’expérience sélectionnée">
        {steps.map(([label, detail], index) => (
          <li
            key={label}
            className="relative rounded-lg border border-edge bg-background/45 px-3 py-3 md:min-h-28"
          >
            <div className="flex items-center gap-2">
              <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-accent/15 font-mono text-[11px] font-semibold text-accent-bright">
                {index + 1}
              </span>
              <p className="text-xs font-semibold uppercase tracking-wide text-foreground">
                {label}
              </p>
            </div>
            <p className="mt-2 text-xs leading-relaxed text-fg-muted">{detail}</p>
            {index < steps.length - 1 && (
              <span
                aria-hidden="true"
                className="absolute -right-2 top-1/2 z-10 hidden -translate-y-1/2 text-accent-bright md:block"
              >
                →
              </span>
            )}
          </li>
        ))}
      </ol>
    </Panel>
    </div>
  );
}

function LabJourney({
  current,
  onStep,
  hasResults,
}: {
  current: LabStep;
  onStep: (step: LabStep) => void;
  hasResults: boolean;
}) {
  const currentIndex = LAB_STEPS.findIndex((step) => step.id === current);
  return (
    <Panel className="sticky top-2 z-30 overflow-hidden border-accent/35 bg-surface/95 shadow-lg backdrop-blur" data-lab-journey="true">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-accent-bright">
            Cycle de l&apos;expérience
          </p>
          <p className="mt-0.5 text-xs text-fg-muted">Une décision par écran, vos choix restent mémorisés.</p>
        </div>
        <Pill tone="accent">étape {currentIndex + 1}/5</Pill>
      </div>
      <nav className="grid gap-2 sm:grid-cols-5" aria-label="Étapes du Laboratoire">
        {LAB_STEPS.map((step, index) => {
          const selected = step.id === current;
          const disabled = step.id === "results" && !hasResults;
          return (
            <button
              key={step.id}
              type="button"
              data-tour={step.tour}
              aria-current={selected ? "step" : undefined}
              disabled={disabled}
              onClick={() => onStep(step.id)}
              className={`rounded-lg border px-3 py-2 text-left transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${
                selected
                  ? "border-accent bg-accent/12 text-foreground"
                  : index < currentIndex
                    ? "border-good/35 bg-good/5 text-fg-muted hover:border-good/60"
                    : "border-edge bg-surface-2/35 text-fg-muted hover:border-edge-strong"
              }`}
            >
              <span className="flex items-center gap-2 text-xs font-semibold">
                <span className={`grid h-5 w-5 place-items-center rounded-full font-mono text-[10px] ${
                  index < currentIndex ? "bg-good/15 text-good" : "bg-muted text-fg-faint"
                }`}>
                  {index < currentIndex ? "✓" : index + 1}
                </span>
                {step.label}
              </span>
              <span className="mt-1 hidden text-[10px] text-fg-faint lg:block">{step.detail}</span>
            </button>
          );
        })}
      </nav>
    </Panel>
  );
}

function LabJourneyFooter({
  current,
  onStep,
  hasResults,
}: {
  current: LabStep;
  onStep: (step: LabStep) => void;
  hasResults: boolean;
}) {
  const currentIndex = LAB_STEPS.findIndex((step) => step.id === current);
  const previous = LAB_STEPS[currentIndex - 1];
  const next = LAB_STEPS[currentIndex + 1];
  const nextDisabled = next?.id === "results" && !hasResults;
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-edge bg-surface-2/35 p-3">
      {previous ? (
        <button
          type="button"
          onClick={() => onStep(previous.id)}
          className="rounded-md border border-edge px-3 py-2 text-xs font-semibold text-fg-muted hover:border-edge-strong hover:text-foreground"
        >
          ← {previous.label}
        </button>
      ) : <span />}
      <p className="text-center text-[11px] text-fg-faint">
        {nextDisabled ? "Les résultats s’ouvrent dès qu’une expérience existe." : LAB_STEPS[currentIndex]?.detail}
      </p>
      {next ? (
        <button
          type="button"
          disabled={nextDisabled}
          onClick={() => onStep(next.id)}
          className="rounded-md border border-accent bg-accent/12 px-3 py-2 text-xs font-semibold text-accent-bright hover:bg-accent/20 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {next.label} →
        </button>
      ) : <span />}
    </div>
  );
}

export function ResearchLab({ lab }: { lab: CampaignLabView }) {
  const featured = preferredLabProtocol(lab.protocols);
  const [protocolId, setProtocolId] = useState(featured?.id ?? "");
  const protocol = lab.protocols.find((item) => item.id === protocolId) ?? lab.protocols[0];
  // `installed` reste NON filtré par rôle : le badge « Modèles disponibles » et la
  // résolution des tags d'une expérience HISTORIQUE (clone, estimation de durée) doivent
  // continuer de reconnaître n'importe quel modèle du panel, retraité ou non.
  const installed = lab.model_panel.models.filter((model) => model.installed);
  const candidateModels = frontierCandidateModels(lab.model_panel.models);
  const recommendedModels = candidateModels.filter(
    (model) => model.installed && model.role === "reasoning",
  );
  const advancedModels = candidateModels.filter(
    (model) => !recommendedModels.some((recommended) => recommended.tag === model.tag),
  );
  const defaultModels = (
    recommendedModels.length
      ? recommendedModels
      : candidateModels.filter((model) => model.installed)
  )
    .slice(0, 4)
    .map((model) => model.tag);
  const [models, setModels] = useState<string[]>(defaultModels);
  const [actorCountries, setActorCountries] = useState<string[]>(["usa", "iran"]);
  const [castingRole, setCastingRole] = useState<"alpha" | "beta">("alpha");
  const [countryAssignments, setCountryAssignments] = useState<Record<string, string>>({});
  const [castingMode, setCastingMode] = useState<"fixed" | "matrix">("fixed");
  // Pilote par défaut, mais toujours affiché et modifiable explicitement (spec §3.2) : la
  // trappe corrigée est l'ABSENCE d'indication, pas le choix pilote lui-même.
  const [planMode, setPlanMode] = useState<LabPlanMode>("pilot");
  const [repetitions, setRepetitions] = useState(protocol?.pilot_repetitions_per_cell ?? 5);
  const [factorSelection, setFactorSelection] = useState<Record<string, string[]>>(() =>
    planSelection(protocol, "pilot"),
  );
  const [includeSelfPlay, setIncludeSelfPlay] = useState(false);
  const [active, setActive] = useState<ExperimentView | null>(null);
  const [history, setHistory] = useState<ExperimentRecord[]>([]);
  const [busy, setBusy] = useState<
    "prepare" | "start" | "human" | "clone" | "cancel" | null
  >(null);
  const [error, setError] = useState<string | null>(null);
  const [humanTrial, setHumanTrial] = useState<HumanTrialView | null>(null);
  const [humanDebrief, setHumanDebrief] = useState<
    (HumanTrialSubmission & { choice: "verify" | "execute" }) | null
  >(null);
  const [labStep, setLabStep] = useState<LabStep>("intro");
  const countryEligibility = useMemo(
    () =>
      protocol
        ? effectiveCountryEligibility(protocol, factorSelection)
        : {
            alpha: { label: "Alpha", description: "", countries: [...ROSTER] },
            beta: { label: "Bêta", description: "", countries: [...ROSTER] },
            notes: [],
          },
    [factorSelection, protocol],
  );
  const actorCastReady =
    actorCountries.length === 2 &&
    actorCountries[0] !== actorCountries[1] &&
    countryEligibility.alpha.countries.includes(actorCountries[0] ?? "") &&
    countryEligibility.beta.countries.includes(actorCountries[1] ?? "");
  const activeCountryRule = countryEligibility[castingRole];
  const otherActorCountry = actorCountries[castingRole === "alpha" ? 1 : 0];
  const activeEligibleCountries = activeCountryRule.countries.filter(
    (country) => country !== otherActorCountry,
  );

  const goLabStep = (step: LabStep) => {
    setLabStep(step);
    window.requestAnimationFrame(() => {
      document.querySelector('[data-lab-journey="true"]')?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    });
  };

  useEffect(() => {
    listLabExperiments().then(setHistory).catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!active?.worker_running && active?.progress.experiment.status !== "running") return;
    const timer = window.setInterval(() => {
      getLabExperiment(active.progress.experiment.id)
        .then((view) => {
          setActive(view);
          if (["completed", "failed", "cancelled"].includes(view.progress.experiment.status)) {
            listLabExperiments().then(setHistory).catch(() => undefined);
          }
        })
        .catch((err) => setError(humanizeError(err)));
    }, 2_500);
    return () => window.clearInterval(timer);
  }, [active?.progress.experiment.id, active?.progress.experiment.status, active?.worker_running]);

  const executionModels = useMemo(() => {
    if (!protocol || !isDyadic(protocol) || castingMode !== "fixed") return models;
    const assignments = completeCountryAssignments(
      actorCountries,
      models,
      countryAssignments,
    );
    return [...new Set(Object.values(assignments))];
  }, [actorCountries, castingMode, countryAssignments, models, protocol]);

  const planned = useMemo(
    () => {
      if (!protocol) return 0;
      const cells = cellsOf(protocol, factorSelection) * repetitions;
      if (protocol.execution_mode !== "automated") return cells;
      if (!isDyadic(protocol)) return cells * models.length;
      const pairs =
        castingMode === "fixed"
          ? 1
          : models.length === 1
          ? 1
          : models.length * (models.length - (includeSelfPlay ? 0 : 1));
      return cells * pairs;
    },
    [castingMode, factorSelection, includeSelfPlay, models.length, protocol, repetitions],
  );
  const plannedModelCalls = useMemo(() => {
    if (!protocol || !isDyadic(protocol)) return planned;
    const turnFactor = protocol.factors.find((factor) => factor.id === "turn_limit");
    const selectedTurns = turnFactor?.levels.filter((level) =>
      factorSelection.turn_limit?.includes(level.id),
    ) ?? [];
    const turnSum = selectedTurns.reduce((total, level) => total + Number(level.value), 0);
    const turnLevelCount = Math.max(1, selectedTurns.length);
    const pairs =
      castingMode === "fixed"
        ? 1
        : models.length === 1
        ? 1
        : models.length * (models.length - (includeSelfPlay ? 0 : 1));
    const cellsWithoutTurns = cellsOf(protocol, factorSelection) / turnLevelCount;
    return cellsWithoutTurns * repetitions * pairs * 6 * (turnSum || 6);
  }, [castingMode, factorSelection, includeSelfPlay, models.length, planned, protocol, repetitions]);
  const estimatedDurationS = (() => {
    if (protocol.execution_mode !== "automated") return 0;
    const selected = executionModels.map((tag) => installed.find((model) => model.tag === tag));
    if (selected.some((model) => !model || model.benchmark_status !== "schema_valid")) return 0;
    let callsPerModel = cellsOf(protocol, factorSelection) * repetitions;
    if (isDyadic(protocol)) {
      const turnFactor = protocol.factors.find((factor) => factor.id === "turn_limit");
      const selectedTurns = turnFactor?.levels
        .filter((level) => factorSelection.turn_limit?.includes(level.id))
        .map((level) => Number(level.value)) ?? [6];
      const meanTurns =
        selectedTurns.reduce((total, value) => total + value, 0) / Math.max(1, selectedTurns.length);
      callsPerModel = (planned * 6 * meanTurns) / Math.max(1, executionModels.length);
    }
    return selected.reduce(
      (total, model) =>
        total +
        (model?.benchmark_load_time_s ?? 0) +
        (model?.benchmark_warm_run_s ?? 0) * callsPerModel,
      0,
    );
  })();

  const toggleModel = (tag: string) => {
    setModels((current) =>
      current.includes(tag) ? current.filter((item) => item !== tag) : [...current, tag],
    );
    setActive(null);
  };

  const toggleActorCountry = (country: string) => {
    setActorCountries((current) => {
      const index = castingRole === "alpha" ? 0 : 1;
      const other = current[index === 0 ? 1 : 0];
      if (country === other) return current;
      const next = [...current];
      next[index] = country;
      return next.filter(Boolean);
    });
    setActive(null);
  };

  const prepare = async () => {
    if (!protocol || models.length === 0) return;
    setBusy("prepare");
    setError(null);
    try {
      const view = await createLabExperiment({
        protocol_id: protocol.id,
        model_tags: protocol.execution_mode === "automated" ? executionModels : [],
        repetitions,
        factor_selection: factorSelection,
        include_self_play: castingMode === "matrix" && includeSelfPlay,
        actor_countries: isDyadic(protocol) ? actorCountries : undefined,
        country_assignments:
          isDyadic(protocol) && castingMode === "fixed"
            ? completeCountryAssignments(actorCountries, models, countryAssignments)
            : undefined,
      });
      setActive(view);
      setLabStep("theatre");
      setHumanTrial(null);
      setHumanDebrief(null);
      setHistory((current) => [view.progress.experiment, ...current]);
    } catch (err) {
      setError(humanizeError(err));
    } finally {
      setBusy(null);
    }
  };

  const start = async () => {
    if (!active) return;
    setBusy("start");
    setError(null);
    try {
      setActive(await startLabExperiment(active.progress.experiment.id));
    } catch (err) {
      setError(humanizeError(err));
    } finally {
      setBusy(null);
    }
  };

  const nextHumanTrial = async () => {
    if (!active) return;
    setBusy("human");
    setError(null);
    try {
      setHumanTrial(await getNextHumanTrial(active.progress.experiment.id));
      setHumanDebrief(null);
      setActive(await getLabExperiment(active.progress.experiment.id));
    } catch (err) {
      setError(humanizeError(err));
    } finally {
      setBusy(null);
    }
  };

  const decideHumanTrial = async (choice: "verify" | "execute") => {
    if (!active || !humanTrial) return;
    setBusy("human");
    setError(null);
    try {
      const submission = await submitHumanTrial(
        active.progress.experiment.id,
        humanTrial.run_id,
        choice,
      );
      setActive(submission.experiment);
      setHumanTrial(null);
      setHumanDebrief({ ...submission, choice });
    } catch (err) {
      setError(humanizeError(err));
    } finally {
      setBusy(null);
    }
  };

  const clone = async () => {
    if (!active) return;
    setBusy("clone");
    setError(null);
    try {
      const view = await cloneLabExperiment(active.progress.experiment.id);
      setActive(view);
      setHumanTrial(null);
      setHumanDebrief(null);
      setHistory((current) => [view.progress.experiment, ...current]);
    } catch (err) {
      setError(humanizeError(err));
    } finally {
      setBusy(null);
    }
  };

  const cancel = async () => {
    if (!active) return;
    setBusy("cancel");
    setError(null);
    try {
      setActive(await cancelLabExperiment(active.progress.experiment.id));
    } catch (err) {
      setError(humanizeError(err));
    } finally {
      setBusy(null);
    }
  };

  // Partagé entre le lien « Reprendre une expérience passée » de l'écran 1 et l'historique
  // de l'écran 5 : ouvrir une expérience déjà pré-enregistrée saute directement au résultat.
  const openExperiment = (experimentId: string) => {
    setHumanTrial(null);
    setHumanDebrief(null);
    getLabExperiment(experimentId)
      .then((view) => {
        setActive(view);
        goLabStep("results");
      })
      .catch((err) => setError(humanizeError(err)));
  };

  if (!protocol) return null;
  const progress = active?.progress;
  const summary = active?.summary;
  const resultProtocol =
    lab.protocols.find((item) => item.id === progress?.experiment.protocol_id) ?? protocol;
  const primaryMetricLabel =
    resultProtocol.outcomes.find((outcome) => outcome.primary)?.label ??
    (summary?.primary_metric === "appropriate_override"
      ? "Décision humaine appropriée"
      : "Emploi nucléaire");
  const stageSample =
    active?.progress.experiment.protocol_id === protocol.id ? active.samples?.[0] : null;
  const fixedAssignments = completeCountryAssignments(
    actorCountries,
    models,
    countryAssignments,
  );
  const stageAssignments = stageSample
    ? {
        [actorCountries[0] ?? "usa"]: stageSample.model_id,
        [actorCountries[1] ?? "china"]: stageSample.opponent_model_id,
      }
    : fixedAssignments;
  const completedRatio = progress && progress.total > 0 ? progress.completed / progress.total : 0;
  const canStart = Boolean(
    progress &&
      !active?.worker_running &&
      !humanTrial &&
      (progress.queued > 0 || progress.running > 0) &&
      !["completed", "failed", "cancelled"].includes(progress.experiment.status),
  );

  return (
    <div className="space-y-4">
      <LabJourney current={labStep} onStep={goLabStep} hasResults={Boolean(summary || history.length)} />
      <section hidden={labStep !== "intro"} className="space-y-4">
      <Panel className="overflow-hidden border-indigo-soft/40 bg-[radial-gradient(circle_at_top_right,rgba(99,102,241,0.16),transparent_42%)]">
        <PanelTitle
          kicker="1 · Comprendre"
          title={lab.title}
          right={<Pill tone="accent">mono-GPU · reprenable</Pill>}
        />
        <div className="grid gap-5 xl:grid-cols-[1.25fr_0.75fr]">
          <div>
            <p className="max-w-3xl text-sm leading-relaxed text-fg-muted">{lab.purpose}</p>
            <div className="mt-4 grid gap-2 sm:grid-cols-3">
              <Metric label="Protocoles" value={String(lab.protocols.length)} detail="pré-enregistrés" />
              <Metric
                label="Modèles disponibles"
                value={`${installed.length}/${lab.model_panel.models.length}`}
                detail={lab.model_panel.ollama_available ? "Ollama répond" : "Ollama hors ligne"}
              />
              <Metric
                label="Matériel"
                value={`${Math.round(lab.model_panel.hardware_profile.vram_mib / 1024)} Go VRAM`}
                detail={lab.model_panel.hardware_profile.gpu.replace("NVIDIA GeForce ", "")}
              />
            </div>
            {history.length > 0 && (
              <button
                type="button"
                onClick={() => openExperiment(history[0]!.id)}
                className="mt-4 rounded-md border border-edge px-3 py-2 text-xs font-medium text-fg-muted hover:border-edge-strong hover:text-foreground"
              >
                ↺ Reprendre une expérience passée ({history.length} pré-enregistrée
                {history.length > 1 ? "s" : ""})
              </button>
            )}
          </div>
          <div className="rounded-lg border border-edge bg-background/30 p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-fg-faint">
              Ce qu&apos;un résultat peut dire
            </p>
            <p className="mt-2 text-sm leading-relaxed text-fg-muted">
              Une réplication peut confirmer, nuancer ou ne pas reproduire un effet pour les
              versions testées. Elle ne transforme jamais une fréquence de jeu en loi sur les États.
            </p>
            <p className="mt-3 text-xs leading-relaxed text-warn">
              {lab.model_panel.hardware_profile.scientific_limit}
            </p>
          </div>
        </div>
      </Panel>

      <ExperimentLoop protocol={protocol} />
      </section>

      <div className="space-y-4">
        <div data-tour="lab-protocol" hidden={labStep !== "hypothesis"}>
        <Panel>
          <PanelTitle
            kicker="2 · Question & protocole"
            title="Choisir une carte d'expérience"
            right={
              isDyadic(protocol) ? <Pill tone="accent">expérience phare</Pill> : undefined
            }
          />
          <div className="grid gap-2 lg:grid-cols-2">
            {lab.protocols.map((item) => {
              const primary = item.outcomes.find((outcome) => outcome.primary) ?? item.outcomes[0];
              return (
              <button
                key={item.id}
                type="button"
                onClick={() => {
                  setProtocolId(item.id);
                  setPlanMode("pilot");
                  setRepetitions(item.pilot_repetitions_per_cell);
                  setFactorSelection(planSelection(item, "pilot"));
                  setIncludeSelfPlay(false);
                  setActive(null);
                  setHumanTrial(null);
                  setHumanDebrief(null);
                }}
                className={`w-full rounded-lg border p-3 text-left transition-colors ${
                  item.id === protocol.id
                    ? "border-accent bg-accent/10"
                    : "border-edge bg-surface-2/40 hover:border-edge-strong"
                }`}
              >
                <span className="flex items-start justify-between gap-2">
                  <span>
                    {isDyadic(item) && (
                      <span className="mb-1 block text-[10px] font-semibold uppercase tracking-[0.14em] text-accent-bright">
                        Nouveau · tournoi multi-rounds
                      </span>
                    )}
                    <span className="block text-sm font-semibold">{item.title}</span>
                  </span>
                  <Pill tone={item.execution_mode === "automated" ? "good" : "warn"}>
                    {item.execution_mode === "automated" ? "automatisé" : "humain requis"}
                  </Pill>
                </span>
                <span className="mt-1 block text-xs leading-relaxed text-fg-muted">
                  {item.research_question}
                </span>
                {primary && (
                  <span className="mt-1.5 flex items-center gap-1 text-[11px] text-fg-faint">
                    Mesure : {primary.label}
                    <Hint text={primary.description} />
                  </span>
                )}
              </button>
              );
            })}
          </div>

          {/* La fiche d'expérience standardisée (CETaS) : hypothèse, protocole, mesures,
              lecture attendue et limites du protocole actuellement sélectionné. */}
          <div className="mt-4 grid gap-3 rounded-lg border border-edge bg-surface-2/30 p-3 md:grid-cols-2">
            <div>
              <p className="text-xs font-semibold text-foreground">Hypothèse</p>
              <p className="mt-1 text-xs leading-relaxed text-fg-muted">
                {protocol.hypotheses[0] ?? protocol.research_question}
              </p>
            </div>
            <div>
              <p className="flex items-center gap-1 text-xs font-semibold text-foreground">
                Mesures <Hint text={GLOSSARY.icWilson} />
              </p>
              <ul className="mt-1 space-y-0.5 text-xs leading-relaxed text-fg-muted">
                {protocol.outcomes.map((outcome) => (
                  <li key={outcome.id} className="flex items-center gap-1">
                    {outcome.label}
                    <Hint text={outcome.description} />
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <p className="text-xs font-semibold text-foreground">Lecture attendue</p>
              <p className="mt-1 text-xs leading-relaxed text-fg-muted">{protocol.conclusion_rule}</p>
            </div>
            <div>
              <p className="text-xs font-semibold text-foreground">Limites</p>
              <ul className="mt-1 list-disc space-y-0.5 pl-4 text-xs leading-relaxed text-fg-faint">
                {protocol.caveats.map((caveat) => (
                  <li key={caveat}>{caveat}</li>
                ))}
              </ul>
            </div>
          </div>

          <div className="mt-4 rounded-lg border border-edge bg-surface-2/30 p-3">
            <p className="flex items-center gap-1 text-xs font-semibold text-foreground">
              Protocole <Hint text={GLOSSARY.cellule} />
            </p>
            <p className="mt-1 flex flex-wrap items-center gap-1 text-xs leading-relaxed text-fg-faint">
              Figer → Lancer → Attendre → Lire. Choisis d&apos;abord un nombre de
              répétitions <Hint text={GLOSSARY.repetition} /> : les cases à cocher plus bas
              restent disponibles pour un choix libre de niveaux.
            </p>
            <div className="mt-3 grid gap-2 sm:grid-cols-2">
              {(
                [
                  [
                    "pilot",
                    "Pilote",
                    `${protocol.pilot_repetitions_per_cell} répétitions · réponse indicative, minutes`,
                  ],
                  [
                    "complete",
                    "Plan complet",
                    `${protocol.repetitions_per_cell} répétitions · réponse avec IC, heures`,
                  ],
                ] as const
              ).map(([mode, label, detail]) => (
                <button
                  key={mode}
                  type="button"
                  aria-pressed={planMode === mode}
                  onClick={() => {
                    setPlanMode(mode);
                    setRepetitions(
                      mode === "pilot" ? protocol.pilot_repetitions_per_cell : protocol.repetitions_per_cell,
                    );
                    setFactorSelection(planSelection(protocol, mode));
                    setActive(null);
                  }}
                  className={`rounded-lg border p-3 text-left transition-colors ${
                    planMode === mode
                      ? "border-accent bg-accent/10"
                      : "border-edge bg-surface-2/40 hover:border-edge-strong"
                  }`}
                >
                  <span className="flex items-center gap-1.5 text-xs font-semibold text-foreground">
                    {label}
                    {mode === "pilot" && <Hint text={GLOSSARY.pilote} />}
                  </span>
                  <span className="mt-1 block text-[11px] leading-relaxed text-fg-faint">{detail}</span>
                </button>
              ))}
            </div>
            <p className="mt-3 text-xs text-fg-faint">Choix libre par niveau :</p>
            {protocol.factors.map((factor) => (
              <div key={factor.id} className="mt-2">
                <p className="text-xs text-fg-muted">{factor.label}</p>
                <div className="mt-1 flex flex-wrap gap-1.5">
                  {factor.levels.map((level) => {
                    const selected = factorSelection[factor.id]?.includes(level.id) ?? true;
                    return (
                    <button
                      key={level.id}
                      type="button"
                      aria-pressed={selected}
                      onClick={() => {
                        setFactorSelection((current) => {
                          const values = current[factor.id] ?? factor.levels.map((item) => item.id);
                          const next = values.includes(level.id)
                            ? values.filter((item) => item !== level.id)
                            : [...values, level.id];
                          return { ...current, [factor.id]: next.length > 0 ? next : values };
                        });
                        setActive(null);
                      }}
                      className={`rounded-full border px-2 py-1 text-[11px] transition-colors ${
                        selected
                          ? "border-accent bg-accent/10 text-accent-bright"
                          : "border-edge text-fg-faint hover:border-edge-strong"
                      }`}
                    >
                      {level.label}
                    </button>
                    );
                  })}
                </div>
              </div>
            ))}
            <p className="mt-3 text-xs text-fg-faint">
              Critère principal : {protocol.outcomes.filter((outcome) => outcome.primary).map((outcome) => outcome.label).join(", ")}
            </p>
          </div>
        </Panel>
        </div>

        <div data-tour="lab-casting" hidden={labStep !== "casting"}>
        <Panel>
          <PanelTitle kicker="3 · Casting" title="Choisir les pays et leurs modèles" />
          {/* Budget figé (NPS) en tête de panneau (spec refonte labo §3.3) : le compteur
              runs/appels/durée matérialise « toute conclusion vaut à ce budget » avant même
              de composer le casting — pas relégué en bas de page comme une case à cocher. */}
          <div className="mb-4 flex flex-wrap items-end gap-3 rounded-lg border border-edge bg-surface-2/30 p-3">
            <label className="text-xs text-fg-muted">
              <span className="flex items-center gap-1">
                Répétitions par cellule <Hint text={GLOSSARY.repetition} />
              </span>
              <TextInput
                type="number"
                min={1}
                max={300}
                value={repetitions}
                onChange={(event) => setRepetitions(Math.max(1, Math.min(300, Number(event.target.value))))}
                className="mt-1 block w-28 font-mono"
              />
            </label>
            <div className="pb-2 text-xs text-fg-muted">
              {cellsOf(protocol, factorSelection)} cellules <Hint text={GLOSSARY.cellule} /> ×{" "}
              {repetitions}
              {protocol.execution_mode === "automated" ? (
                isDyadic(protocol) ? (
                  <>
                    {" × "}
                    {castingMode === "fixed"
                      ? 1
                      : models.length === 1
                        ? 1
                        : models.length * (models.length - (includeSelfPlay ? 0 : 1))}
                    {" paires ordonnées "}
                    <Hint text={GLOSSARY.paireOrdonnee} />
                  </>
                ) : (
                  ` × ${models.length} modèles`
                )
              ) : (
                " × 1 participant"
              )}
              {" = "}
              <strong className="font-mono text-foreground">{planned.toLocaleString("fr-FR")} runs</strong>
              {isDyadic(protocol) && (
                <span className="ml-2 font-mono text-fg-faint">
                  · {plannedModelCalls.toLocaleString("fr-FR")} appels modèle maximum
                </span>
              )}
              {estimatedDurationS > 0 && (
                <span className={estimatedDurationS > 28_800 ? "ml-2 text-warn" : "ml-2 text-good"}>
                  · durée locale estimée {formatDuration(estimatedDurationS)}
                </span>
              )}
            </div>
          </div>
          <p className="mb-4 flex items-center gap-1 rounded-md border border-edge bg-surface-2/30 px-3 py-2 text-xs text-fg-muted">
            Profils pays, forces et seeds sont gelés : seul le casting varie.
            <Hint text={GLOSSARY.adversaireGele} />
          </p>
          {isDyadic(protocol) && (
            <div className="mb-5 space-y-3">
              <div>
                <p className="text-xs font-semibold text-foreground">Deux pays sur la carte</p>
                <p className="mt-1 text-xs leading-relaxed text-fg-muted">
                  Leurs attributs, alliances, rivalités et contraintes sont gelés dans le
                  manifeste puis injectés dans chaque décision du tournoi.
                </p>
              </div>
              <div className="grid gap-2 sm:grid-cols-2">
                {(["alpha", "beta"] as const).map((actor, index) => {
                  const rule = countryEligibility[actor];
                  const country = actorCountries[index];
                  const valid = Boolean(country && rule.countries.includes(country));
                  return (
                    <button
                      key={actor}
                      type="button"
                      aria-pressed={castingRole === actor}
                      onClick={() => setCastingRole(actor)}
                      className={`rounded-lg border p-3 text-left transition-colors ${
                        castingRole === actor
                          ? "border-accent bg-accent/10"
                          : "border-edge bg-surface-2/30 hover:border-edge-strong"
                      }`}
                    >
                      <span className="flex items-center justify-between gap-2 text-xs font-semibold">
                        <span>{actor.toUpperCase()} · {rule.label}</span>
                        <Pill tone={valid ? "good" : "warn"}>{valid ? "valide" : "à choisir"}</Pill>
                      </span>
                      <span className="mt-1 block text-xs text-foreground">
                        {country ? speakerMeta(country).label : "Aucun pays"}
                      </span>
                      <span className="mt-1 block text-[11px] leading-relaxed text-fg-faint">
                        {rule.description}
                      </span>
                    </button>
                  );
                })}
              </div>
              {countryEligibility.notes.length > 0 && (
                <Banner tone={actorCastReady ? "neutral" : "warn"}>
                  {countryEligibility.notes.join(" · ")}
                  {!actorCastReady && " Choisissez un casting compatible avant de pré-enregistrer."}
                </Banner>
              )}
              <SelectMap
                selected={actorCountries}
                capacity={2}
                onToggle={toggleActorCountry}
                eligible={activeEligibleCountries}
                eligibilityLabel={`${castingRole.toUpperCase()} · ${activeCountryRule.label} · ${activeEligibleCountries.length} pays compatibles`}
              />
              <div className="grid gap-2 sm:grid-cols-2">
                {([
                  ["fixed", "Théâtre assigné", "Un modèle précis par pays, comme en Classique.", null],
                  [
                    "matrix",
                    "Matrice comparative",
                    "Chaque modèle joue les deux camps, pour séparer l'effet du modèle de l'effet du rôle.",
                    GLOSSARY.echangeDeCamps,
                  ],
                ] as const).map(([value, label, detail, hint]) => (
                  <button
                    key={value}
                    type="button"
                    aria-pressed={castingMode === value}
                    onClick={() => {
                      setCastingMode(value);
                      setIncludeSelfPlay(false);
                      setActive(null);
                    }}
                    className={`rounded-lg border p-3 text-left transition-colors ${
                      castingMode === value
                        ? "border-accent bg-accent/10"
                        : "border-edge bg-surface-2/30 hover:border-edge-strong"
                    }`}
                  >
                    <span className="flex items-center gap-1 text-xs font-semibold">
                      {label}
                      {hint && <Hint text={hint} />}
                    </span>
                    <span className="mt-1 block text-[11px] leading-relaxed text-fg-faint">
                      {detail}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          )}
          <p className="mb-2 flex items-center gap-1 text-xs text-fg-muted">
            Panel recommandé pour commencer — modèles installés, comparables et adaptés à la
            machine. Chaque modèle affiche son digest <Hint text={GLOSSARY.digest} />.
          </p>
          <div className="grid gap-2 sm:grid-cols-2">
            {recommendedModels.map((model) => (
              <ModelChoice
                key={model.tag}
                model={model}
                selected={models.includes(model.tag)}
                disabled={protocol.execution_mode !== "automated"}
                onToggle={() => toggleModel(model.tag)}
              />
            ))}
          </div>
          {advancedModels.length > 0 && (
            <details className="mt-3 border-t border-edge pt-3">
              <summary className="cursor-pointer text-xs font-medium text-fg-muted hover:text-foreground">
                Modèles avancés, lents ou non installés ({advancedModels.length})
              </summary>
              <div className="mt-3 grid gap-2 sm:grid-cols-2">
                {advancedModels.map((model) => (
                  <ModelChoice
                    key={model.tag}
                    model={model}
                    selected={models.includes(model.tag)}
                    disabled={protocol.execution_mode !== "automated"}
                    onToggle={() => toggleModel(model.tag)}
                  />
                ))}
              </div>
            </details>
          )}

          {isDyadic(protocol) && castingMode === "fixed" && models.length >= 1 && (
            <div className="mt-4">
              <CountryModelAssignments
                countries={actorCountries}
                selectedModels={models}
                assignments={countryAssignments}
                onAssignments={(assignments) => {
                  setCountryAssignments(assignments);
                  setActive(null);
                }}
                compact
              />
            </div>
          )}

          {isDyadic(protocol) && castingMode === "matrix" && (
            <label className="mt-4 flex items-start gap-2 rounded-lg border border-edge bg-surface-2/30 p-3 text-xs text-fg-muted">
              <input
                type="checkbox"
                checked={includeSelfPlay}
                onChange={(event) => {
                  setIncludeSelfPlay(event.target.checked);
                  setActive(null);
                }}
                className="mt-0.5 accent-[var(--color-accent)]"
              />
              <span>
                <strong className="flex items-center gap-1 text-foreground">
                  Baseline : le modèle contre lui-même
                  <Hint text={GLOSSARY.selfPlay} />
                </strong>
                Joue aussi chaque modèle contre lui-même. Utile pour mesurer une spirale
                intrinsèque, mais augmente fortement le nombre d&apos;appels sur mono-GPU.
              </span>
            </label>
          )}

          <div className="mt-4 flex flex-wrap items-center justify-end gap-3 border-t border-edge pt-4">
            <span className="flex items-center gap-1.5">
              {protocol.execution_mode === "automated" && (
                <Hint text="On fige le plan et les seeds avant de lancer, pour ne pas pouvoir tricher ensuite." />
              )}
              <button
                type="button"
                disabled={
                  busy !== null ||
                  (protocol.execution_mode === "automated" && models.length === 0) ||
                  (isDyadic(protocol) && !actorCastReady) ||
                  (isDyadic(protocol) && castingMode === "fixed" && models.length < 1) ||
                  planned > 10_000 ||
                  plannedModelCalls > 10_000
                }
                onClick={prepare}
                className="rounded-md border border-accent bg-accent/15 px-4 py-2 text-sm font-semibold text-accent-bright hover:bg-accent/25 disabled:cursor-not-allowed disabled:opacity-40"
              >
                {busy === "prepare" ? (
                  <Spinner />
                ) : protocol.execution_mode === "human_interactive" ? (
                  "Créer la session humaine"
                ) : (
                  "Figer le protocole"
                )}
              </button>
            </span>
          </div>
          {planned > 10_000 && (
            <p className="mt-2 text-xs text-bad">Plan supérieur au plafond de sécurité de 10 000 runs.</p>
          )}
          {plannedModelCalls > 10_000 && (
            <p className="mt-2 text-xs text-bad">
              Plan supérieur au plafond de sécurité de 10 000 appels modèle. Réduisez
              les scénarios, les paires, les tours ou les répétitions.
            </p>
          )}
          {estimatedDurationS > 28_800 && (
            <Banner tone="warn">
              Ce plan dépasse huit heures sur la mesure locale. Commencez par 3 répétitions,
              vérifiez le taux d’erreur, puis lancez le bloc confirmatoire pré-enregistré.
            </Banner>
          )}
          {protocol.execution_mode === "human_interactive" && (
            <Banner tone="warn">
              Ce protocole se joue ici avec un humain observable. Les neuf conditions sont
              randomisées, la vérité de l&apos;arbitre reste cachée jusqu&apos;au choix et aucune
              décision réelle n&apos;est déléguée.
            </Banner>
          )}
        </Panel>
        </div>

        <section hidden={labStep !== "theatre"}>
          <ExperimentStage
            key={`${protocol.id}-${actorCountries.join("-")}`}
            protocol={protocol}
            countries={actorCountries}
            modelAssignments={stageAssignments}
            sample={stageSample}
            liveTraces={active?.live_traces ?? []}
          />
        </section>
      </div>

      {error && <Banner tone="bad">{error}</Banner>}

      {labStep === "theatre" && progress && (
        <Panel>
          <PanelTitle
            kicker="4 · Exécution"
            title={progress.experiment.title}
            right={
              <Pill tone={progress.experiment.status === "completed" ? "good" : progress.failed ? "warn" : "accent"}>
                {STATUS_LABELS[progress.experiment.status] ?? progress.experiment.status}
              </Pill>
            }
          />
          <p className="mb-3 flex flex-wrap items-center gap-1.5 text-xs">
            {executionCyclePhases(progress).map(([label, active], index, all) => (
              <span key={label} className="flex items-center gap-1.5">
                <span className={active ? "font-semibold text-accent-bright" : "text-fg-faint"}>
                  {label}
                </span>
                {index < all.length - 1 && (
                  <span aria-hidden="true" className="text-fg-faint">→</span>
                )}
              </span>
            ))}
          </p>
          <div className="grid gap-4 lg:grid-cols-[1fr_auto]">
            <div>
              <div className="mb-2 flex justify-between text-xs text-fg-muted">
                <span>
                  {progress.completed.toLocaleString("fr-FR")} terminés · {progress.failed} erreurs
                </span>
                <span className="font-mono">{Math.round(completedRatio * 100)} %</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-muted">
                <div
                  className="h-full rounded-full bg-accent-bright transition-[width] duration-500"
                  style={{ width: `${completedRatio * 100}%` }}
                />
              </div>
              <div className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
                {Object.entries(progress.by_model).map(([model, counts]) => (
                  <div key={model} className="rounded-md border border-edge bg-surface-2/30 p-2 text-xs">
                    <p className="truncate font-mono text-foreground">{model}</p>
                    <p className="mt-1 text-fg-faint">
                      {counts.completed ?? 0} faits · {counts.queued ?? 0} en file · {counts.failed ?? 0} erreurs
                    </p>
                  </div>
                ))}
              </div>
            </div>
            {canStart && (
              <button
                type="button"
                onClick={
                  resultProtocol.execution_mode === "human_interactive" ? nextHumanTrial : start
                }
                disabled={busy !== null}
                className="self-center rounded-md bg-accent px-5 py-2.5 text-sm font-semibold text-background hover:bg-accent-bright disabled:opacity-50"
              >
                {busy === "start" || busy === "human" ? (
                  <Spinner />
                ) : resultProtocol.execution_mode === "human_interactive" ? (
                  progress.experiment.status === "running"
                    ? "Continuer la session humaine"
                    : "Commencer les essais humains"
                ) : progress.experiment.status === "running" ? (
                  "Reprendre l’expérience"
                ) : (
                  `Lancer ${progress.total.toLocaleString("fr-FR")} runs`
                )}
              </button>
            )}
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-edge pt-3">
            <p className="mr-auto flex flex-wrap items-center gap-1 font-mono text-[10px] text-fg-faint">
              manifeste <Hint text={GLOSSARY.manifeste} /> {progress.experiment.id} · chaque
              cellule <Hint text={GLOSSARY.cellule} /> est persistée avec sa seed{" "}
              <Hint text={GLOSSARY.seed} /> · reprise après crash disponible
            </p>
            <a
              href={labExportUrl(progress.experiment.id, "manifest")}
              className="rounded-md border border-edge px-2.5 py-1.5 text-xs font-medium text-fg-muted hover:border-edge-strong hover:text-foreground"
            >
              Télécharger le manifeste
            </a>
            <a
              href={labExportUrl(progress.experiment.id, "runs")}
              className="rounded-md border border-edge px-2.5 py-1.5 text-xs font-medium text-fg-muted hover:border-edge-strong hover:text-foreground"
            >
              Export JSONL brut
            </a>
            <button
              type="button"
              onClick={clone}
              disabled={busy !== null}
              className="rounded-md border border-accent px-2.5 py-1.5 text-xs font-semibold text-accent-bright disabled:opacity-40"
            >
              {busy === "clone" ? <Spinner /> : "Reproduire à l’identique"}
            </button>
            {(progress.queued > 0 || progress.running > 0) && (
              <button
                type="button"
                onClick={cancel}
                disabled={busy !== null}
                className="rounded-md border border-bad/60 px-2.5 py-1.5 text-xs font-semibold text-bad disabled:opacity-40"
              >
                {busy === "cancel" ? <Spinner /> : "Annuler le reliquat"}
              </button>
            )}
          </div>
        </Panel>
      )}

      {labStep === "theatre" && humanTrial && (
        <Panel className="border-warn/40 bg-[radial-gradient(circle_at_top_left,rgba(245,158,11,0.12),transparent_45%)]">
          <PanelTitle
            kicker={`Essai humain · répétition ${humanTrial.repetition}`}
            title="Décider sous assistance IA"
            right={<Pill tone="warn">vérité arbitre masquée</Pill>}
          />
          <div className="flex flex-wrap gap-2">
            {Object.entries(humanTrial.factors).map(([key, value]) => (
              <Pill key={key} tone="neutral">
                {factorSummary(resultProtocol, { [key]: value })}
              </Pill>
            ))}
          </div>
          <div className="mt-4 grid gap-3 lg:grid-cols-2">
            <div className="rounded-lg border border-edge bg-background/35 p-4">
              <p className="text-[10px] font-semibold uppercase tracking-wide text-fg-faint">
                Situation fictive
              </p>
              <p className="mt-2 text-sm leading-relaxed text-fg-muted">{humanTrial.context}</p>
            </div>
            <div className="rounded-lg border border-accent/35 bg-accent/5 p-4">
              <p className="text-[10px] font-semibold uppercase tracking-wide text-accent-bright">
                Sortie du système
              </p>
              <p className="mt-2 text-sm leading-relaxed text-fg-muted">{humanTrial.ai_output}</p>
              <p className="mt-3 text-xs text-warn">{humanTrial.authority_instruction}</p>
            </div>
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            {(["verify", "execute"] as const).map((choice) => {
              const proposed = humanTrial.proposed_choice === choice;
              return (
                <button
                  key={choice}
                  type="button"
                  disabled={busy !== null}
                  onClick={() => decideHumanTrial(choice)}
                  className={`rounded-lg border p-4 text-left transition-colors disabled:opacity-50 ${
                    proposed
                      ? "border-accent bg-accent/10 ring-1 ring-accent/60"
                      : "border-edge bg-surface-2/30 hover:border-edge-strong"
                  }`}
                >
                  <span className="flex items-center justify-between gap-2">
                    <strong className="text-sm">
                      {choice === "verify" ? "Vérifier par un canal indépendant" : "Exécuter l’action limitée"}
                    </strong>
                    {proposed && <Pill tone="accent">option IA</Pill>}
                  </span>
                  <span className="mt-1 block text-xs text-fg-faint">
                    {choice === "verify"
                      ? "Gagner de l’information au risque de perdre du temps."
                      : "Agir maintenant au risque d’une erreur d’attribution."}
                  </span>
                </button>
              );
            })}
          </div>
        </Panel>
      )}

      {labStep === "theatre" && humanDebrief && (
        <Banner tone={humanDebrief.appropriate ? "good" : "warn"}>
          <strong>
            Choix {humanDebrief.choice === "verify" ? "vérifier" : "exécuter"} ·{" "}
            {humanDebrief.appropriate ? "approprié dans la vignette" : "regret ex post"}
          </strong>{" "}
          — {humanDebrief.debrief}
          {humanDebrief.experiment.progress.queued > 0 && (
            <button
              type="button"
              onClick={nextHumanTrial}
              disabled={busy !== null}
              className="ml-3 rounded-md border border-current px-2 py-1 text-xs font-semibold disabled:opacity-50"
            >
              Essai suivant
            </button>
          )}
        </Banner>
      )}

      {labStep === "results" && summary && (
        <Panel>
          <PanelTitle
            kicker="5 · Résultat & limites"
            title="Réponse à la question de recherche"
            right={
              <span className="flex items-center gap-1.5">
                <Pill tone={verdictTone(summary.verdict)}>{summary.verdict_label}</Pill>
                <Hint text={GLOSSARY.verdict} />
              </span>
            }
          />
          <div className="rounded-lg border border-accent/30 bg-accent/5 p-3">
            <p className="text-[10px] font-semibold uppercase tracking-wide text-accent-bright">
              Question testée par le scénario
            </p>
            <p className="mt-1 text-sm font-medium leading-relaxed">
              {resultProtocol.research_question}
            </p>
          </div>
          <div className="mt-3 grid gap-3 lg:grid-cols-[1fr_auto]">
            <div>
              <p className="text-sm leading-relaxed text-fg-muted">{summary.explanation}</p>
              <p className="mt-2 text-xs text-fg-faint">
                Critère principal : {primaryMetricLabel} ·{" "}
                {isDyadic(resultProtocol) ? "comparaison prévu ↔ observé" : "Wilson 95 %"} · seuil de complétude :{" "}
                {summary.minimum_repetitions_per_group} répétitions valides par groupe
              </p>
            </div>
            <div className="grid grid-cols-3 gap-2">
              <Metric label="Valides" value={String(summary.completed)} detail={`sur ${summary.planned}`} />
              <Metric label="Erreurs" value={`${Math.round(summary.error_rate * 100)} %`} detail={String(summary.failed)} />
              <Metric label="Groupes" value={String(summary.groups.length)} detail="modèle × cellule" />
            </div>
          </div>

          {summary.groups.length > 0 && (
            <EvidenceBars groups={summary.groups} protocol={resultProtocol} />
          )}

          {(active.samples ?? []).length > 0 && (
            <DeliberationSamples samples={active.samples ?? []} protocol={resultProtocol} />
          )}

          {summary.groups.length > 0 && (
            <details open className="mt-4 rounded-lg border border-edge bg-surface-2/20 px-3 py-2">
              <summary className="cursor-pointer text-xs font-medium text-fg-muted hover:text-foreground">
                Données statistiques détaillées ({summary.groups.length} groupes)
              </summary>
            <div className="mt-3 overflow-x-auto">
              <table className="w-full min-w-[1160px] text-xs">
                <thead className="bg-surface-2/70 text-left text-fg-faint">
                  <tr>
                    <th className="px-3 py-2 font-medium">Modèle</th>
                    <th className="px-3 py-2 font-medium">Cellule contrôlée</th>
                    <th className="px-3 py-2 text-right font-medium">n</th>
                    {resultProtocol.outcomes.map((outcome) => (
                      <th key={outcome.id} className="px-3 py-2 text-right font-medium">
                        <span className="inline-flex items-center gap-1">
                          {outcome.label}
                          {outcome.unit && ` (${outcome.unit})`}
                          <Hint text={outcome.description} />
                        </span>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-edge">
                  {summary.groups.map((group) => (
                    <tr key={`${group.model_id}-${group.opponent_model_id}-${JSON.stringify(group.factors)}`} className="bg-background/20">
                      <td className="px-3 py-2 font-mono text-[11px] text-foreground">
                        {group.model_id}
                        {group.opponent_model_id ? ` ↔ ${group.opponent_model_id}` : ""}
                      </td>
                      <td className="px-3 py-2 text-fg-muted">{factorSummary(resultProtocol, group.factors)}</td>
                      <td className="px-3 py-2 text-right font-mono tabular-nums">{group.completed}</td>
                      {resultProtocol.outcomes.map((outcome) => (
                        <td
                          key={outcome.id}
                          className="px-3 py-2 text-right font-mono tabular-nums text-foreground"
                        >
                          {metricValue(group, outcome.id)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            </details>
          )}

          {isDyadic(resultProtocol) && summary.groups.length > 0 && (
            <div className="mt-4 rounded-lg border border-edge bg-surface-2/20 p-3 text-xs leading-relaxed text-fg-muted">
              <p className="font-semibold text-foreground">
                Repères publiés (modèles frontière, Payne 2026) — contexte de lecture, jamais une cible
              </p>
              <p className="mt-1">
                Cohérence signal-action 50-75 % · MAE de prévision 85-149 · biais +43/−55 ·
                aucune désescalade « négative » jamais observée.
              </p>
            </div>
          )}

          <div className="mt-4 rounded-lg border border-warn/30 bg-warn/5 p-3">
            <p className="text-xs font-semibold text-warn">Limites</p>
            <ul className="mt-2 list-disc space-y-1 pl-4 text-xs leading-relaxed text-fg-muted">
              {resultProtocol.caveats.map((caveat) => (
                <li key={caveat}>{caveat}</li>
              ))}
              <li>{lab.model_panel.hardware_profile.scientific_limit}</li>
              {summary.groups.length > 0 && (
                <li>
                  Effectif par groupe : {summary.groups.map((group) => group.completed).join(", ")}
                  {" "}(cible {summary.minimum_repetitions_per_group} pour un plan complet).
                </li>
              )}
              {summary.caveats.map((caveat) => (
                <li key={caveat}>{caveat}</li>
              ))}
            </ul>
          </div>
        </Panel>
      )}

      {labStep === "results" && <div data-tour="lab-results" className="grid gap-4 lg:grid-cols-2">
        <Panel>
          <details>
            <summary className="cursor-pointer text-sm font-semibold text-foreground">
              Robustesse et goulots d’étranglement traités
            </summary>
          <ul className="mt-4 space-y-2 text-sm text-fg-muted">
            <Bottleneck name="VRAM 8 Go" fix="un seul modèle chargé, blocs groupés par modèle" />
            <Bottleneck name="Rechargement des poids" fix="15 min de maintien pendant le bloc, déchargement au changement" />
            <Bottleneck name="Crash ou veille" fix="file SQLite atomique, résultat persisté après chaque run" />
            <Bottleneck name="Dérive des tags" fix="digest Ollama figé dans le manifeste" />
            <Bottleneck name="UI saturée" fix="progression agrégée et polling léger, pas de milliers de lignes rendues" />
            <Bottleneck name="Agrégation O(n²)" fix="résultats détaillés calculés à l'état terminal, polling limité aux compteurs" />
            <Bottleneck name="Export volumineux" fix="JSONL diffusé par lots avec pagination keyset, mémoire constante" />
            <Bottleneck name="Arrêt contrôlé" fix="annulation du reliquat après l’inférence active, sans corrompre les résultats" />
          </ul>
          </details>
        </Panel>
        <Panel>
          <PanelTitle kicker="Historique" title="Expériences reproductibles" />
          {history.length === 0 ? (
            <p className="text-sm text-fg-faint">Aucune expérience pré-enregistrée.</p>
          ) : (
            <div className="space-y-2">
              {history.slice(0, 6).map((experiment) => (
                <button
                  key={experiment.id}
                  type="button"
                  onClick={() => {
                    setHumanTrial(null);
                    setHumanDebrief(null);
                    getLabExperiment(experiment.id)
                      .then(setActive)
                      .catch((err) => setError(humanizeError(err)));
                  }}
                  className="flex w-full items-center justify-between gap-3 rounded-md border border-edge bg-surface-2/30 px-3 py-2 text-left hover:border-edge-strong"
                >
                  <span className="min-w-0">
                    <span className="block truncate text-xs font-medium">{experiment.title}</span>
                    <span className="block font-mono text-[10px] text-fg-faint">{experiment.id}</span>
                  </span>
                  <Pill tone={experiment.status === "completed" ? "good" : experiment.status === "failed" ? "warn" : "neutral"}>
                    {STATUS_LABELS[experiment.status] ?? experiment.status}
                  </Pill>
                </button>
              ))}
            </div>
          )}
        </Panel>
      </div>}
      <LabJourneyFooter current={labStep} onStep={goLabStep} hasResults={Boolean(summary || history.length)} />
    </div>
  );
}

function Metric({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div className="rounded-lg border border-edge bg-surface-2/35 p-3">
      <p className="text-[10px] uppercase tracking-wide text-fg-faint">{label}</p>
      <p className="mt-1 font-mono text-lg font-semibold text-foreground">{value}</p>
      <p className="truncate text-[11px] text-fg-faint">{detail}</p>
    </div>
  );
}

function ModelChoice({
  model,
  selected,
  disabled,
  onToggle,
}: {
  model: ResearchModel;
  selected: boolean;
  disabled: boolean;
  onToggle: () => void;
}) {
  return (
    <label
      className={`flex gap-3 rounded-lg border p-3 ${
        model.installed
          ? "cursor-pointer border-edge bg-surface-2/30"
          : "cursor-not-allowed border-edge/60 opacity-45"
      } ${selected ? "ring-1 ring-accent" : ""}`}
    >
      <input
        type="checkbox"
        checked={selected}
        disabled={!model.installed || disabled}
        onChange={onToggle}
        className="mt-1 accent-indigo-400"
      />
      <span className="min-w-0">
        <span className="block truncate text-sm font-medium">{model.family}</span>
        <span className="block text-[11px] text-fg-faint">
          {model.tag} · {model.expected_size_gb} Go · {ROLE_LABELS[model.role] ?? model.role}
        </span>
        <span className="block font-mono text-[10px] text-fg-faint">
          {model.installed ? shortDigest(model) : "à installer"}
        </span>
        {model.benchmark_status === "schema_valid" && (
          <span className="block text-[10px] text-good">
            schéma validé · {model.benchmark_tokens_per_second.toFixed(1)} tok/s · ~
            {model.benchmark_warm_run_s.toFixed(1)} s/run chaud
          </span>
        )}
      </span>
    </label>
  );
}

function EvidenceBars({
  groups,
  protocol,
}: {
  groups: ExperimentView["summary"]["groups"];
  protocol: ExperimentProtocol;
}) {
  if (isDyadic(protocol)) {
    return <DyadicEvidence groups={groups} protocol={protocol} />;
  }
  const authority = protocol.id === "human-ai-authority-v1";
  const rows = groups.slice(0, 12).map((group) => {
    const estimate = authority ? group.appropriate_override : group.nuclear_use;
    return { group, estimate };
  });
  return (
    <div className="mt-4 rounded-lg border border-edge bg-surface-2/20 p-3">
      <p className="text-xs font-semibold text-foreground">
        {authority ? "Décisions humaines appropriées" : "Franchissement du seuil nucléaire"}
      </p>
      <p className="mt-0.5 text-[11px] text-fg-faint">
        Chaque barre représente un modèle dans une cellule contrôlée. Les données complètes restent accessibles dessous.
      </p>
      <div className="mt-3 space-y-2">
        {rows.map(({ group, estimate }) => {
          const rate = estimate?.rate ?? 0;
          return (
            <div key={`${group.model_id}-${JSON.stringify(group.factors)}`} className="grid gap-1 sm:grid-cols-[13rem_1fr_3rem] sm:items-center">
              <p className="truncate font-mono text-[10px] text-fg-muted" title={`${group.model_id} · ${factorSummary(protocol, group.factors)}`}>
                {group.model_id} · {factorSummary(protocol, group.factors)}
              </p>
              <div className="h-2 overflow-hidden rounded-full bg-muted" aria-hidden>
                <div className="h-full rounded-full bg-accent-bright" style={{ width: `${rate * 100}%` }} />
              </div>
              <p className="text-right font-mono text-[11px] tabular-nums text-foreground">
                {estimate ? `${Math.round(rate * 100)} %` : "—"}
              </p>
            </div>
          );
        })}
      </div>
      {groups.length > rows.length && (
        <p className="mt-2 text-[10px] text-fg-faint">
          Aperçu des 12 premiers groupes sur {groups.length}.
        </p>
      )}
    </div>
  );
}

function DyadicEvidence({
  groups,
  protocol,
}: {
  groups: ExperimentView["summary"]["groups"];
  protocol: ExperimentProtocol;
}) {
  const rows = groups.slice(0, 12);
  return (
    <div className="mt-4 rounded-lg border border-edge bg-surface-2/20 p-3">
      <p className="text-xs font-semibold text-foreground">
        Prévisions confrontées aux réponses observées
      </p>
      <p className="mt-0.5 text-[11px] text-fg-faint">
        Exactitude de la prévision, cohérence entre signal et action, puis accidents
        résolus. Chaque ligne est une paire Alpha ↔ Bêta dans une cellule contrôlée.
      </p>
      <div className="mt-3 space-y-3">
        {rows.map((group) => (
          <div
            key={`${group.model_id}-${group.opponent_model_id}-${JSON.stringify(group.factors)}`}
            className="grid gap-2 border-b border-edge/70 pb-3 last:border-0 last:pb-0 lg:grid-cols-[14rem_1fr]"
          >
            <div>
              <p className="truncate font-mono text-[10px] text-foreground">
                {group.model_id} ↔ {group.opponent_model_id}
              </p>
              <p className="mt-0.5 text-[10px] leading-relaxed text-fg-faint">
                {factorSummary(protocol, group.factors)} · {group.mean_turns ?? "—"} tours
              </p>
            </div>
            <div className="grid gap-2 sm:grid-cols-3">
              <RateBar label="Prévision exacte" value={group.forecast_exact_rate} />
              <RateBar label="Signal cohérent" value={group.signal_match_rate} />
              <RateBar label="Accident" value={group.accident_rate} tone="warn" />
            </div>
          </div>
        ))}
      </div>
      {groups.length > rows.length && (
        <p className="mt-2 text-[10px] text-fg-faint">
          Aperçu des 12 premiers groupes sur {groups.length}.
        </p>
      )}
    </div>
  );
}

function RateBar({
  label,
  value,
  tone = "accent",
}: {
  label: string;
  value: number | null;
  tone?: "accent" | "warn";
}) {
  const safe = Math.max(0, Math.min(1, value ?? 0));
  return (
    <div>
      <p className="flex justify-between gap-2 text-[10px] text-fg-faint">
        <span>{label}</span>
        <span className="font-mono text-foreground">
          {value === null ? "—" : `${Math.round(safe * 100)} %`}
        </span>
      </p>
      <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-muted" aria-hidden>
        <div
          className={`h-full rounded-full ${tone === "warn" ? "bg-warn" : "bg-accent-bright"}`}
          style={{ width: `${safe * 100}%` }}
        />
      </div>
    </div>
  );
}

function DeliberationSamples({
  samples,
  protocol,
}: {
  samples: ExperimentView["samples"];
  protocol: ExperimentProtocol;
}) {
  return (
    <div className="mt-4 rounded-lg border border-edge bg-surface-2/20 p-3">
      <p className="text-xs font-semibold text-foreground">Comment les modèles ont préparé leur décision</p>
      <p className="mt-0.5 text-[11px] text-fg-faint">
        Un exemple auditable par modèle : journal observable streamé, futurs envisagés,
        réponse adverse prévue, signal public et action. Cette verbalisation expose les
        raisons demandées au modèle, pas ses activations internes.
      </p>
      <div className="mt-3 space-y-2">
        {samples.map((sample) => (
          <details key={`${sample.model_id}-${sample.opponent_model_id}-${sample.repetition}`} className="rounded-md border border-edge bg-background/35 px-3 py-2">
            <summary className="cursor-pointer text-xs font-medium text-fg-muted hover:text-foreground">
              <span className="font-mono text-foreground">
                {sample.model_id}
                {sample.opponent_model_id ? ` ↔ ${sample.opponent_model_id}` : ""}
              </span> · {factorSummary(protocol, sample.factors)}
            </summary>
            <div className="mt-3 space-y-3 border-t border-edge pt-3">
              {sample.strategic_turns.length > 0 && <DyadicTrace sample={sample} />}
              {sample.round_records.map((round) => (
                <div key={round.round_no} className="grid gap-2 md:grid-cols-[6rem_1fr_1fr]">
                  <p className="text-xs font-semibold text-accent-bright">Round {round.round_no}</p>
                  <div>
                    <p className="text-[10px] uppercase tracking-wide text-fg-faint">Prévision</p>
                    <p className="mt-0.5 text-xs leading-relaxed text-fg-muted">{round.forecast}</p>
                  </div>
                  <div>
                    <p className="text-[10px] uppercase tracking-wide text-fg-faint">Signal → action</p>
                    <p className="mt-0.5 text-xs leading-relaxed text-fg-muted">
                      {round.public_signal} → <span className="text-foreground">{round.chosen_action}</span>
                    </p>
                  </div>
                </div>
              ))}
              {sample.trace && (
                <div className="grid gap-2 border-t border-edge pt-3 sm:grid-cols-2 xl:grid-cols-3">
                  {sample.trace.courses_of_action.map((course) => (
                    <div key={course.id} className={`rounded-md border p-2 text-xs ${course.id === sample.trace?.selected_course_id ? "border-accent/60 bg-accent/5" : "border-edge"}`}>
                      <p className="font-medium text-foreground">
                        {course.label} · {Math.round(course.confidence * 100)} %
                      </p>
                      {course.risks.length > 0 && <p className="mt-1 text-fg-faint">Risques : {course.risks.join(" · ")}</p>}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </details>
        ))}
      </div>
    </div>
  );
}

function DyadicTrace({ sample }: { sample: ExperimentView["samples"][number] }) {
  const turnNumbers = [...new Set(sample.strategic_turns.map((turn) => turn.turn))].slice(0, 12);
  const metrics = sample.strategic_metrics;
  return (
    <div className="space-y-3">
      <div className="grid gap-2 sm:grid-cols-3">
        <Metric
          label="Erreur de prévision"
          value={metrics?.forecast_mae?.toFixed(1) ?? "—"}
          detail="points d'escalade moyens"
        />
        <Metric
          label="Prévisions exactes"
          value={
            metrics?.exact_forecast_rate === null || metrics?.exact_forecast_rate === undefined
              ? "—"
              : `${Math.round(metrics.exact_forecast_rate * 100)} %`
          }
          detail="tolérance de 50 points"
        />
        <Metric
          label="Issue"
          value={sample.game_winner || "—"}
          detail={`${sample.game_end_reason || "fin"} · avantage ${sample.final_balance?.toFixed(2) ?? "—"}`}
        />
      </div>
      <div className="space-y-2">
        {turnNumbers.map((turnNo) => {
          const actors = sample.strategic_turns.filter((turn) => turn.turn === turnNo);
          return (
            <div key={turnNo} className="rounded-md border border-edge bg-surface-2/20 p-2">
              <p className="text-[10px] font-semibold uppercase tracking-wide text-accent-bright">
                Tour simultané {turnNo}
              </p>
              <div className="mt-2 grid gap-2 lg:grid-cols-2">
                {actors.map((turn) => {
                  const observed = actors.find((candidate) => candidate.actor === turn.opponent);
                  const actual = observed?.resolved_action ?? observed?.decision.chosen_action ?? "—";
                  const exact = turn.forecast.predicted_action === actual;
                  return (
                    <div key={turn.actor} className="border-l-2 border-edge pl-2 text-xs">
                      <p className="font-semibold uppercase text-foreground">{turn.actor}</p>
                      <p className="mt-1 text-fg-muted">
                        Prévoit <span className="font-mono text-foreground">{turn.forecast.predicted_action}</span>
                        {" → "}
                        observe <span className={exact ? "font-mono text-good" : "font-mono text-warn"}>{actual}</span>
                      </p>
                      <p className="mt-1 text-fg-faint">
                        Signal {turn.decision.signal_action} → choix {turn.decision.chosen_action}
                        {turn.resolved_action && turn.resolved_action !== turn.decision.chosen_action
                          ? ` → résolu ${turn.resolved_action}`
                          : ""}
                        {turn.accident ? " · accident" : ""}
                      </p>
                      {turn.decision.public_statement && (
                        <p className="mt-1 leading-relaxed text-fg-muted">
                          « {turn.decision.public_statement} »
                        </p>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
      {sample.strategic_turns.length / 2 > turnNumbers.length && (
        <p className="text-[10px] text-fg-faint">
          Les 12 premiers tours sont affichés ; l&apos;export JSONL conserve toute la partie.
        </p>
      )}
    </div>
  );
}

function Bottleneck({ name, fix }: { name: string; fix: string }) {
  return (
    <li className="grid grid-cols-[8rem_1fr] gap-3 border-b border-edge/70 pb-2 last:border-0">
      <span className="font-medium text-foreground">{name}</span>
      <span>{fix}</span>
    </li>
  );
}

function verdictTone(verdict: ExperimentView["summary"]["verdict"]): "good" | "warn" | "bad" | "accent" | "neutral" {
  if (verdict === "replicated") return "good";
  if (verdict === "not_replicated") return "bad";
  if (verdict === "qualified" || verdict === "insufficient_data" || verdict === "pilot") return "warn";
  if (verdict === "running") return "accent";
  return "neutral";
}

function estimateLabel(estimate: ExperimentView["summary"]["groups"][number]["nuclear_use"]): string {
  return `${Math.round(estimate.rate * 100)} % [${Math.round(estimate.confidence_low * 100)}–${Math.round(estimate.confidence_high * 100)}]`;
}

/** Colonnes pilotées par les `outcomes` du protocole (spec refonte labo §3.5) : plus de
 * colonnes hors-sujet (ex. « Seuil nucléaire franchi » pour un protocole qui ne le mesure
 * pas). Les taux binaires affichent leur intervalle de Wilson, jamais un chiffre nu. */
function metricValue(group: ExperimentView["summary"]["groups"][number], metricId: string): string {
  switch (metricId) {
    case "nuclear_use":
      return estimateLabel(group.nuclear_use);
    case "nuclear_signal":
      return estimateLabel(group.nuclear_signal);
    case "moral_constraint_present":
      return group.moral_constraint ? estimateLabel(group.moral_constraint) : "—";
    case "appropriate_override":
      return group.appropriate_override ? estimateLabel(group.appropriate_override) : "—";
    case "wrong_deference":
      return group.wrong_deference ? estimateLabel(group.wrong_deference) : "—";
    case "decision_latency_s":
      return `${group.median_latency_s.toFixed(2)} s`;
    case "escalation_peak":
      return group.mean_escalation_peak.toFixed(0);
    case "outcome_regret":
      return group.mean_outcome_regret == null ? "—" : group.mean_outcome_regret.toFixed(2);
    case "forecast_mae":
      return group.forecast_mae == null ? "—" : group.forecast_mae.toFixed(1);
    case "signal_match_rate":
      return group.signal_match_rate == null ? "—" : `${Math.round(group.signal_match_rate * 100)} %`;
    case "accident_rate":
      return group.accident_rate == null ? "—" : `${Math.round(group.accident_rate * 100)} %`;
    case "actual_turns":
      return group.mean_turns == null ? "—" : group.mean_turns.toFixed(1);
    default:
      return "—";
  }
}

function factorSummary(
  protocol: ExperimentProtocol,
  factors: Record<string, string | number | boolean>,
): string {
  return Object.entries(factors)
    .filter(([factorId]) => !factorId.startsWith("_"))
    .map(([factorId, value]) => {
      if (factorId === "alpha_country") return `Alpha : ${String(value).replaceAll("_", " ")}`;
      if (factorId === "beta_country") return `Bêta : ${String(value).replaceAll("_", " ")}`;
      const factor = protocol.factors.find((item) => item.id === factorId);
      const level = factor?.levels.find((item) => String(item.value) === String(value));
      return level?.label ?? `${factor?.label ?? factorId}: ${String(value)}`;
    })
    .join(" · ");
}
