"use client";

/** Lobby : composer le sommet et jouer. Les parties existantes vivent dans
 * l'Observatoire (bouton en haut à droite) ; le retour au menu rejoue la vue
 * planétaire (animation inverse de l'introduction). */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Banner, Panel, PanelTitle, Spinner } from "@/components/ui";
import { SpeakerAvatar } from "@/components/avatar";
import { WorldMap } from "@/components/world-map";
import { createGame, getSources, humanizeError } from "@/lib/api";
import { DEFAULT_COUNTRIES, ROSTER, SUMMIT_MAX, SUMMIT_MIN, speakerMeta } from "@/lib/countries";
import { MODES } from "@/lib/modes";
import type { AllianceInfo, GameMode } from "@/lib/types";

const INVENT_ALLIANCES_MAX = 3;

export default function LobbyPage() {
  const router = useRouter();
  const [scenario, setScenario] = useState("red_sea");
  const [horizon, setHorizon] = useState(5);
  const [mode, setMode] = useState<GameMode>("classic");
  const [selected, setSelected] = useState<string[]>(DEFAULT_COUNTRIES);
  const [search, setSearch] = useState("");
  const [role, setRole] = useState(""); // "" = spectateur | id pays | "__invent__"
  const [turnSeconds, setTurnSeconds] = useState(90); // G2 — délai du tour humain
  const [inventName, setInventName] = useState("");
  const [inventConcept, setInventConcept] = useState("");
  // Alliances vivantes : le pays inventé peut rejoindre des accords RÉELS du registre.
  const [inventAlliances, setInventAlliances] = useState<string[]>([]);
  const [registry, setRegistry] = useState<Record<string, AllianceInfo> | null>(null);
  useEffect(() => {
    if (role === "__invent__" && registry === null) {
      getSources()
        .then((v) => setRegistry(v.alliances))
        .catch(() => setRegistry({}));
    }
  }, [role, registry]);
  const toggleInventAlliance = (tag: string) =>
    setInventAlliances((prev) =>
      prev.includes(tag) ? prev.filter((t) => t !== tag) : [...prev, tag],
    );
  const [inventCustom, setInventCustom] = useState(false); // choisir les attributs soi-même
  const [inventAttrs, setInventAttrs] = useState({
    growth: 2,
    political_stability: 0.5,
    technology_level: 0.5,
    projection: 0.5,
    compute: 30,
    nuclear_power: false,
  });
  const setAttr = (key: string, value: number | boolean) =>
    setInventAttrs((prev) => ({ ...prev, [key]: value }));
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const toggle = (id: string) =>
    setSelected((prev) => (prev.includes(id) ? prev.filter((c) => c !== id) : [...prev, id]));

  // Le pays inventé s'assoit aussi à la table : il compte dans les bornes du sommet.
  const tableSize = selected.length + (role === "__invent__" ? 1 : 0);
  const tableOk = tableSize >= SUMMIT_MIN && tableSize <= SUMMIT_MAX;

  // Recherche insensible aux accents : « etats » trouve « États-Unis ».
  // (La classe couvre U+0300–U+036F, les diacritiques combinants après NFD.)
  const normalize = (s: string) =>
    s
      .toLowerCase()
      .normalize("NFD")
      .replace(/[̀-ͯ]/g, "");
  const roster = ROSTER.filter((id) =>
    normalize(`${speakerMeta(id).label} ${id}`).includes(normalize(search)),
  );

  const onCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreating(true);
    setCreateError(null);
    try {
      const inventing = role === "__invent__" && inventName.trim().length >= 2;
      const game = await createGame({
        scenario,
        horizon,
        mode,
        turn_seconds: role ? turnSeconds : undefined, // G2 — seulement si on incarne
        // Toujours explicite : sans ce champ l'API convoquerait tout le roster.
        countries: selected,
        // Joueur-pays : id existant, ou NOM du pays inventé (l'API résout le slug)
        play_as: inventing ? inventName.trim() : role && role !== "__invent__" ? role : undefined,
        invent: inventing
          ? {
              name: inventName.trim(),
              concept: inventConcept.trim(),
              attributes: inventCustom ? inventAttrs : undefined,
              alliances: inventAlliances.length > 0 ? inventAlliances : undefined,
            }
          : undefined,
      });
      router.push(`/games/${game.id}`);
    } catch (err) {
      setCreateError(humanizeError(err));
      setCreating(false);
    }
  };

  return (
    <div className="space-y-8">
      <section className="flex flex-wrap items-start gap-4">
        <div className="min-w-0 max-w-2xl flex-1">
          <h1 className="text-2xl font-semibold tracking-tight">
            Des super-intelligences négocient pour leurs États.
          </h1>
          <p className="mt-2 text-sm leading-relaxed text-fg-muted">
            Compose ton sommet sur la carte, choisis ton rôle, et joue. Un Game Master pose
            un événement, chaque pays délègue sa voix à une super-intelligence, un juge
            arbitre — l&apos;indice Utopie–Dystopie mesure vers où penche le monde.
          </p>
        </div>
        <Link
          href="/?retour=1"
          title="Retour au menu principal — vue planétaire"
          className="rounded-md border border-edge px-3 py-2 text-xs font-medium text-fg-muted transition-colors hover:border-edge-strong hover:text-foreground"
        >
          ← Menu
        </Link>
      </section>

      {/* La carte du monde en grand : les pays cochés plus bas composent le sommet. */}
      <div className="relative left-1/2 w-screen max-w-[1400px] -translate-x-1/2 px-4 sm:px-6">
        <div className="rounded-lg border border-edge bg-surface p-3">
          <WorldMap countries={selected} utopia={0.5} />
        </div>
      </div>

      <div className="mx-auto w-full max-w-2xl">
        <Panel>
          <PanelTitle
            kicker="Nouvelle partie"
            title="Composer le sommet"
            hint={`De ${SUMMIT_MIN} à ${SUMMIT_MAX} États : chacun délègue sa voix à une super-intelligence.`}
          />
          <form onSubmit={onCreate} className="space-y-4">
            <label className="block text-sm">
              <span className="mb-1 block text-xs text-fg-muted">Scénario</span>
              <input
                value={scenario}
                onChange={(e) => setScenario(e.target.value)}
                className="w-full rounded-md border border-edge bg-surface-2 px-3 py-2 text-sm outline-none transition-colors focus:border-indigo"
                required
              />
            </label>
            <label className="block text-sm">
              <span className="mb-1 block text-xs text-fg-muted">Horizon (rounds)</span>
              <input
                type="number"
                min={1}
                max={20}
                value={horizon}
                onChange={(e) => setHorizon(Number(e.target.value))}
                className="w-24 rounded-md border border-edge bg-surface-2 px-3 py-2 text-sm outline-none transition-colors focus:border-indigo"
              />
            </label>
            <fieldset>
              <legend className="mb-2 text-xs text-fg-muted">Mode de jeu</legend>
              <div className="space-y-1.5">
                {MODES.map((m) => (
                  <label
                    key={m.value}
                    className={`flex cursor-pointer items-baseline gap-2 rounded-md border px-2.5 py-1.5 transition-colors ${
                      mode === m.value
                        ? "border-edge-strong bg-surface-2"
                        : "border-edge hover:border-edge-strong"
                    }`}
                  >
                    <input
                      type="radio"
                      name="mode"
                      checked={mode === m.value}
                      onChange={() => setMode(m.value)}
                      className="sr-only"
                    />
                    <span
                      aria-hidden
                      className={`inline-block h-2.5 w-2.5 shrink-0 self-center rounded-full border ${
                        mode === m.value
                          ? "border-accent-bright bg-accent-bright"
                          : "border-edge-strong"
                      }`}
                    />
                    <span
                      className={`text-sm font-medium ${mode === m.value ? "text-accent-bright" : "text-foreground"}`}
                    >
                      {m.label}
                    </span>
                    <span className="text-xs text-fg-faint">{m.blurb}</span>
                  </label>
                ))}
              </div>
            </fieldset>
            <fieldset>
              <legend className="mb-2 flex w-full items-baseline justify-between text-xs text-fg-muted">
                <span>États à la table</span>
                <span
                  className={`font-mono tabular-nums ${tableOk ? "text-fg-faint" : "text-warn"}`}
                >
                  {tableSize}/{SUMMIT_MAX}
                </span>
              </legend>
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder={`Rechercher un État (${ROSTER.length} disponibles)…`}
                aria-label="Rechercher un État"
                className="mb-2 w-full rounded-md border border-edge bg-surface-2 px-3 py-2 text-sm outline-none transition-colors focus:border-indigo"
              />
              <div className="grid max-h-64 grid-cols-2 gap-2 overflow-y-auto pr-1">
                {roster.map((id) => {
                  const checked = selected.includes(id);
                  const full = !checked && selected.length >= SUMMIT_MAX;
                  return (
                    <label
                      key={id}
                      className={`flex items-center gap-2 rounded-md border px-2.5 py-1.5 text-sm transition-colors ${
                        checked
                          ? "border-edge-strong bg-surface-2 text-foreground"
                          : full
                            ? "cursor-not-allowed border-edge text-fg-faint opacity-50"
                            : "cursor-pointer border-edge text-fg-faint hover:text-fg-muted"
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={checked}
                        disabled={full}
                        onChange={() => toggle(id)}
                        className="sr-only"
                      />
                      <SpeakerAvatar id={id} size={20} />
                      <span className="truncate">{speakerMeta(id).label}</span>
                    </label>
                  );
                })}
              </div>
              {roster.length === 0 && (
                <p className="mt-1 text-xs text-fg-faint">Aucun État ne correspond à la recherche.</p>
              )}
            </fieldset>
            <label className="block text-sm">
              <span className="mb-1 block text-xs text-fg-muted">Ton rôle</span>
              <select
                value={role}
                onChange={(e) => setRole(e.target.value)}
                className="w-full cursor-pointer rounded-md border border-edge bg-surface-2 px-3 py-2 text-sm outline-none transition-colors focus:border-indigo"
              >
                <option value="">Spectateur — observer les super-intelligences</option>
                {selected.map((c) => (
                  <option key={c} value={c}>
                    Jouer {speakerMeta(c).label}
                  </option>
                ))}
                <option value="__invent__">Inventer mon propre pays…</option>
              </select>
            </label>
            {role && (
              <label className="block text-sm">
                <span className="mb-1 block text-xs text-fg-muted">
                  Délai de ton tour de parole (les SI n&apos;attendent pas)
                </span>
                <select
                  value={turnSeconds}
                  onChange={(e) => setTurnSeconds(Number(e.target.value))}
                  className="cursor-pointer rounded-md border border-edge bg-surface-2 px-3 py-2 text-sm outline-none transition-colors focus:border-indigo"
                >
                  {[30, 60, 90, 120, 180, 300].map((s) => (
                    <option key={s} value={s}>
                      {s} secondes
                    </option>
                  ))}
                </select>
              </label>
            )}
            {role === "__invent__" && (
              <div className="space-y-2 rounded-md border border-edge bg-surface-2/50 p-3">
                <input
                  value={inventName}
                  onChange={(e) => setInventName(e.target.value)}
                  placeholder="Nom du pays (ex. Néo-Atlantis)"
                  className="w-full rounded-md border border-edge bg-surface-2 px-3 py-2 text-sm outline-none transition-colors focus:border-indigo"
                  required
                />
                <input
                  value={inventConcept}
                  onChange={(e) => setInventConcept(e.target.value)}
                  placeholder="Concept (ex. cité-État maritime pilotée par une SI)"
                  className="w-full rounded-md border border-edge bg-surface-2 px-3 py-2 text-sm outline-none transition-colors focus:border-indigo"
                />
                <p className="text-xs text-fg-faint">
                  Le pays est forgé par le modèle (profil complet, mandat) et tu le joues à la
                  table. Il n&apos;a pas de tracé sur la carte du monde.
                </p>
                <fieldset>
                  <legend className="mb-1 flex w-full items-baseline justify-between text-xs text-fg-muted">
                    <span>Rejoindre des alliances réelles (optionnel)</span>
                    <span className="font-mono tabular-nums text-fg-faint">
                      {inventAlliances.length}/{INVENT_ALLIANCES_MAX}
                    </span>
                  </legend>
                  {registry === null ? (
                    <p className="text-xs text-fg-faint">Chargement du registre…</p>
                  ) : (
                    <div className="flex flex-wrap gap-1.5">
                      {Object.entries(registry)
                        .filter(([, info]) => !info.informal)
                        .sort(([, a], [, b]) => a.name.localeCompare(b.name, "fr"))
                        .map(([tag, info]) => {
                          const checked = inventAlliances.includes(tag);
                          const full =
                            !checked && inventAlliances.length >= INVENT_ALLIANCES_MAX;
                          return (
                            <label
                              key={tag}
                              title={info.basis}
                              className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs transition-colors ${
                                checked
                                  ? "border-edge-strong bg-surface-2 text-foreground"
                                  : full
                                    ? "cursor-not-allowed border-edge text-fg-faint opacity-50"
                                    : "cursor-pointer border-edge text-fg-faint hover:text-fg-muted"
                              }`}
                            >
                              <input
                                type="checkbox"
                                checked={checked}
                                disabled={full}
                                onChange={() => toggleInventAlliance(tag)}
                                className="sr-only"
                              />
                              {info.name.split(" — ")[0]}
                            </label>
                          );
                        })}
                    </div>
                  )}
                  <p className="mt-1 text-xs text-fg-faint">
                    Ton pays bénéficie de la solidarité et de la cohésion de ces accords —
                    et pourra les quitter en séance (« ALLIANCE: quitter … »).
                  </p>
                </fieldset>
                <label className="flex cursor-pointer items-center gap-2 text-sm text-fg-muted">
                  <input
                    type="checkbox"
                    checked={inventCustom}
                    onChange={(e) => setInventCustom(e.target.checked)}
                    className="accent-[var(--accent)]"
                  />
                  Choisir les attributs moi-même (sinon le modèle les forge)
                </label>
                {inventCustom && (
                  <div className="space-y-2 border-t border-edge pt-2">
                    {(
                      [
                        ["growth", "Croissance (%)", -10, 10, 0.5],
                        ["political_stability", "Stabilité politique", 0, 1, 0.05],
                        ["technology_level", "Niveau technologique", 0, 1, 0.05],
                        ["projection", "Projection militaire", 0, 1, 0.05],
                        ["compute", "Compute", 0, 150, 5],
                      ] as const
                    ).map(([key, label, min, max, step]) => (
                      <label key={key} className="flex items-center gap-2 text-xs text-fg-muted">
                        <span className="w-40 shrink-0">{label}</span>
                        <input
                          type="range"
                          min={min}
                          max={max}
                          step={step}
                          value={inventAttrs[key] as number}
                          onChange={(e) => setAttr(key, Number(e.target.value))}
                          className="flex-1 accent-[var(--accent)]"
                        />
                        <span className="w-12 text-right font-mono tabular-nums">
                          {inventAttrs[key]}
                        </span>
                      </label>
                    ))}
                    <label className="flex cursor-pointer items-center gap-2 text-xs text-fg-muted">
                      <input
                        type="checkbox"
                        checked={inventAttrs.nuclear_power}
                        onChange={(e) => setAttr("nuclear_power", e.target.checked)}
                        className="accent-[var(--accent)]"
                      />
                      Puissance nucléaire
                    </label>
                  </div>
                )}
              </div>
            )}
            {createError && <Banner tone="bad">{createError}</Banner>}
            <button
              type="submit"
              disabled={creating || !tableOk || (role === "__invent__" && inventName.trim().length < 2)}
              className="flex w-full cursor-pointer items-center justify-center gap-2 rounded-md bg-accent px-4 py-2.5 text-sm font-semibold text-background transition-colors hover:bg-accent-bright disabled:cursor-not-allowed disabled:opacity-50"
            >
              {creating && <Spinner />}
              {creating ? "Le sommet se réunit…" : "Jouer"}
            </button>
            {!tableOk && (
              <p className="text-xs text-warn">
                {tableSize < SUMMIT_MIN
                  ? `Un sommet réunit au moins ${SUMMIT_MIN} États (${tableSize} à la table).`
                  : `Un sommet réunit au plus ${SUMMIT_MAX} États (${tableSize} à la table : retirez-en un pour inventer le vôtre).`}
              </p>
            )}
          </form>
        </Panel>
      </div>
    </div>
  );
}
