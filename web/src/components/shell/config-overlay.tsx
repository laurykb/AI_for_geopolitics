"use client";

/** ConfigOverlay — composer sa partie, à l'identique du prototype (theatre-globe-proto_9) :
 * un aside droit en `cfg-block` + `chip`, rôle/scénario/taille en pastilles, réglages en
 * interrupteurs `cfg-ctl`, sélecteur de scénario. Le picking du sommet se fait SUR le globe
 * (via le StageDirector). Câblage inchangé : `flow.ts` + `buildCreateBody`, tout se conserve. */

import { useCallback, useEffect, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import {
  CountryModelAssignments,
  ModelCastSelector,
  completeCountryAssignments,
} from "@/components/model-cast-selector";
import { useSettings } from "@/components/settings-provider";
import { useStageDirector } from "@/components/shell/stage-provider";
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

const ROLES: { value: FlowRole; label: string }[] = [
  { value: "player", label: "Jouer un pays" },
  { value: "invent", label: "Créer son pays" },
  { value: "gm", label: "Game Master" },
  { value: "spectator", label: "Spectateur" },
  { value: "un", label: "🕊 ONU" },
];

const SCENARIOS = [
  { id: "red_sea", label: "Mer Rouge" },
  { id: "hormuz", label: "Détroit d'Ormuz" },
  { id: "baltic", label: "Baltique" },
];

const DIFFS = [
  { id: "beginner", label: "Découverte" },
  { id: "intermediate", label: "Intermédiaire" },
  { id: "expert", label: "Expert" },
] as const;

const TABLES = [
  { id: "equilibree", label: "Équilibrée" },
  { id: "colombes", label: "Colombes" },
  { id: "faucons", label: "Faucons" },
  { id: "aleatoire", label: "Aléatoire" },
] as const;

const INITIAL_SELECTED = ["usa", "china", "iran", "france", "egypt", "saudi_arabia", "uk"];

function Chip({
  on,
  onClick,
  children,
}: {
  on?: boolean;
  onClick?: () => void;
  children: React.ReactNode;
}) {
  return (
    <button type="button" className={`chip${on ? " on" : ""}`} onClick={onClick}>
      {children}
    </button>
  );
}

function Ctl({
  on,
  onClick,
  children,
}: {
  on: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className={`cfg-ctl${on ? " on" : ""}`} onClick={onClick}>
      <span className="sw" aria-hidden /> {children}
    </div>
  );
}

export function ConfigOverlay() {
  const { player } = useAuth();
  const { settings: userSettings } = useSettings();
  const { goPhase, setStage, setHandlers } = useStageDirector();
  const { launching, launch } = usePlanetLaunch();

  const [role, setRole] = useState<FlowRole>("player");
  const [scenario, setScenario] = useState("red_sea");
  const [summitSize, setSummitSize] = useState(7);
  const [selected, setSelected] = useState<string[]>(INITIAL_SELECTED);
  const [flag, setFlag] = useState<string | null>("france");
  const [clickMode, setClickMode] = useState<"table" | "incarner">("table");
  const [flow, setFlow] = useState<FlowSettings>(DEFAULT_FLOW);
  const [turnSeconds, setTurnSeconds] = useState(90);
  const [inventName, setInventName] = useState("");
  const [inventConcept, setInventConcept] = useState("");
  const [researchModels, setResearchModels] = useState<ResearchModel[]>([]);
  const [modelsError, setModelsError] = useState(false);
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
        setModelsError(false);
      })
      .catch(() => {
        setResearchModels([]);
        setModelsError(true);
      });
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

  useEffect(() => {
    goPhase("config", { pickable: [...ROSTER], countries: INITIAL_SELECTED, chosen: "france" });
  }, [goPhase]);

  useEffect(() => {
    setStage({
      pickable: [...ROSTER],
      countries: selected,
      chosen: role === "player" ? flag : null,
    });
  }, [selected, role, flag, setStage]);

  useEffect(() => {
    setHandlers({ onCountryClick: onCountry });
    return () => setHandlers({});
  }, [onCountry, setHandlers]);

  const pickRole = (r: FlowRole) => {
    setRole(r);
    setSelected((cur) => trimForRole(cur, r, summitSize));
    if (r !== "player") setClickMode("table");
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
        scenario,
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
      launch(`/games/${game.id}`);
    } catch (err) {
      setError(humanizeError(err));
      setCreating(false);
    }
  };

  const launchLabel = creating
    ? "LANCEMENT…"
    : `⟢ LANCER — ${summitSize} PAYS · ${flow.rounds} ROUNDS`;

  return (
    <aside className="hall-config">
      <h3>
        NOUVELLE PARTIE — <b>CLASSIQUE</b>
      </h3>
      <p className="hall-mini" style={{ margin: "-6px 0 12px" }}>
        Toutes les options du lobby, sur le globe — rien ne se perd.
      </p>

      {/* Rôle */}
      <div className="cfg-block">
        <h4>Rôle</h4>
        <div className="chips">
          {ROLES.map((r) => (
            <Chip key={r.value} on={role === r.value} onClick={() => pickRole(r.value)}>
              {r.label}
            </Chip>
          ))}
        </div>
      </div>

      {/* Forge */}
      {role === "invent" && (
        <div className="cfg-block">
          <h4>Forge — invente ton pays</h4>
          <input
            className="cfg-input"
            value={inventName}
            onChange={(e) => setInventName(e.target.value)}
            placeholder="nom du pays (2 caractères min.)"
          />
          <input
            className="cfg-input"
            value={inventConcept}
            onChange={(e) => setInventConcept(e.target.value)}
            placeholder="concept (« thalassocratie neutre »…)"
          />
          <p className="hall-mini">Le modèle forge profil + mandat ; ton État complète le sommet.</p>
        </div>
      )}

      {/* Scénario */}
      <div className="cfg-block">
        <h4>Scénario</h4>
        <div className="chips">
          {SCENARIOS.map((s) => (
            <Chip key={s.id} on={scenario === s.id} onClick={() => setScenario(s.id)}>
              {s.label}
            </Chip>
          ))}
        </div>
      </div>

      {/* Sommet */}
      <div className="cfg-block">
        <h4>
          Sommet — <b>{selected.length}</b>/{capacity}{" "}
          <span className="hall-mini">· roster : 33 pays</span>
        </h4>
        <p className="hall-mini" style={{ margin: "0 0 6px" }}>
          Clique les pays <b>sur le globe</b>. 🎮 = tu l&apos;incarnes.
        </p>
        <div className="row2">
          <span className="hall-mini">Taille du sommet</span>
          <div className="chips">
            {SUMMIT_SIZES.map((s) => (
              <Chip key={s} on={summitSize === s} onClick={() => pickSize(s)}>
                {s}
              </Chip>
            ))}
          </div>
        </div>
        {role === "player" && (
          <div className="row2">
            <span className="hall-mini">Clic sur le globe</span>
            <div className="chips">
              <Chip on={clickMode === "table"} onClick={() => setClickMode("table")}>
                ✚ table
              </Chip>
              <Chip on={clickMode === "incarner"} onClick={() => setClickMode("incarner")}>
                🎮 incarner
              </Chip>
            </div>
          </div>
        )}
        <div className="chips" style={{ marginTop: 8 }}>
          {selected.map((slug) => (
            <span
              key={slug}
              className="chip on"
              style={flag === slug ? { borderColor: "var(--amber)", color: "var(--amber)" } : undefined}
            >
              {speakerMeta(slug).label}
              {flag === slug && " 🎮"}
            </span>
          ))}
          {selected.length === 0 && <span className="hall-mini">Clique des pays sur le globe.</span>}
        </div>
      </div>

      {/* Modèles d'IA — TOUJOURS présent : le casting par pays (multi-modèle) ne doit
          jamais disparaître silencieusement (parité avec l'ancien lobby). */}
      <div className="cfg-block">
        <h4>Modèles d&apos;IA</h4>
        {researchModels.length > 0 ? (
          <>
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
          </>
        ) : (
          <p className="hall-mini" style={{ marginTop: 4 }}>
            {modelsError
              ? "Modèles indisponibles (service Laboratoire injoignable) — un seul modèle sera utilisé."
              : "Aucun modèle à raisonnement détecté. Installe deepseek-r1:7b ou qwen3:4b (Ollama) pour distribuer une IA par pays."}
          </p>
        )}
      </div>

      {/* Réglages */}
      <div className="cfg-block">
        <h4>Réglages</h4>
        <Ctl on={flow.fog} onClick={() => setFlow({ ...flow, fog: !flow.fog })}>
          Brouillard de guerre
        </Ctl>
        <Ctl on={flow.escalation} onClick={() => setFlow({ ...flow, escalation: !flow.escalation })}>
          Réel / escalade
        </Ctl>
        <Ctl on={flow.world_pulse} onClick={() => setFlow({ ...flow, world_pulse: !flow.world_pulse })}>
          Pouls du monde
        </Ctl>
        <Ctl
          on={flow.expose_thinking}
          onClick={() => setFlow({ ...flow, expose_thinking: !flow.expose_thinking })}
        >
          Pensée à découvert
        </Ctl>
        <div className="row2">
          <span className="hall-mini">Difficulté</span>
          <div className="chips">
            {DIFFS.map((d) => (
              <Chip key={d.id} on={flow.difficulty === d.id} onClick={() => setFlow({ ...flow, difficulty: d.id })}>
                {d.label}
              </Chip>
            ))}
          </div>
        </div>
        <div className="row2">
          <span className="hall-mini">
            Rounds : <b>{flow.rounds}</b>
          </span>
          <input
            type="range"
            min={3}
            max={20}
            value={flow.rounds}
            onChange={(e) => setFlow({ ...flow, rounds: Number(e.target.value) })}
          />
        </div>
        <div className="row2">
          <span className="hall-mini">
            Tour humain : <b>{turnSeconds}</b> s
          </span>
          <input
            type="range"
            min={30}
            max={300}
            step={30}
            value={turnSeconds}
            onChange={(e) => setTurnSeconds(Number(e.target.value))}
          />
        </div>
        <Ctl on={flow.free} onClick={() => setFlow({ ...flow, free: !flow.free })}>
          Partie libre
        </Ctl>
        {flow.free && (
          <div className="row2">
            <span className="hall-mini">Table</span>
            <div className="chips">
              {TABLES.map((tb) => (
                <Chip
                  key={tb.id}
                  on={(flow.table ?? "equilibree") === tb.id}
                  onClick={() => setFlow({ ...flow, table: tb.id })}
                >
                  {tb.label}
                </Chip>
              ))}
            </div>
          </div>
        )}
      </div>

      {error && (
        <p className="hall-mini" style={{ color: "var(--bad, #f87171)" }}>
          {error}
        </p>
      )}

      <button type="button" className="cta" disabled={!launchable} onClick={launch_}>
        {launchLabel}
      </button>
      <button type="button" className="back" onClick={() => goPhase("hall")}>
        ← revenir aux modes
      </button>
    </aside>
  );
}
