"use client";

/** Création de partie — flow séquentiel mode → rôle → pays (G11-b §1 S2-S4).
 *
 * Machine à états à retour arrière sans perte (les choix survivent aux allers-retours).
 * Entre les écrans : une brève rotation du globe (≤ 1,5 s, skippable au clic, désactivée
 * si prefers-reduced-motion). « Campagne » remplace S4 par la sélection de chapitre
 * (page /campagne). Les réglages transversaux vivent sous les cartes de mode. */

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useRef, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { SpeakerAvatar } from "@/components/avatar";
import { useSettings, useT } from "@/components/settings-provider";
import { Globe } from "@/components/globe";
import {
  completeCountryAssignments,
  CountryModelAssignments,
  ModelCastSelector,
} from "@/components/model-cast-selector";
import { SelectMap, type Fiche } from "@/components/select-map";
import { Banner, Eyebrow, Panel, PanelTitle, Segmented, Spinner, Switch } from "@/components/ui";
import { createGame, getCampaign, getLab, getSources, humanizeError, startChapter } from "@/lib/api";
import { speakerMeta } from "@/lib/countries";
import { fmt } from "@/lib/format";
import {
  buildCreateBody,
  canLaunch,
  DEFAULT_SETTINGS,
  FLOW_MODES,
  FLOW_STEPS,
  type LobbyMode,
  type FlowRole,
  type FlowSettings,
  type FlowStep,
  mapCapacity,
  nextStep,
  prevStep,
  ROUNDS_MAX,
  ROUNDS_MIN,
  trimForRole,
} from "@/lib/flow";
import { prefersReducedMotion } from "@/lib/stage";
import { TABLES } from "@/lib/temperament";
import type { AllianceInfo, CountrySources, Difficulty, ResearchModel } from "@/lib/types";

const TRANSITION_MS = 1200; // rotation du globe entre écrans (≤ 1,5 s, spec)
const INVENT_ALLIANCES_MAX = 3;

// RG-4 — la difficulté règle le moteur (budget, juge, enjeux) ET sert d'interrupteur
// des « coulisses » : Débutant/Intermédiaire gardent une façade épurée (scène, indice
// du monde, marché, outils de détection) ; Expert dévoile le banc d'essai (toutes les
// mesures d'analyse), aussi expliqué dans l'onglet Informations. Libellés en i18n
// (`lobby.diff.<value>.titre/desc`).
const DIFFICULTIES: readonly Difficulty[] = ["beginner", "intermediate", "expert"] as const;

const ROLES: { value: FlowRole; label: string; blurb: string }[] = [
  {
    value: "player",
    label: "Jouer un pays",
    blurb: "Incarne une super-intelligence : parole, directives, motions.",
  },
  {
    value: "invent",
    label: "Créer son pays",
    blurb: "Forge ton propre État (profil + mandat) et joue-le à la table.",
  },
  {
    value: "gm",
    label: "Game Master",
    blurb: "Invente les événements et adresse des consignes à toutes les IA.",
  },
  {
    value: "spectator",
    label: "Spectateur",
    blurb: "Tu paries et tu regardes le sommet — le monde qui penche fait ta note. En accéléré.",
  },
];

/** `useSearchParams` exige une frontière Suspense sur une page prérendue. */
export default function LobbyPage() {
  return (
    <Suspense fallback={null}>
      <LobbyFlow />
    </Suspense>
  );
}

function LobbyFlow() {
  const router = useRouter();
  const { player } = useAuth();
  // `prefs` = réglages utilisateur (G14 : langue des nouvelles parties, trad du chrome) ;
  // à ne pas confondre avec `settings` = réglages transversaux du flow (Dérive, rounds…).
  const { settings: prefs, t } = useSettings();

  const [step, setStep] = useState<FlowStep>("mode");
  const [transitioning, setTransitioning] = useState(false);
  const [baseMode, setBaseMode] = useState<LobbyMode>("classic");
  const [settings, setSettings] = useState<FlowSettings>(DEFAULT_SETTINGS);
  const [role, setRole] = useState<FlowRole>("player");
  const [selected, setSelected] = useState<string[]>([]);
  const [flag, setFlag] = useState<string | null>(null);

  // Invention (rôle « Créer son pays »)
  const [inventName, setInventName] = useState("");
  const [inventConcept, setInventConcept] = useState("");
  const [inventAlliances, setInventAlliances] = useState<string[]>([]);

  const [sources, setSources] = useState<CountrySources[] | null>(null);
  const [registry, setRegistry] = useState<Record<string, AllianceInfo>>({});
  const [creating, setCreating] = useState(false);
  const [sourcesError, setSourcesError] = useState(false); // fiches pays indisponibles
  const [error, setError] = useState<string | null>(null);
  const [researchModels, setResearchModels] = useState<ResearchModel[]>([]);
  const [modelCastEnabled, setModelCastEnabled] = useState(false);
  const [castModels, setCastModels] = useState<string[]>([]);
  const [castAssignments, setCastAssignments] = useState<Record<string, string>>({});

  // Étape adressable par l'URL (?etape=mode|role|pays) — deep-link utilisé par la
  // visite guidée (G13) : la page n'a aucune logique de tour, elle honore le param.
  // Le ref évite de ré-imposer un param déjà appliqué quand l'utilisateur revient
  // en arrière avec les boutons internes.
  const search = useSearchParams();
  const appliedEtape = useRef<string | null>(null);
  useEffect(() => {
    const etape = search.get("etape");
    if (!etape || appliedEtape.current === etape) return;
    appliedEtape.current = etape;
    if (!(FLOW_STEPS as readonly string[]).includes(etape)) return;
    const t = setTimeout(() => setStep(etape as FlowStep), 0); // jamais de setState sync en effet
    return () => clearTimeout(t);
  }, [search]);

  // Données pour les mini-fiches (indices clés) et les alliances d'invention.
  useEffect(() => {
    getSources()
      .then((v) => {
        setSources(v.countries);
        setRegistry(v.alliances);
      })
      .catch(() => {
        setSources([]); // la sélection reste possible, sans les mini-fiches
        setSourcesError(true);
      });
  }, []);

  useEffect(() => {
    getLab()
      .then((lab) => {
        const eligible = lab.model_panel.models.filter(
          (model) => model.installed && model.role !== "slow_robustness_only",
        );
        setResearchModels(eligible);
        setCastModels((current) =>
          current.length
            ? current
            : (eligible.filter((model) => model.role === "core_comparison").length
                ? eligible.filter((model) => model.role === "core_comparison")
                : eligible
              )
                .slice(0, 2)
                .map((model) => model.tag),
        );
      })
      .catch(() => undefined);
  }, []);

  const ficheByCountry = useMemo(() => {
    const map = new Map<string, Fiche>();
    for (const c of sources ?? []) {
      const rows = c.attributes.slice(0, 4).map((a) => ({
        label: a.label,
        value: typeof a.game_value === "boolean" ? (a.game_value ? "oui" : "non") : fmt(a.game_value),
      }));
      map.set(c.id, { rows });
    }
    return map;
  }, [sources]);

  const capacity = mapCapacity(role);
  const setRoleTrimming = (r: FlowRole) => {
    setRole(r);
    setSelected((prev) => trimForRole(prev, r)); // ne jamais dépasser la capacité
    setFlag(null);
  };

  const toggle = (slug: string) =>
    setSelected((prev) => {
      if (prev.includes(slug)) {
        if (flag === slug) setFlag(null);
        return prev.filter((c) => c !== slug);
      }
      if (prev.length >= capacity) return prev;
      return [...prev, slug];
    });

  const invent =
    role === "invent" && inventName.trim().length >= 2
      ? {
          name: inventName.trim(),
          concept: inventConcept.trim(),
          alliances: inventAlliances.length ? inventAlliances : undefined,
        }
      : undefined;

  const summitReady = canLaunch(role, selected, { flag, inventName });
  const humanCountry = role === "player" ? flag : null;
  const activeCastModels = modelCastEnabled ? castModels : castModels.slice(0, 1);
  const effectiveCastAssignments = completeCountryAssignments(
    selected,
    activeCastModels,
    castAssignments,
    humanCountry,
  );
  const castReady =
    researchModels.length === 0 ||
    (activeCastModels.length >= (modelCastEnabled ? 2 : 1) &&
      activeCastModels.length <= 4 &&
      activeCastModels.length <= selected.length - (role === "player" && flag ? 1 : 0));
  const launchable = summitReady && castReady;
  // Ce qui manque pour lancer — affiché à côté du bouton au lieu d'un disabled muet.
  const missing = capacity - selected.length;
  const launchHint = launchable
    ? null
    : missing > 0
      ? `Choisis encore ${missing} État${missing > 1 ? "s" : ""} sur la carte`
      : role === "player" && !flag
        ? "Désigne le pays que tu incarnes (il passera en doré)"
        : role === "invent" && inventName.trim().length < 2
          ? "Nomme ton État inventé (2 caractères minimum)"
          : modelCastEnabled && castModels.length < 2
            ? "Choisis au moins 2 modèles pour le casting diplomatique"
            : !castReady
              ? "Le casting contient plus de modèles que de pays joués par une IA"
              : null;

  // --- navigation avec transition globe ------------------------------------------
  const pendingRef = useRef<null | { t: ReturnType<typeof setTimeout>; to: FlowStep }>(null);
  // Nettoyage : un timer en vol ne doit pas déclencher setState après démontage
  // (retour à l'accueil / lancement de la partie pendant la transition).
  useEffect(() => () => clearTimeout(pendingRef.current?.t), []);
  const go = (to: FlowStep) => {
    if (prefersReducedMotion()) {
      setStep(to);
      return;
    }
    if (pendingRef.current) clearTimeout(pendingRef.current.t); // pas de timer orphelin
    setTransitioning(true);
    const t = setTimeout(() => {
      setStep(to);
      setTransitioning(false);
      pendingRef.current = null;
    }, TRANSITION_MS);
    pendingRef.current = { t, to }; // pour le skip au clic
  };
  const skipTransition = () => {
    if (!pendingRef.current) return;
    clearTimeout(pendingRef.current.t);
    setStep(pendingRef.current.to);
    setTransitioning(false);
    pendingRef.current = null;
  };

  const onNext = () => {
    // Campagne et Laboratoire sont deux destinations autonomes. Ils ne traversent pas
    // les écrans de rôle/pays du Classique : leur promesse reste immédiatement lisible.
    const destination = FLOW_MODES.find((mode) => mode.value === baseMode)?.destination;
    if (step === "mode" && destination) {
      router.push(destination);
      return;
    }
    const to = nextStep(step);
    if (to) go(to);
  };
  const onBack = () => {
    const to = prevStep(step);
    if (to) go(to);
  };

  // CC-5 — « Apprendre à jouer » : ouvre le chapitre 0 (tutoriel guidé, imperdable).
  // Le théâtre lance le guide tout seul sur le flag `tutorial` du chapitre.
  const [learning, setLearning] = useState(false);
  const learnToPlay = async () => {
    setLearning(true);
    setError(null);
    try {
      const camp = await getCampaign();
      const ch = camp.chapters.find((c) => c.tutorial);
      if (!ch) throw new Error("chapitre d'apprentissage introuvable");
      const game = await startChapter(ch.id, player?.id);
      router.push(`/games/${game.id}`);
    } catch (err) {
      setError(humanizeError(err));
      setLearning(false);
    }
  };

  const onLaunch = async () => {
    if (baseMode !== "classic") return;
    setCreating(true);
    setError(null);
    try {
      const game = await createGame(
        buildCreateBody({
          scenario: "red_sea",
          baseMode,
          settings,
          role,
          selected,
          flag,
          ownerId: player?.id,
          invent,
          language: prefs.lang, // G14 — les nouvelles parties naissent dans la langue réglée
          modelCast: activeCastModels.length
            ? {
                strategy: "manual",
                models: activeCastModels,
                assignments: effectiveCastAssignments,
                game_master_model: activeCastModels[0],
                judge_model: activeCastModels[activeCastModels.length - 1],
              }
            : undefined,
        }),
      );
      router.push(`/games/${game.id}`);
    } catch (err) {
      setError(humanizeError(err));
      setCreating(false);
    }
  };

  const stepIndex = { mode: 0, role: 1, pays: 2 }[step];
  const destination = FLOW_MODES.find((m) => m.value === baseMode)?.destination;

  return (
    <div className="space-y-8">
      {/* Transition : le globe tourne brièvement entre deux écrans. */}
      {transitioning && (
        <button
          onClick={skipTransition}
          aria-label="Passer la transition"
          className="fixed inset-0 z-50 flex items-center justify-center bg-background/95"
        >
          <Globe spinning className="w-72 max-w-[60vw]" />
          <span className="absolute bottom-16 text-xs text-fg-faint">
            {t("lobby.transition-skip")}
          </span>
        </button>
      )}

      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <Eyebrow>
            {t("lobby.kicker")} {stepIndex + 1}/3
          </Eyebrow>
          <h1 className="text-2xl font-semibold tracking-tight">
            {step === "mode"
              ? t("lobby.titre-mode")
              : step === "role"
                ? t("lobby.titre-role")
                : t("lobby.titre-pays")}
          </h1>
        </div>
        <Link
          href="/accueil"
          className="rounded-md border border-edge px-3 py-2 text-xs font-medium text-fg-muted transition-colors hover:border-edge-strong hover:text-foreground"
        >
          {t("lobby.retour-accueil")}
        </Link>
      </header>

      {/* Fil d'étapes */}
      <ol className="flex items-center gap-2 text-xs">
        {(["mode", "role", "pays"] as const).map((s, i) => (
          <li key={s} className="flex items-center gap-2">
            <span
              className={`grid h-6 w-6 place-items-center rounded-full border text-[11px] font-semibold ${
                i === stepIndex
                  ? "border-accent-bright bg-accent text-background"
                  : i < stepIndex
                    ? "border-accent-bright text-accent-bright"
                    : "border-edge text-fg-faint"
              }`}
            >
              {i + 1}
            </span>
            <span className={i === stepIndex ? "text-foreground" : "text-fg-faint"}>
              {[t("lobby.fil-mode"), t("lobby.fil-role"), t("lobby.fil-pays")][i]}
            </span>
            {i < 2 && <span className="mx-1 text-fg-faint">→</span>}
          </li>
        ))}
      </ol>

      {step === "mode" && (
        <>
          <ModeStep
            {...{
              baseMode,
              setBaseMode,
              settings,
              setSettings,
              researchModels,
              modelCastEnabled,
              setModelCastEnabled,
              castModels,
              setCastModels,
            }}
          />
          {/* CC-5 — la porte d'entrée des nouveaux : le chapitre 0 guidé. */}
          <p className="text-sm text-fg-faint">
            {t("lobby.apprendre-question")}{" "}
            <button
              onClick={learnToPlay}
              disabled={learning}
              className="cursor-pointer underline transition-colors hover:text-foreground disabled:cursor-wait disabled:opacity-60"
            >
              {learning ? t("lobby.apprendre-lancement") : t("lobby.apprendre")}
            </button>
          </p>
        </>
      )}
      {step === "role" && <RoleStep role={role} setRole={setRoleTrimming} />}
      {step === "pays" && (
        <PaysStep
          {...{
            role,
            selected,
            capacity,
            toggle,
            flag,
            setFlag,
            ficheByCountry,
            inventName,
            setInventName,
            inventConcept,
            setInventConcept,
            inventAlliances,
            setInventAlliances,
            registry,
            modelCastEnabled,
            castModels,
            castAssignments,
            setCastAssignments,
          }}
        />
      )}

      {step === "pays" && sourcesError && (
        <Banner tone="neutral">
          Les fiches pays sont indisponibles (API hors ligne ?) — la sélection reste
          possible, sans les infos clés au survol.
        </Banner>
      )}
      {error && <Banner tone="bad">{error}</Banner>}

      {/* Barre de navigation */}
      <div className="flex items-center justify-between gap-3 border-t border-edge pt-5">
        <button
          onClick={onBack}
          disabled={step === "mode"}
          className="rounded-md border border-edge px-4 py-2 text-sm text-fg-muted transition-colors hover:border-edge-strong hover:text-foreground disabled:opacity-40"
        >
          {t("lobby.retour")}
        </button>
        {step !== "pays" ? (
          <button
            onClick={onNext}
            className="rounded-md bg-accent px-6 py-2 text-sm font-semibold text-background transition-colors hover:bg-accent-bright"
          >
            {step === "mode" && destination
              ? baseMode === "campaign"
                ? t("lobby.chapitre")
                : t("lobby.laboratoire-ouvrir")
              : t("lobby.suivant")}
          </button>
        ) : (
          <span className="flex items-center gap-3">
            {launchHint && (
              <span role="status" className="text-xs text-fg-faint">
                {launchHint}
              </span>
            )}
            <button
              onClick={onLaunch}
              disabled={!launchable || creating}
              className="flex items-center gap-2 rounded-md bg-accent px-6 py-2 text-sm font-semibold text-background transition-colors hover:bg-accent-bright disabled:cursor-not-allowed disabled:opacity-50"
            >
              {creating && <Spinner />}
              {creating ? t("lobby.lancement") : t("lobby.jouer")}
            </button>
          </span>
        )}
      </div>
    </div>
  );
}

// --- S2 : mode + réglages transversaux ------------------------------------------

function ModeStep({
  baseMode,
  setBaseMode,
  settings,
  setSettings,
  researchModels,
  modelCastEnabled,
  setModelCastEnabled,
  castModels,
  setCastModels,
}: {
  baseMode: LobbyMode;
  setBaseMode: (m: LobbyMode) => void;
  settings: FlowSettings;
  setSettings: (s: FlowSettings) => void;
  researchModels: ResearchModel[];
  modelCastEnabled: boolean;
  setModelCastEnabled: (enabled: boolean) => void;
  castModels: string[];
  setCastModels: (models: string[]) => void;
}) {
  // En Campagne, chaque chapitre impose ses réglages (rounds, difficulté, mode) :
  // le panneau se désactive au lieu de laisser croire qu'il s'appliquera.
  const t = useT();
  const separateMode = baseMode !== "classic";
  return (
    <div className="space-y-6">
      <div className="grid gap-3 md:grid-cols-3" data-tour="modes">
        {FLOW_MODES.map((m) => (
          <button
            key={m.value}
            onClick={() => setBaseMode(m.value)}
            className={`rounded-lg border p-4 text-left transition-colors ${
              baseMode === m.value
                ? "border-accent-bright bg-surface-2"
                : "border-edge hover:border-edge-strong"
            }`}
          >
            <p
              className={`text-sm font-semibold ${baseMode === m.value ? "text-accent-bright" : "text-foreground"}`}
            >
              {t(`lobby.mode.${m.value}.titre`)}
            </p>
            <p className="mt-1 text-xs text-fg-muted">{t(`lobby.mode.${m.value}.blurb`)}</p>
            <p className="mt-2 text-xs text-fg-faint">
              {t("lobby.apprend-prefixe")} {t(`lobby.mode.${m.value}.apprend`)}
            </p>
          </button>
        ))}
      </div>

      <Panel>
        <PanelTitle
          kicker={t("lobby.reglages-kicker")}
          title={t("lobby.reglages-titre")}
          hint={t("lobby.reglages-aide")}
        />
        {separateMode && (
          <p className="-mt-2 mb-4 rounded-md border border-edge bg-surface-2/50 px-3 py-1.5 text-xs text-fg-faint">
            {t("lobby.destination-note")}
          </p>
        )}
        <div className={separateMode ? "space-y-4 opacity-50" : "space-y-4"} aria-disabled={separateMode}>
          {/* RG-2 — variantes de saveur : le Brouillard et le Réel/escalade (jadis des
              modes) sont deux interrupteurs, composables sur une partie classique. */}
          <div className="space-y-3 rounded-lg border border-edge bg-surface-2/40 p-3">
            <Switch
              label={t("lobby.brouillard-titre")}
              desc={t("lobby.brouillard-desc")}
              checked={settings.fog}
              disabled={separateMode}
              onChange={(v) => setSettings({ ...settings, fog: v })}
            />
            <Switch
              label={t("lobby.escalade-titre")}
              desc={t("lobby.escalade-desc")}
              checked={settings.escalation}
              disabled={separateMode}
              onChange={(v) => setSettings({ ...settings, escalation: v })}
            />
          </div>
          <label className="block">
            <span className="mb-1 flex items-baseline justify-between text-xs text-fg-muted">
              <span>{t("lobby.rounds")}</span>
              <span className="font-mono tabular-nums text-fg-faint">{settings.rounds}</span>
            </span>
            <input
              type="range"
              min={ROUNDS_MIN}
              max={ROUNDS_MAX}
              value={settings.rounds}
              disabled={separateMode}
              onChange={(e) => setSettings({ ...settings, rounds: Number(e.target.value) })}
              className="w-full accent-[var(--accent)] disabled:cursor-not-allowed"
            />
          </label>
          <div>
            <span className="mb-1 block text-xs text-fg-muted">{t("lobby.difficulte")}</span>
            <Segmented
              ariaLabel={t("lobby.difficulte")}
              value={settings.difficulty}
              disabled={separateMode}
              onChange={(d) => setSettings({ ...settings, difficulty: d })}
              options={DIFFICULTIES.map((d) => ({ value: d, label: t(`lobby.diff.${d}.titre`) }))}
            />
            <p className="mt-1.5 text-xs text-fg-faint">
              {t(`lobby.diff.${settings.difficulty}.desc`)}
            </p>
          </div>
          {/* CC-15c — les réglages rares vivent sous « Options avancées » : Partie libre,
              composition de la table. (La Dérive n'est plus un choix — RG-2.) */}
          <details className="border-t border-edge pt-3">
            <summary className="cursor-pointer select-none text-xs font-medium text-fg-muted transition-colors hover:text-foreground">
              {t("ui.options-avancees")}
            </summary>
            <div className="mt-3 space-y-4">
              <Switch
                label={t("lobby.libre-titre")}
                desc={t("lobby.libre-desc")}
                checked={settings.free}
                disabled={separateMode}
                onChange={(v) => setSettings({ ...settings, free: v })}
              />
              {/* G17 — composition de la table (partie LIBRE uniquement : sinon la table
                  reste équilibrée, le backend le garantit aussi). */}
              {settings.free && (
                <div>
                  <span className="mb-1 flex items-baseline justify-between text-xs text-fg-muted">
                    <span>{t("lobby.table-titre")}</span>
                    <span className="text-fg-faint">{t("lobby.table-pastilles")}</span>
                  </span>
                  <Segmented
                    size="sm"
                    ariaLabel={t("lobby.table-titre")}
                    value={settings.table ?? "equilibree"}
                    onChange={(v) => setSettings({ ...settings, table: v })}
                    options={TABLES}
                  />
                  <p className="mt-1.5 text-xs text-fg-faint">
                    {TABLES.find((tbl) => tbl.value === (settings.table ?? "equilibree"))?.desc}
                  </p>
                </div>
              )}
            </div>
          </details>
        </div>
      </Panel>
      {baseMode === "classic" && (
        <ModelCastSelector
          models={researchModels}
          enabled={modelCastEnabled}
          selected={castModels}
          onEnabled={setModelCastEnabled}
          onSelected={setCastModels}
          context="classic"
        />
      )}
    </div>
  );
}

// --- S3 : rôle ------------------------------------------------------------------

function RoleStep({
  role,
  setRole,
}: {
  role: FlowRole;
  setRole: (r: FlowRole) => void;
}) {
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4" data-tour="roles">
      {ROLES.map((r) => (
        <button
          key={r.value}
          onClick={() => setRole(r.value)}
          className={`rounded-lg border p-4 text-left transition-colors ${
            role === r.value ? "border-accent-bright bg-surface-2" : "border-edge hover:border-edge-strong"
          }`}
        >
          <p
            className={`text-sm font-semibold ${role === r.value ? "text-accent-bright" : "text-foreground"}`}
          >
            {r.label}
          </p>
          <p className="mt-1 text-xs text-fg-muted">{r.blurb}</p>
        </button>
      ))}
    </div>
  );
}

// --- S4 : pays ------------------------------------------------------------------

function PaysStep(props: {
  role: FlowRole;
  selected: string[];
  capacity: number;
  toggle: (slug: string) => void;
  flag: string | null;
  setFlag: (s: string) => void;
  ficheByCountry: Map<string, Fiche>;
  inventName: string;
  setInventName: (s: string) => void;
  inventConcept: string;
  setInventConcept: (s: string) => void;
  inventAlliances: string[];
  setInventAlliances: (fn: (prev: string[]) => string[]) => void;
  registry: Record<string, AllianceInfo>;
  modelCastEnabled: boolean;
  castModels: string[];
  castAssignments: Record<string, string>;
  setCastAssignments: (assignments: Record<string, string>) => void;
}) {
  const {
    role,
    selected,
    capacity,
    toggle,
    flag,
    setFlag,
    ficheByCountry,
    inventName,
    setInventName,
    inventConcept,
    setInventConcept,
    inventAlliances,
    setInventAlliances,
    registry,
    modelCastEnabled,
    castModels,
    castAssignments,
    setCastAssignments,
  } = props;

  const full = selected.length === capacity;
  const pickingFlag = role === "player" && full;

  return (
    <div className="space-y-4" data-tour="carte">
      <p className="text-sm text-fg-muted">
        {role === "invent"
          ? "Choisis 6 États sur la carte — ton pays inventé complétera le sommet à 7."
          : role === "player"
            ? full
              ? "Sommet complet. Clique le pays que tu veux incarner (il passe en doré)."
              : "Choisis exactement 7 États. Ton pays se désignera ensuite parmi eux."
            : "Choisis exactement 7 États : c'est le sommet que tu animeras."}
      </p>

      <SelectMap
        selected={selected}
        capacity={capacity}
        onToggle={toggle}
        flag={flag}
        pickingFlag={pickingFlag}
        onPickFlag={setFlag}
        ficheFor={(slug) => ficheByCountry.get(slug) ?? null}
      />

      {role === "player" && full && (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs text-fg-muted">Ton pays :</span>
          {selected.map((c) => (
            <button
              key={c}
              onClick={() => setFlag(c)}
              className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs transition-colors ${
                flag === c
                  ? "border-accent-bright bg-accent/20 text-accent-bright"
                  : "border-edge text-fg-muted hover:border-edge-strong"
              }`}
            >
              <SpeakerAvatar id={c} size={16} />
              {speakerMeta(c).label}
            </button>
          ))}
        </div>
      )}

      {role === "invent" && (
        <Panel>
          <PanelTitle kicker="Forge" title="Invente ton pays" hint="Le modèle en forge le profil complet et le mandat ; tu le joues à la table." />
          <div className="space-y-2">
            <input
              value={inventName}
              onChange={(e) => setInventName(e.target.value)}
              placeholder="Nom du pays (ex. Néo-Atlantis)"
              className="w-full rounded-md border border-edge bg-surface-2 px-3 py-2 text-sm outline-none transition-colors focus:border-indigo"
            />
            <input
              value={inventConcept}
              onChange={(e) => setInventConcept(e.target.value)}
              placeholder="Concept (ex. cité-État maritime pilotée par une IA)"
              className="w-full rounded-md border border-edge bg-surface-2 px-3 py-2 text-sm outline-none transition-colors focus:border-indigo"
            />
            {/* CC-15c — repliées : un pays inventé se joue très bien sans alliance. */}
            <details className="pt-1">
              <summary className="cursor-pointer select-none text-xs text-fg-muted transition-colors hover:text-foreground">
                Rejoindre des alliances réelles (optionnel){" "}
                <span className="font-mono tabular-nums text-fg-faint">
                  {inventAlliances.length}/{INVENT_ALLIANCES_MAX}
                </span>
              </summary>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {Object.entries(registry)
                  .filter(([, info]) => !info.informal)
                  .sort(([, a], [, b]) => a.name.localeCompare(b.name, "fr"))
                  .map(([tag, info]) => {
                    const checked = inventAlliances.includes(tag);
                    const disabled = !checked && inventAlliances.length >= INVENT_ALLIANCES_MAX;
                    return (
                      <button
                        key={tag}
                        type="button"
                        disabled={disabled}
                        onClick={() =>
                          setInventAlliances((prev) =>
                            prev.includes(tag) ? prev.filter((t) => t !== tag) : [...prev, tag],
                          )
                        }
                        title={info.basis}
                        className={`rounded-full border px-2 py-0.5 text-xs transition-colors ${
                          checked
                            ? "border-accent-bright bg-accent/20 text-accent-bright"
                            : disabled
                              ? "cursor-not-allowed border-edge text-fg-faint opacity-50"
                              : "border-edge text-fg-muted hover:border-edge-strong"
                        }`}
                      >
                        {info.name.split(" — ")[0]}
                      </button>
                    );
                  })}
              </div>
            </details>
          </div>
        </Panel>
      )}

      {modelCastEnabled && castModels.length >= 2 && (
        <CountryModelAssignments
          countries={selected}
          humanCountry={role === "player" ? flag : null}
          selectedModels={castModels}
          assignments={castAssignments}
          onAssignments={setCastAssignments}
        />
      )}

    </div>
  );
}
