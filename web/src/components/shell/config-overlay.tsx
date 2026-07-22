"use client";

/** ConfigOverlay — composer sa partie SUR le globe persistant (spec coquille §3, Inc 3).
 *
 * Porté du hall parallèle (`app/hall/page.tsx`) mais ne monte plus son propre globe :
 * il pousse son intention (pays cliquables, sélection, pays incarné) dans le
 * `StageDirector` et enregistre le clic-pays comme handler du globe du layout. Toute
 * la parité S11 : 5 sièges (dont ONU verrouillée → C5), tailles 5/7/9/12, forge,
 * réglages transversaux, casting multi-modèles, lancement.
 *
 * Note : les alliances de forge + i18n `hall.*` + plongée caméra continue arrivent
 * avant la suppression de `/lobby` (Inc 5/Inc 4). Ici, lancement = voile + navigation. */

import { useCallback, useEffect, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import {
  CountryModelAssignments,
  ModelCastSelector,
  completeCountryAssignments,
} from "@/components/model-cast-selector";
import { useSettings } from "@/components/settings-provider";
import { useStageDirector } from "@/components/shell/stage-provider";
import { Banner, Segmented, Spinner, Switch } from "@/components/ui";
import { usePlanetLaunch } from "@/hooks/usePlanetLaunch";
import { createGame, getLab, humanizeError } from "@/lib/api";
import { ROSTER, speakerMeta } from "@/lib/countries";
import {
  DEFAULT_SETTINGS as DEFAULT_FLOW,
  SUMMIT_SIZES,
  buildCreateBody,
  canLaunch,
  defaultCountryCastModels,
  mapCapacity,
  reasoningCountryModels,
  toggleCountry,
  trimForRole,
  type FlowRole,
  type FlowSettings,
} from "@/lib/flow";
import type { ResearchModel } from "@/lib/types";

const ROLES: { value: FlowRole | "un"; icon: string; label: string; desc: string }[] = [
  { value: "player", icon: "🎮", label: "Jouer un pays", desc: "Incarne un État du sommet." },
  { value: "invent", icon: "🛠", label: "Créer son pays", desc: "Forge un État et joue-le." },
  { value: "gm", icon: "🎭", label: "Game Master", desc: "Écris les crises, ne joue personne." },
  { value: "spectator", icon: "👁", label: "Spectateur", desc: "Observe et parie." },
  { value: "un", icon: "🕊", label: "ONU", desc: "La veille institutionnelle, depuis Genève." },
];

const TABLES = [
  { value: "equilibree", label: "Équilibrée" },
  { value: "colombes", label: "Colombes" },
  { value: "faucons", label: "Faucons" },
  { value: "aleatoire", label: "Aléatoire" },
] as const;

const INITIAL_SELECTED = ["usa", "china", "iran", "france", "egypt", "saudi_arabia", "uk"];

export function ConfigOverlay() {
  const { player } = useAuth();
  const { settings: userSettings } = useSettings();
  const { goPhase, setStage, setHandlers } = useStageDirector();
  const { launching, launch } = usePlanetLaunch();

  const [role, setRole] = useState<FlowRole>("player");
  const [summitSize, setSummitSize] = useState<number>(7);
  const [selected, setSelected] = useState<string[]>(INITIAL_SELECTED);
  const [flag, setFlag] = useState<string | null>("france");
  const [clickMode, setClickMode] = useState<"table" | "incarner">("table");
  const [flow, setFlow] = useState<FlowSettings>(DEFAULT_FLOW);
  const [turnSeconds, setTurnSeconds] = useState(120);
  const [inventName, setInventName] = useState("");
  const [inventConcept, setInventConcept] = useState("");
  const [researchModels, setResearchModels] = useState<ResearchModel[]>([]);
  const [castEnabled, setCastEnabled] = useState(false);
  const [castModels, setCastModels] = useState<string[]>([]);
  const [castAssignments, setCastAssignments] = useState<Record<string, string>>({});
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const capacity = mapCapacity(role, summitSize);

  useEffect(() => {
    getLab()
      .then((lab) => {
        const eligible = reasoningCountryModels(lab.model_panel.models);
        setResearchModels(eligible);
        setCastModels(defaultCountryCastModels(eligible));
      })
      .catch(() => setResearchModels([]));
  }, []);

  const onCountry = useCallback(
    (slug: string) => {
      if (clickMode === "incarner" && role === "player") {
        setSelected((cur) => {
          if (cur.includes(slug)) setFlag(slug);
          return cur;
        });
        return;
      }
      setSelected((cur) => {
        const next = toggleCountry(cur, slug, capacity);
        if (!next.includes(slug)) setFlag((f) => (f === slug ? null : f));
        return next;
      });
    },
    [capacity, clickMode, role],
  );

  // Entrer en phase config (globe cliquable, liseré doré, sélection initiale).
  useEffect(() => {
    goPhase("config", {
      pickable: [...ROSTER],
      countries: INITIAL_SELECTED,
      chosen: "france",
    });
  }, [goPhase]);

  // Garder le globe synchrone avec la composition.
  useEffect(() => {
    setStage({
      pickable: [...ROSTER],
      countries: selected,
      chosen: role === "player" ? flag : null,
    });
  }, [selected, role, flag, setStage]);

  // Relayer le clic-pays du globe vers la logique de composition.
  useEffect(() => {
    setHandlers({ onCountryClick: onCountry });
    return () => setHandlers({});
  }, [onCountry, setHandlers]);

  const pickRole = (r: FlowRole) => {
    setRole(r);
    setSelected((cur) => trimForRole(cur, r, summitSize));
    if (r !== "player") setClickMode("table");
    // GM, spectateur et ONU n'incarnent aucun pays.
    if (r === "gm" || r === "spectator" || r === "un") setFlag(null);
  };

  const pickSize = (size: number) => {
    setSummitSize(size);
    setSelected((cur) => trimForRole(cur, role, size));
  };

  const launchable =
    !creating &&
    !launching &&
    canLaunch(role, selected, { flag, inventName }, summitSize) &&
    (!castEnabled || castModels.length >= 1);

  const launch_ = async () => {
    if (!launchable) return;
    setCreating(true);
    setError(null);
    try {
      const activeCast = castEnabled ? castModels : castModels.slice(0, 1);
      const body = buildCreateBody({
        scenario: "red_sea",
        baseMode: "classic",
        settings: flow,
        role,
        selected,
        flag,
        ownerId: player?.id,
        invent:
          role === "invent"
            ? { name: inventName.trim(), concept: inventConcept.trim() || undefined }
            : undefined,
        language: userSettings.lang,
        modelCast: activeCast.length
          ? {
              strategy: "balanced",
              models: activeCast,
              assignments: castEnabled
                ? completeCountryAssignments(
                    selected,
                    activeCast,
                    castAssignments,
                    role === "player" ? flag : null,
                  )
                : undefined,
              game_master_model: activeCast[0],
              judge_model: activeCast[activeCast.length - 1],
            }
          : undefined,
      });
      const game = await createGame({ ...body, turn_seconds: turnSeconds });
      // Plongée (voile) vers le round 1 ; la caméra continue arrive en Inc 4.
      launch(`/games/${game.id}`);
    } catch (err) {
      setError(humanizeError(err));
      setCreating(false);
    }
  };

  return (
    <div className="pointer-events-none absolute bottom-3 right-3 top-3 z-20 flex w-[400px] max-w-[92vw] flex-col gap-2">
      <div className="thk-panel thk-cut pointer-events-auto flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto p-4 text-sm">
        <header className="flex items-center justify-between">
          <p className="thk-block-label">Composer la partie</p>
          <button type="button" className="thk-ghost" onClick={() => goPhase("hall")}>
            ← le hall
          </button>
        </header>

        {/* 1. Le siège occupé (5 rôles, dont l'ONU verrouillée → C5). */}
        <section className="space-y-1.5">
          <p className="thk-block-label">Ton siège</p>
          {ROLES.map((r) => {
            const isUn = r.value === "un";
            const active = role === r.value;
            return (
              <button
                key={r.value}
                type="button"
                onClick={() => pickRole(r.value as FlowRole)}
                className="thk-cast-row w-full"
                style={
                  active
                    ? { borderColor: "var(--thk-amber)", background: "rgba(255,193,77,.07)" }
                    : isUn
                      ? { borderColor: "rgba(91,146,229,.4)" }
                      : undefined
                }
              >
                <span
                  aria-hidden
                  className="grid h-6 w-6 shrink-0 place-items-center text-sm"
                  style={isUn ? { background: "#5b92e5", borderRadius: 3 } : undefined}
                >
                  {r.icon}
                </span>
                <span className="min-w-0 text-left">
                  <span className="block text-xs font-semibold">{r.label}</span>
                  <span className="block truncate text-[11px] text-fg-faint">{r.desc}</span>
                </span>
                {active && <span className="who-tag">TOI</span>}
              </button>
            );
          })}
        </section>

        {/* 2. Le sommet : taille + sélection AU CLIC SUR LE GLOBE. */}
        <section className="space-y-2">
          <p className="thk-block-label">
            Le sommet — {selected.length}/{capacity} au clic sur le globe
          </p>
          <Segmented
            ariaLabel="Taille du sommet"
            value={String(summitSize)}
            onChange={(v) => pickSize(Number(v))}
            size="sm"
            options={SUMMIT_SIZES.map((s) => ({
              value: String(s),
              label: s === 7 ? "7 ★" : String(s),
            }))}
          />
          {summitSize > 7 && (
            <p className="text-[11px] text-warn">
              ⚠ Chaque pays de plus = une réflexion de plus par round (pool mono-GPU) : les rounds
              seront sensiblement plus longs.
            </p>
          )}
          {role === "player" && (
            <Segmented
              ariaLabel="Action du clic sur le globe"
              value={clickMode}
              onChange={setClickMode}
              size="sm"
              options={[
                { value: "table", label: "✚ table" },
                { value: "incarner", label: "🎮 incarner" },
              ]}
            />
          )}
          <div className="flex flex-wrap gap-1.5">
            {selected.map((slug) => (
              <span
                key={slug}
                className="flex items-center gap-1 border border-edge px-1.5 py-0.5 text-[11px]"
                style={flag === slug ? { borderColor: "var(--thk-cyan)" } : undefined}
              >
                {speakerMeta(slug).label}
                {flag === slug && <span aria-hidden>🎮</span>}
                <button
                  type="button"
                  aria-label={`Retirer ${speakerMeta(slug).label}`}
                  className="text-fg-faint hover:text-bad"
                  onClick={() => onCountry(slug)}
                >
                  ✕
                </button>
              </span>
            ))}
            {selected.length === 0 && (
              <span className="text-[11px] text-fg-faint">
                Clique des pays sur le globe pour composer la table.
              </span>
            )}
          </div>
        </section>

        {/* 3. La forge (rôle Créer son pays). */}
        {role === "invent" && (
          <section className="space-y-2">
            <p className="thk-block-label">La forge — ton État ({capacity} + lui)</p>
            <input
              value={inventName}
              onChange={(e) => setInventName(e.target.value)}
              placeholder="Nom du pays (2 caractères min.)"
              className="thk-input text-sm"
            />
            <input
              value={inventConcept}
              onChange={(e) => setInventConcept(e.target.value)}
              placeholder="Concept (optionnel) : cité-État neutre, théocratie solaire…"
              className="thk-input text-sm"
            />
          </section>
        )}

        {/* 4. Les réglages transversaux (parité lobby). */}
        <section className="space-y-3">
          <p className="thk-block-label">Réglages</p>
          <Switch
            label="Brouillard"
            desc="Chaque pays perçoit sa propre version des faits — parfois fausse."
            checked={flow.fog}
            onChange={(v) => setFlow({ ...flow, fog: v })}
          />
          <Switch
            label="Crise qui monte"
            desc="Les rounds s'enchaînent, la tension grimpe."
            checked={flow.escalation}
            onChange={(v) => setFlow({ ...flow, escalation: v })}
          />
          <Switch
            label="Pensée à découvert"
            desc="Voir les IA penser en direct — mode observation."
            checked={flow.expose_thinking}
            onChange={(v) => setFlow({ ...flow, expose_thinking: v })}
          />
          <div>
            <p className="mb-1 text-xs text-fg-muted">Difficulté</p>
            <Segmented
              ariaLabel="Difficulté"
              size="sm"
              value={flow.difficulty}
              onChange={(v) => setFlow({ ...flow, difficulty: v })}
              options={[
                { value: "beginner", label: "Débutant" },
                { value: "intermediate", label: "Intermédiaire" },
                { value: "expert", label: "Expert" },
              ]}
            />
          </div>
          <label className="block text-xs text-fg-muted">
            Rounds : <span className="font-mono">{flow.rounds}</span>
            <input
              type="range"
              min={3}
              max={20}
              value={flow.rounds}
              onChange={(e) => setFlow({ ...flow, rounds: Number(e.target.value) })}
              className="mt-1 w-full"
            />
          </label>
          <label className="block text-xs text-fg-muted">
            Délai du tour humain : <span className="font-mono">{turnSeconds} s</span>
            <input
              type="range"
              min={30}
              max={300}
              step={10}
              value={turnSeconds}
              onChange={(e) => setTurnSeconds(Number(e.target.value))}
              className="mt-1 w-full"
            />
          </label>
          <Switch
            label="Partie libre"
            desc="Non classée — consignes globales et composition de table."
            checked={flow.free}
            onChange={(v) => setFlow({ ...flow, free: v })}
          />
          {flow.free && (
            <div>
              <p className="mb-1 text-xs text-fg-muted">Composition de la table (G17)</p>
              <Segmented
                ariaLabel="Composition de la table"
                size="sm"
                value={flow.table ?? "equilibree"}
                onChange={(v) => setFlow({ ...flow, table: v })}
                options={TABLES.map((tb) => ({ value: tb.value, label: tb.label }))}
              />
            </div>
          )}
        </section>

        {/* 5. Le casting des modèles (multi-modèles + assignations). */}
        {researchModels.length > 0 && (
          <section className="space-y-2">
            <ModelCastSelector
              models={researchModels}
              enabled={castEnabled}
              selected={castModels}
              onEnabled={setCastEnabled}
              onSelected={setCastModels}
              context="classic"
            />
            {castEnabled && castModels.length >= 1 && selected.length > 0 && (
              <CountryModelAssignments
                countries={selected}
                humanCountry={role === "player" ? flag : null}
                selectedModels={castModels}
                assignments={completeCountryAssignments(
                  selected,
                  castModels,
                  castAssignments,
                  role === "player" ? flag : null,
                )}
                onAssignments={setCastAssignments}
                compact
              />
            )}
          </section>
        )}

        {error && <Banner tone="bad">{error}</Banner>}
      </div>

      <button
        type="button"
        disabled={!launchable}
        onClick={launch_}
        className="thk-cta thk-cut-sm pointer-events-auto flex items-center justify-center gap-2 font-semibold"
      >
        {creating && <Spinner />}
        {creating
          ? "Lancement…"
          : `Lancer — ${summitSize} pays · ${flow.rounds} rounds${
              role === "player" && flag ? ` · ${speakerMeta(flag).label}` : ""
            }${role === "invent" && inventName ? ` · ${inventName}` : ""}`}
      </button>

      {launching && <div className="intro-veil pointer-events-auto fixed inset-0 z-30 bg-background" />}
    </div>
  );
}
