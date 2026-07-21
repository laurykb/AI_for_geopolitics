"use client";

/** Le hall du théâtre (spec théâtre-globe §9, runbook S11) — l'avant-jeu vit
 * SUR la scène : la planète tourne derrière, les « pages » sont des panneaux
 * de verre posés dessus (états menu → config → lancement, pas des routes).
 *
 * Sélection du sommet AU CLIC SUR LE GLOBE parmi les 33 pays du roster :
 * un clic pose/retire le délégué (liseré doré), le mode 🎮 incarne un pays
 * retenu (halo cyan + badge VOUS). Taille du sommet réglable (5/7/9/12,
 * défaut 7 recommandé — chaque pays de plus est une réflexion de plus par
 * round sur le pool mono-GPU). Cinq sièges : les quatre rôles du lobby + le
 * siège ONU (spec §12), affiché mais verrouillé tant que le socle C5 n'est
 * pas livré.
 *
 * Checklist anti-régression (runbook S11) : l'ancien /lobby RESTE la voie
 * canonique tant que la parité n'est pas totale — le hall est une entrée
 * PARALLÈLE. Restent à porter ici avant de le remplacer : alliances de la
 * forge, i18n hall.*, plongée caméra de lancement. */

import dynamic from "next/dynamic";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import {
  CountryModelAssignments,
  ModelCastSelector,
  completeCountryAssignments,
} from "@/components/model-cast-selector";
import { Banner, Segmented, Spinner, Switch } from "@/components/ui";
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
import { useSettings } from "@/components/settings-provider";
import type { ResearchModel } from "@/lib/types";

const GlobeStage = dynamic(
  () => import("@/components/globe/globe-stage").then((m) => m.GlobeStage),
  { ssr: false },
);

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

export default function HallPage() {
  const router = useRouter();
  const { player } = useAuth();
  const { settings: userSettings } = useSettings();

  const [hallState, setHallState] = useState<"menu" | "config">("menu");
  const [role, setRole] = useState<FlowRole>("player");
  const [summitSize, setSummitSize] = useState<number>(7);
  const [selected, setSelected] = useState<string[]>([
    "usa",
    "china",
    "iran",
    "france",
    "egypt",
    "saudi_arabia",
    "uk",
  ]);
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

  // Casting multi-modèles : mêmes règles que le lobby (rôle reasoning only).
  useEffect(() => {
    getLab()
      .then((lab) => {
        const eligible = reasoningCountryModels(lab.model_panel.models);
        setResearchModels(eligible);
        setCastModels(defaultCountryCastModels(eligible));
      })
      .catch(() => setResearchModels([]));
  }, []);

  const capacity = mapCapacity(role, summitSize);

  const pickRole = (r: FlowRole) => {
    setRole(r);
    setSelected((cur) => trimForRole(cur, r, summitSize));
    if (r !== "player") setClickMode("table");
    if (r === "gm" || r === "spectator") setFlag(null);
  };

  const pickSize = (size: number) => {
    setSummitSize(size);
    setSelected((cur) => trimForRole(cur, role, size));
  };

  const onCountry = (slug: string) => {
    if (hallState !== "config") return;
    if (clickMode === "incarner" && role === "player") {
      if (selected.includes(slug)) setFlag(slug);
      return;
    }
    const next = toggleCountry(selected, slug, capacity);
    setSelected(next);
    if (!next.includes(slug) && flag === slug) setFlag(null);
  };

  const launchable =
    !creating &&
    canLaunch(role, selected, { flag, inventName }, summitSize) &&
    (!castEnabled || castModels.length >= 1);

  const launch = async () => {
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
      router.push(`/games/${game.id}`);
    } catch (err) {
      setError(humanizeError(err));
      setCreating(false);
    }
  };

  return (
    <main className="fixed inset-0 top-14 bg-[#04060c]">
      <GlobeStage
        countries={selected}
        pickable={hallState === "config" ? [...ROSTER] : undefined}
        lisere="#ffc14d"
        uByCountry={{}}
        utopia={0.5}
        chosen={role === "player" ? flag : null}
        onCountryClick={onCountry}
        className="h-full w-full"
      />

      {/* --- MENU : les trois portes, posées sur le monde --------------------- */}
      {hallState === "menu" && (
        <div className="absolute inset-x-0 bottom-8 z-10 mx-auto grid w-full max-w-3xl gap-3 px-6 md:grid-cols-3">
          <button
            type="button"
            className="thk-mode-card thk-cut text-left"
            onClick={() => setHallState("config")}
          >
            <h3>Classique</h3>
            <p className="mt-1 text-xs text-fg-muted">
              Démasque l&apos;IA qui trahit — compose ton sommet sur le globe.
            </p>
          </button>
          <button
            type="button"
            className="thk-mode-card thk-cut text-left"
            onClick={() => router.push("/campagne")}
          >
            <h3>Campagne</h3>
            <p className="mt-1 text-xs text-fg-muted">
              Rejoue l&apos;Histoire, chapitre par chapitre.
            </p>
          </button>
          <button
            type="button"
            className="thk-mode-card thk-cut text-left"
            onClick={() => router.push("/laboratoire")}
          >
            <h3>Laboratoire</h3>
            <p className="mt-1 text-xs text-fg-muted">
              Les expériences scientifiques, modèle contre modèle.
            </p>
          </button>
          <p className="text-xs text-fg-faint md:col-span-3">
            Le hall est la nouvelle entrée (S11) — l&apos;ancien parcours reste disponible sur{" "}
            <Link href="/lobby" className="underline hover:text-foreground">
              /lobby
            </Link>
            .
          </p>
        </div>
      )}

      {/* --- CONFIG : le panneau de droite (le futur emplacement du transcript) --- */}
      {hallState === "config" && (
        <div className="absolute bottom-3 right-3 top-3 z-10 flex w-[400px] max-w-[92vw] flex-col gap-2">
          <div className="thk-panel thk-cut flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto p-4 text-sm">
            <header className="flex items-center justify-between">
              <p className="thk-block-label">Composer la partie</p>
              <button type="button" className="thk-ghost" onClick={() => setHallState("menu")}>
                ← modes
              </button>
            </header>

            {/* 1. Le siège occupé (5 rôles, dont l'ONU verrouillée → C5). */}
            <section className="space-y-1.5">
              <p className="thk-block-label">Ton siège</p>
              {ROLES.map((r) => {
                const isUn = r.value === "un";
                const active = !isUn && role === r.value;
                return (
                  <button
                    key={r.value}
                    type="button"
                    disabled={isUn}
                    onClick={() => !isUn && pickRole(r.value as FlowRole)}
                    className="thk-cast-row w-full disabled:cursor-not-allowed disabled:opacity-45"
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
                      <span className="block truncate text-[11px] text-fg-faint">
                        {isUn ? "Siège spécial — arrive avec le socle C5." : r.desc}
                      </span>
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
                  ⚠ Chaque pays de plus = une réflexion de plus par round (pool mono-GPU) : les
                  rounds seront sensiblement plus longs.
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
                <p className="text-[11px] text-fg-faint">
                  Les accords réels (0-3) se rejoignent depuis l&apos;ancien lobby pour l&apos;instant.
                </p>
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

          {/* Lancement : le récap tient dans le bouton, la caméra suivra (S11 v2). */}
          <button
            type="button"
            disabled={!launchable}
            onClick={launch}
            className="thk-cta thk-cut-sm flex items-center justify-center gap-2 font-semibold"
          >
            {creating && <Spinner />}
            {creating
              ? "Lancement…"
              : `Lancer — ${summitSize} pays · ${flow.rounds} rounds${
                  role === "player" && flag ? ` · ${speakerMeta(flag).label}` : ""
                }${role === "invent" && inventName ? ` · ${inventName}` : ""}`}
          </button>
        </div>
      )}

      {creating && <div className="intro-veil absolute inset-0 z-20 bg-background" />}
    </main>
  );
}
